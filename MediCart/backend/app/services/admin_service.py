from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.models.audit import AuditLog
from app.models.catalogue import Inventory, Medicine, MedicineCategory, Product
from app.models.enums import (
    AIReviewStatus,
    OrderStatus,
    UserConfirmationStatus,
    UserRole,
    VerificationStatus,
    allowed_transitions,
)
from app.models.order import Order, OrderItem
from app.models.prescription import Prescription, PrescriptionItem
from app.models.user import User
from app.schemas.admin import (
    AdminCategoryOut,
    AdminOrderOut,
    AdminPrescriptionListItem,
    AdminUserOut,
    AdminUserUpdate,
    AuditLogOut,
    CategoryIn,
    CategoryUpdate,
    DashboardOut,
    InventoryUpdate,
    LowStockItem,
    MedicineCreate,
    MedicineUpdate,
    PrescriptionStats,
    ProductIn,
    ProductUpdate,
)
from app.schemas.order import OrderStatusUpdate
from app.services import audit_service, order_service
from app.services.catalogue_service import invalidate_home_cache
from app.utils.pagination import PageParams
from app.utils.text import slugify

OPEN_ORDER_STATUSES = {
    OrderStatus.PLACED.value,
    OrderStatus.VERIFICATION_PENDING.value,
    OrderStatus.VERIFIED.value,
    OrderStatus.PROCESSING.value,
    OrderStatus.PACKED.value,
    OrderStatus.SHIPPED.value,
}


def _count(db: Session, stmt) -> int:
    return int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)


# ---------------------------------------------------------------- dashboard


def dashboard(db: Session) -> DashboardOut:
    status_rows = db.execute(
        select(Order.order_status, func.count(Order.id)).group_by(Order.order_status)
    ).all()
    by_status = {status: int(count) for status, count in status_rows}
    total_orders = sum(by_status.values())

    revenue = db.scalar(
        select(func.coalesce(func.sum(Order.order_total), 0)).where(
            Order.order_status != OrderStatus.CANCELLED.value
        )
    )

    rx_rows = db.execute(
        select(Prescription.pharmacist_verification_status, func.count(Prescription.id)).group_by(
            Prescription.pharmacist_verification_status
        )
    ).all()
    rx_by_status = {status: int(count) for status, count in rx_rows}

    recent = db.scalars(
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.user), selectinload(Order.shipment))
        .order_by(Order.created_at.desc(), Order.id.desc())
        .limit(8)
    ).all()

    low_stock_rows = db.execute(
        select(Product.id, Medicine.medicine_name, Product.pack_size, Inventory.available_quantity)
        .join(Medicine, Medicine.id == Product.medicine_id)
        .join(Inventory, Inventory.product_id == Product.id)
        .where(Product.is_active.is_(True), Medicine.is_active.is_(True), Inventory.available_quantity <= 10)
        .order_by(Inventory.available_quantity.asc())
        .limit(8)
    ).all()

    return DashboardOut(
        total_customers=_count(db, select(User.id).where(User.role == UserRole.CUSTOMER.value)),
        total_medicines=_count(db, select(Medicine.id).where(Medicine.is_active.is_(True))),
        total_products=_count(db, select(Product.id).where(Product.is_active.is_(True))),
        total_orders=total_orders,
        pending_orders=sum(c for s, c in by_status.items() if s in OPEN_ORDER_STATUSES),
        completed_orders=by_status.get(OrderStatus.DELIVERED.value, 0),
        cancelled_orders=by_status.get(OrderStatus.CANCELLED.value, 0),
        simulated_revenue=Decimal(revenue or 0),
        prescriptions=PrescriptionStats(
            total=sum(rx_by_status.values()),
            awaiting_confirmation=_count(
                db,
                select(Prescription.id).where(
                    Prescription.user_confirmation_status == UserConfirmationStatus.PENDING.value
                ),
            ),
            pending_verification=rx_by_status.get(VerificationStatus.PENDING.value, 0),
            approved=rx_by_status.get(VerificationStatus.APPROVED.value, 0),
            rejected=rx_by_status.get(VerificationStatus.REJECTED.value, 0),
            clarification_requested=rx_by_status.get(VerificationStatus.CLARIFICATION_REQUESTED.value, 0),
            uncertain_items=_count(
                db, select(PrescriptionItem.id).where(PrescriptionItem.uncertainty_status == "uncertain")
            ),
            ai_fallback=_count(
                db,
                select(Prescription.id).where(
                    Prescription.ai_review_status.in_(
                        [AIReviewStatus.FALLBACK.value, AIReviewStatus.UNAVAILABLE.value]
                    )
                ),
            ),
        ),
        recent_orders=[_admin_order(o) for o in recent],
        low_stock=[
            LowStockItem(product_id=pid, medicine_name=name, pack_size=pack, available_quantity=qty)
            for pid, name, pack, qty in low_stock_rows
        ],
        orders_by_status=by_status,
    )


# -------------------------------------------------------------------- users


def list_users(
    db: Session, params: PageParams, q: str | None = None, role: str | None = None
) -> tuple[list[AdminUserOut], int]:
    order_counts = select(Order.user_id, func.count(Order.id).label("n")).group_by(Order.user_id).subquery()
    stmt = select(User, func.coalesce(order_counts.c.n, 0)).outerjoin(
        order_counts, order_counts.c.user_id == User.id
    )
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(User.full_name.ilike(like), User.mobile_number.ilike(like), User.email.ilike(like))
        )
    if role:
        stmt = stmt.where(User.role == role)
    total = _count(db, stmt.with_only_columns(User.id))
    rows = db.execute(
        stmt.order_by(User.created_at.desc()).offset(params.offset).limit(params.page_size)
    ).all()
    users = []
    for user, count in rows:
        out = AdminUserOut.model_validate(user)
        out.order_count = int(count)
        users.append(out)
    return users, total


def update_user(db: Session, admin: User, user_id: int, data: AdminUserUpdate) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found")
    if user.id == admin.id and (data.is_active is False or (data.role and data.role != UserRole.ADMIN)):
        raise ForbiddenError("You cannot deactivate or demote your own account")
    changes = {}
    if data.role is not None and data.role.value != user.role:
        changes["role"] = {"from": user.role, "to": data.role.value}
        user.role = data.role.value
    if data.is_active is not None and data.is_active != user.is_active:
        changes["is_active"] = {"from": user.is_active, "to": data.is_active}
        user.is_active = data.is_active
    if changes:
        audit_service.record(
            db, actor_id=admin.id, action="user.updated", target_type="user", target_id=user.id, meta=changes
        )
        db.commit()
        db.refresh(user)
    return user


# --------------------------------------------------------------- categories


def list_categories(db: Session) -> list[AdminCategoryOut]:
    counts = (
        select(Medicine.category_id, func.count(Medicine.id).label("n"))
        .group_by(Medicine.category_id)
        .subquery()
    )
    rows = db.execute(
        select(MedicineCategory, func.coalesce(counts.c.n, 0))
        .outerjoin(counts, counts.c.category_id == MedicineCategory.id)
        .order_by(MedicineCategory.sort_order, MedicineCategory.name)
    ).all()
    result = []
    for category, count in rows:
        out = AdminCategoryOut.model_validate(category)
        out.medicine_count = int(count)
        result.append(out)
    return result


def _unique_slug(db: Session, base: str, exclude_id: int | None = None) -> str:
    slug = slugify(base)
    candidate, n = slug, 2
    while True:
        stmt = select(MedicineCategory.id).where(MedicineCategory.slug == candidate)
        if exclude_id is not None:
            stmt = stmt.where(MedicineCategory.id != exclude_id)
        if db.scalar(stmt) is None:
            return candidate
        candidate = f"{slug}-{n}"
        n += 1


def create_category(db: Session, admin: User, data: CategoryIn) -> MedicineCategory:
    if db.scalar(select(MedicineCategory.id).where(MedicineCategory.name == data.name)):
        raise ConflictError("A category with this name already exists")
    category = MedicineCategory(
        name=data.name,
        slug=_unique_slug(db, data.slug or data.name),
        description=data.description,
        icon=data.icon,
        sort_order=data.sort_order,
        is_active=data.is_active,
    )
    db.add(category)
    db.flush()
    audit_service.record(
        db, actor_id=admin.id, action="category.created", target_type="category", target_id=category.id
    )
    db.commit()
    db.refresh(category)
    return category


def update_category(db: Session, admin: User, category_id: int, data: CategoryUpdate) -> MedicineCategory:
    category = db.get(MedicineCategory, category_id)
    if category is None:
        raise NotFoundError("Category not found")
    changes = data.model_dump(exclude_unset=True)
    if "slug" in changes:
        changes["slug"] = _unique_slug(db, changes["slug"] or category.name, exclude_id=category.id)
    for key, value in changes.items():
        setattr(category, key, value)
    audit_service.record(
        db, actor_id=admin.id, action="category.updated", target_type="category", target_id=category.id
    )
    db.commit()
    db.refresh(category)
    return category


def delete_category(db: Session, admin: User, category_id: int) -> None:
    category = db.get(MedicineCategory, category_id)
    if category is None:
        raise NotFoundError("Category not found")
    in_use = db.scalar(select(func.count(Medicine.id)).where(Medicine.category_id == category.id))
    if in_use:
        raise ConflictError(
            f"{in_use} medicine(s) still use this category. Move them first.", code="category_in_use"
        )
    db.delete(category)
    audit_service.record(
        db, actor_id=admin.id, action="category.deleted", target_type="category", target_id=category_id
    )
    db.commit()


# ---------------------------------------------------------------- medicines


def _medicine_stmt():
    return select(Medicine).options(
        selectinload(Medicine.products).selectinload(Product.inventory),
        selectinload(Medicine.category),
    )


def get_medicine(db: Session, medicine_id: int) -> Medicine:
    medicine = db.scalar(_medicine_stmt().where(Medicine.id == medicine_id))
    if medicine is None:
        raise NotFoundError("Medicine not found")
    return medicine


def list_medicines(
    db: Session,
    params: PageParams,
    q: str | None = None,
    category_id: int | None = None,
    include_inactive: bool = True,
) -> tuple[list[Medicine], int]:
    stmt = _medicine_stmt()
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Medicine.medicine_name.ilike(like),
                Medicine.brand_name.ilike(like),
                Medicine.generic_name.ilike(like),
                Medicine.manufacturer.ilike(like),
            )
        )
    if category_id is not None:
        stmt = stmt.where(Medicine.category_id == category_id)
    if not include_inactive:
        stmt = stmt.where(Medicine.is_active.is_(True))
    total = _count(db, select(Medicine.id).where(*stmt._where_criteria))
    rows = db.scalars(
        stmt.order_by(Medicine.updated_at.desc(), Medicine.id.desc())
        .offset(params.offset)
        .limit(params.page_size)
    ).all()
    return list(rows), total


def _next_sku(db: Session, medicine: Medicine) -> str:
    existing = {p.sku for p in medicine.products}
    n = len(medicine.products) + 1
    while True:
        sku = f"MC-{medicine.id:04d}-{n:02d}"
        if sku not in existing and db.scalar(select(Product.id).where(Product.sku == sku)) is None:
            return sku
        n += 1


def _validate_category(db: Session, category_id: int | None) -> None:
    if category_id is not None and db.get(MedicineCategory, category_id) is None:
        raise ValidationError("Category does not exist", code="invalid_category")


def _build_product(db: Session, medicine: Medicine, data: ProductIn) -> Product:
    sku = data.sku.strip() if data.sku else None
    if sku and db.scalar(select(Product.id).where(Product.sku == sku)):
        raise ConflictError(f"SKU '{sku}' is already in use", code="sku_taken")
    product = Product(
        sku=sku or _next_sku(db, medicine),
        pack_size=data.pack_size,
        mrp=data.mrp,
        price=data.price,
        is_active=data.is_active,
    )
    product.inventory = Inventory(
        available_quantity=data.available_quantity,
        batch_number=data.batch_number,
        expiry_date=data.expiry_date,
    )
    return product


def create_medicine(db: Session, admin: User, data: MedicineCreate) -> Medicine:
    _validate_category(db, data.category_id)
    medicine = Medicine(**data.model_dump(exclude={"products"}))
    db.add(medicine)
    db.flush()
    for product_in in data.products:
        medicine.products.append(_build_product(db, medicine, product_in))
    db.flush()
    audit_service.record(
        db, actor_id=admin.id, action="medicine.created", target_type="medicine", target_id=medicine.id
    )
    db.commit()
    invalidate_home_cache()
    return get_medicine(db, medicine.id)


def update_medicine(db: Session, admin: User, medicine_id: int, data: MedicineUpdate) -> Medicine:
    medicine = get_medicine(db, medicine_id)
    changes = data.model_dump(exclude_unset=True)
    if "category_id" in changes:
        _validate_category(db, changes["category_id"])
    for key, value in changes.items():
        setattr(medicine, key, value)
    audit_service.record(
        db,
        actor_id=admin.id,
        action="medicine.updated",
        target_type="medicine",
        target_id=medicine.id,
        meta={"fields": sorted(changes)},
    )
    db.commit()
    invalidate_home_cache()
    return get_medicine(db, medicine.id)


def delete_medicine(db: Session, admin: User, medicine_id: int) -> str:
    medicine = get_medicine(db, medicine_id)
    product_ids = [p.id for p in medicine.products]
    referenced = 0
    if product_ids:
        referenced = db.scalar(select(func.count(OrderItem.id)).where(OrderItem.product_id.in_(product_ids)))
    if referenced:
        medicine.is_active = False
        for product in medicine.products:
            product.is_active = False
        outcome = "deactivated"
    else:
        db.delete(medicine)
        outcome = "deleted"
    audit_service.record(
        db,
        actor_id=admin.id,
        action=f"medicine.{outcome}",
        target_type="medicine",
        target_id=medicine_id,
        meta={"order_items_referencing": int(referenced or 0)},
    )
    db.commit()
    invalidate_home_cache()
    return outcome


def add_product(db: Session, admin: User, medicine_id: int, data: ProductIn) -> Medicine:
    medicine = get_medicine(db, medicine_id)
    medicine.products.append(_build_product(db, medicine, data))
    db.flush()
    audit_service.record(
        db, actor_id=admin.id, action="product.created", target_type="medicine", target_id=medicine.id
    )
    db.commit()
    invalidate_home_cache()
    return get_medicine(db, medicine.id)


def _get_product(db: Session, product_id: int) -> Product:
    product = db.scalar(
        select(Product).where(Product.id == product_id).options(selectinload(Product.inventory))
    )
    if product is None:
        raise NotFoundError("Product not found")
    return product


def update_product(db: Session, admin: User, product_id: int, data: ProductUpdate) -> Medicine:
    product = _get_product(db, product_id)
    changes = data.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(product, key, value)
    if product.price > product.mrp:
        raise ValidationError("Selling price cannot be higher than MRP")
    audit_service.record(
        db,
        actor_id=admin.id,
        action="product.updated",
        target_type="product",
        target_id=product.id,
        meta={"fields": sorted(changes)},
    )
    db.commit()
    invalidate_home_cache()
    return get_medicine(db, product.medicine_id)


def update_inventory(db: Session, admin: User, product_id: int, data: InventoryUpdate) -> Medicine:
    product = _get_product(db, product_id)
    inventory = product.inventory or Inventory(product_id=product.id)
    previous = inventory.available_quantity
    inventory.available_quantity = data.available_quantity
    inventory.batch_number = data.batch_number
    inventory.expiry_date = data.expiry_date
    product.inventory = inventory
    audit_service.record(
        db,
        actor_id=admin.id,
        action="inventory.updated",
        target_type="product",
        target_id=product.id,
        meta={"from": previous, "to": data.available_quantity},
    )
    db.commit()
    invalidate_home_cache()
    return get_medicine(db, product.medicine_id)


# ------------------------------------------------------------------- orders


def _admin_order(order: Order) -> AdminOrderOut:
    out = AdminOrderOut.model_validate(order)
    out.item_count = sum(i.quantity for i in order.items)
    out.delivered_at = order_service.delivered_at(order)
    out.allowed_next_statuses = [s.value for s in allowed_transitions(OrderStatus(order.order_status))]
    out.customer_name = order.user.full_name if order.user else ""
    out.customer_mobile = order.user.mobile_number if order.user else ""
    return out


def list_orders(
    db: Session, params: PageParams, status: str | None = None, q: str | None = None
) -> tuple[list[AdminOrderOut], int]:
    stmt = select(Order).options(
        selectinload(Order.items), selectinload(Order.user), selectinload(Order.shipment)
    )
    if status:
        stmt = stmt.where(Order.order_status == status)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.join(User, User.id == Order.user_id).where(
            or_(Order.order_number.ilike(like), User.full_name.ilike(like), User.mobile_number.ilike(like))
        )
    total = _count(db, stmt.with_only_columns(Order.id))
    rows = db.scalars(
        stmt.order_by(Order.created_at.desc(), Order.id.desc()).offset(params.offset).limit(params.page_size)
    ).all()
    return [_admin_order(o) for o in rows], total


def get_order(db: Session, order_id: int) -> Order:
    return order_service.get_order(db, None, order_id)


def update_order_status(db: Session, admin: User, order_id: int, data: OrderStatusUpdate) -> Order:
    order = order_service.get_order(db, None, order_id)
    return order_service.transition_order(
        db,
        order,
        data.order_status,
        actor=admin,
        tracking_reference=data.tracking_reference,
        note=data.note,
    )


# ------------------------------------------------------------ prescriptions


def list_prescriptions(
    db: Session, params: PageParams, status: str | None = None
) -> tuple[list[AdminPrescriptionListItem], int]:
    stmt = select(Prescription).options(selectinload(Prescription.items), selectinload(Prescription.user))
    if status:
        stmt = stmt.where(Prescription.pharmacist_verification_status == status)
    total = _count(db, stmt.with_only_columns(Prescription.id))
    rows = db.scalars(
        stmt.order_by(Prescription.created_at.desc(), Prescription.id.desc())
        .offset(params.offset)
        .limit(params.page_size)
    ).all()
    items = []
    for prescription in rows:
        out = AdminPrescriptionListItem.model_validate(prescription)
        out.ocr_confidence = (
            float(prescription.ocr_confidence) if prescription.ocr_confidence is not None else None
        )
        out.item_count = len(prescription.items)
        out.uncertain_item_count = sum(1 for i in prescription.items if i.uncertainty_status == "uncertain")
        out.customer_name = prescription.user.full_name if prescription.user else ""
        items.append(out)
    return items, total


# --------------------------------------------------------------- audit logs


def recent_audit_logs(db: Session, limit: int = 100) -> list[AuditLogOut]:
    rows = db.scalars(
        select(AuditLog)
        .options(selectinload(AuditLog.actor))
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    ).all()
    result = []
    for entry in rows:
        out = AuditLogOut.model_validate(entry)
        out.actor_name = entry.actor.full_name if entry.actor else None
        result.append(out)
    return result
