import secrets
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings, get_settings
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.models.catalogue import Inventory, Product
from app.models.enums import (
    CUSTOMER_CANCELLABLE,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    ShipmentStatus,
    UserConfirmationStatus,
    VerificationStatus,
    allowed_transitions,
)
from app.models.order import Order, OrderItem, Payment, Shipment
from app.models.prescription import Prescription
from app.models.user import User
from app.schemas.order import OrderCreate, OrderDetail, OrderSummary
from app.services import address_service, audit_service, cart_service


def _order_options(stmt):
    return stmt.options(
        selectinload(Order.items),
        selectinload(Order.payments),
        selectinload(Order.shipment),
    )


def _lock_inventory(db: Session, product_ids: list[int]) -> dict[int, Inventory]:
    stmt = select(Inventory).where(Inventory.product_id.in_(product_ids))
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        stmt = stmt.with_for_update()
    return {inv.product_id: inv for inv in db.scalars(stmt).all()}


def _validate_prescription_for_order(
    db: Session, user: User, prescription_id: int | None, rx_medicine_ids: set[int]
) -> tuple[Prescription | None, OrderStatus]:
    if not rx_medicine_ids:
        return None, OrderStatus.PLACED
    if prescription_id is None:
        prescription_id = _covering_prescription_id(db, user, rx_medicine_ids)
    if prescription_id is None:
        raise ValidationError(
            "Your cart contains prescription medicines. Upload and confirm a prescription first.",
            code="prescription_required",
        )
    prescription = db.scalar(
        select(Prescription)
        .where(Prescription.id == prescription_id, Prescription.user_id == user.id)
        .options(selectinload(Prescription.items))
    )
    if prescription is None:
        raise NotFoundError("Prescription not found")
    if prescription.user_confirmation_status != UserConfirmationStatus.CONFIRMED.value:
        raise ValidationError(
            "Please review and confirm the prescription before ordering.",
            code="prescription_unconfirmed",
        )
    if prescription.pharmacist_verification_status == VerificationStatus.REJECTED.value:
        raise ValidationError(
            "This prescription was rejected by the pharmacist and cannot be used.",
            code="prescription_rejected",
        )
    covered = {
        item.matched_medicine_id
        for item in prescription.items
        if item.included and item.matched_medicine_id is not None
    }
    missing = rx_medicine_ids - covered
    if missing:
        raise ValidationError(
            "Some prescription medicines in your cart are not on the selected prescription.",
            code="prescription_mismatch",
            details={"medicine_ids": sorted(missing)},
        )
    status = prescription.pharmacist_verification_status
    if status == VerificationStatus.APPROVED.value:
        return prescription, OrderStatus.VERIFIED
    # The order waits for the pharmacist when approval is mandatory, or when the customer asked
    # for a review that is still open. Otherwise it goes straight to fulfilment.
    review_open = status in (
        VerificationStatus.PENDING.value,
        VerificationStatus.CLARIFICATION_REQUESTED.value,
    )
    if get_settings().require_pharmacist_approval or review_open:
        return prescription, OrderStatus.VERIFICATION_PENDING
    return prescription, OrderStatus.PLACED


def _covering_prescription_id(db: Session, user: User, rx_medicine_ids: set[int]) -> int | None:
    """Newest confirmed, non-rejected prescription of this user that lists every Rx item."""
    candidates = db.scalars(
        select(Prescription)
        .where(
            Prescription.user_id == user.id,
            Prescription.user_confirmation_status == UserConfirmationStatus.CONFIRMED.value,
            Prescription.pharmacist_verification_status != VerificationStatus.REJECTED.value,
        )
        .options(selectinload(Prescription.items))
        .order_by(Prescription.created_at.desc(), Prescription.id.desc())
        .limit(20)
    ).all()
    for prescription in candidates:
        covered = {i.matched_medicine_id for i in prescription.items if i.included and i.matched_medicine_id}
        if rx_medicine_ids <= covered:
            return prescription.id
    return None


def place_order(db: Session, user: User, data: OrderCreate, settings: Settings | None = None) -> Order:
    settings = settings or get_settings()
    cart = cart_service.get_cart(db, user)
    if not cart.items:
        raise ValidationError("Your cart is empty", code="cart_empty")

    address = address_service.get_address(db, user, data.address_id)
    inventory = _lock_inventory(db, [item.product_id for item in cart.items])

    subtotal = Decimal("0.00")
    order_items: list[OrderItem] = []
    rx_medicine_ids: set[int] = set()
    for item in cart.items:
        product: Product = item.product
        medicine = product.medicine
        if not product.is_active or not medicine.is_active:
            raise ConflictError(
                f"{medicine.medicine_name} is no longer available",
                code="product_unavailable",
                details={"product_id": product.id},
            )
        stock = inventory.get(product.id)
        available = stock.available_quantity if stock else 0
        if item.quantity > available:
            raise ConflictError(
                f"Only {available} unit(s) of {medicine.medicine_name} are in stock",
                code="insufficient_stock",
                details={"product_id": product.id, "available_quantity": available},
            )
        unit_price = Decimal(product.price)
        line_total = unit_price * item.quantity
        subtotal += line_total
        if medicine.prescription_required:
            rx_medicine_ids.add(medicine.id)
        order_items.append(
            OrderItem(
                product_id=product.id,
                product_name_snapshot=f"{medicine.medicine_name} {medicine.strength or ''}".strip(),
                pack_size_snapshot=product.pack_size,
                prescription_required=medicine.prescription_required,
                quantity=item.quantity,
                price_snapshot=unit_price,
                subtotal=line_total,
            )
        )

    prescription, status = _validate_prescription_for_order(db, user, data.prescription_id, rx_medicine_ids)

    delivery = cart_service.delivery_charge_for(subtotal, settings)
    total = subtotal + delivery

    if data.payment_method == PaymentMethod.COD:
        payment_status = PaymentStatus.COD_PENDING
        reference = None
    else:
        payment_status = PaymentStatus.PAID
        reference = f"SIM-{secrets.token_hex(6).upper()}"

    order = Order(
        order_number=f"MC-{secrets.token_hex(2).upper()}",
        user_id=user.id,
        address_id=address.id,
        address_snapshot=address.as_snapshot(),
        prescription_id=prescription.id if prescription else None,
        subtotal=subtotal,
        delivery_charge=delivery,
        order_total=total,
        payment_method=data.payment_method.value,
        payment_status=payment_status.value,
        order_status=status.value,
    )
    order.items = order_items
    order.payments = [
        Payment(
            payment_method=data.payment_method.value,
            transaction_reference=reference,
            payment_status=payment_status.value,
            amount=total,
        )
    ]
    order.shipment = Shipment(shipment_status=ShipmentStatus.PENDING.value)
    db.add(order)
    db.flush()
    order.order_number = f"MC{datetime.now(UTC):%y%m%d}{order.id:05d}"

    for item in cart.items:
        inventory[item.product_id].available_quantity -= item.quantity

    cart_service.clear_cart(db, cart)
    audit_service.record(
        db,
        actor_id=user.id,
        action="order.placed",
        target_type="order",
        target_id=order.id,
        meta={"total": str(total), "status": status.value, "payment": data.payment_method.value},
    )
    db.commit()
    return get_order(db, user, order.id)


def list_orders(db: Session, user: User) -> list[Order]:
    stmt = _order_options(
        select(Order).where(Order.user_id == user.id).order_by(Order.created_at.desc(), Order.id.desc())
    )
    return list(db.scalars(stmt).all())


def get_order(db: Session, user: User | None, order_id: int) -> Order:
    stmt = _order_options(select(Order).where(Order.id == order_id))
    if user is not None:
        stmt = stmt.where(Order.user_id == user.id)
    order = db.scalar(stmt)
    if order is None:
        raise NotFoundError("Order not found")
    return order


def _restock(db: Session, order: Order) -> None:
    product_ids = [i.product_id for i in order.items if i.product_id is not None]
    if not product_ids:
        return
    inventory = _lock_inventory(db, product_ids)
    for item in order.items:
        stock = inventory.get(item.product_id)
        if stock:
            stock.available_quantity += item.quantity


def _apply_cancellation(db: Session, order: Order, reason: str | None) -> None:
    order.order_status = OrderStatus.CANCELLED.value
    order.cancellation_reason = reason
    if order.payment_status == PaymentStatus.PAID.value:
        order.payment_status = PaymentStatus.REFUNDED.value
        order.payments.append(
            Payment(
                payment_method=order.payment_method,
                transaction_reference=f"REF-{secrets.token_hex(6).upper()}",
                payment_status=PaymentStatus.REFUNDED.value,
                amount=order.order_total,
            )
        )
    else:
        order.payment_status = PaymentStatus.CANCELLED.value
    if order.shipment:
        order.shipment.shipment_status = ShipmentStatus.CANCELLED.value
    _restock(db, order)


def cancel_order(db: Session, user: User, order_id: int, reason: str | None) -> Order:
    order = get_order(db, user, order_id)
    if OrderStatus(order.order_status) not in CUSTOMER_CANCELLABLE:
        raise ConflictError("This order can no longer be cancelled", code="cannot_cancel")
    _apply_cancellation(db, order, reason or "Cancelled by customer")
    audit_service.record(
        db, actor_id=user.id, action="order.cancelled", target_type="order", target_id=order.id
    )
    db.commit()
    return get_order(db, user, order.id)


def transition_order(
    db: Session,
    order: Order,
    new_status: OrderStatus,
    *,
    actor: User,
    tracking_reference: str | None = None,
    note: str | None = None,
) -> Order:
    current = OrderStatus(order.order_status)
    allowed = allowed_transitions(current)
    if new_status not in allowed:
        raise ConflictError(
            f"Cannot move an order from '{current.value}' to '{new_status.value}'",
            code="invalid_transition",
            details={"allowed": [s.value for s in allowed]},
        )
    if new_status == OrderStatus.CANCELLED:
        _apply_cancellation(db, order, note or "Cancelled by MediCart")
    else:
        order.order_status = new_status.value
        shipment = order.shipment or Shipment(order_id=order.id)
        if new_status == OrderStatus.PACKED:
            shipment.shipment_status = ShipmentStatus.PACKED.value
        elif new_status == OrderStatus.SHIPPED:
            shipment.shipment_status = ShipmentStatus.IN_TRANSIT.value
            shipment.tracking_reference = tracking_reference or f"TRK{secrets.randbelow(10**10):010d}"
        elif new_status == OrderStatus.DELIVERED:
            shipment.shipment_status = ShipmentStatus.DELIVERED.value
            shipment.tracking_reference = (
                shipment.tracking_reference or tracking_reference or f"TRK{secrets.randbelow(10**10):010d}"
            )
            if order.payment_status == PaymentStatus.COD_PENDING.value:
                order.payment_status = PaymentStatus.PAID.value
                order.payments.append(
                    Payment(
                        payment_method=order.payment_method,
                        transaction_reference=f"COD-{secrets.token_hex(6).upper()}",
                        payment_status=PaymentStatus.PAID.value,
                        amount=order.order_total,
                    )
                )
        order.shipment = shipment
    audit_service.record(
        db,
        actor_id=actor.id,
        action="order.status_changed",
        target_type="order",
        target_id=order.id,
        meta={"from": current.value, "to": new_status.value, "note": note},
    )
    db.commit()
    return get_order(db, None, order.id)


def apply_prescription_decision(db: Session, prescription: Prescription, approved: bool) -> int:
    """Move orders waiting on this prescription forward (or cancel them). Returns count."""
    orders = db.scalars(
        _order_options(
            select(Order).where(
                Order.prescription_id == prescription.id,
                Order.order_status == OrderStatus.VERIFICATION_PENDING.value,
            )
        )
    ).all()
    for order in orders:
        if approved:
            order.order_status = OrderStatus.VERIFIED.value
        else:
            _apply_cancellation(db, order, "Prescription rejected by pharmacist")
    return len(orders)


def delivered_at(order: Order):
    if order.order_status == OrderStatus.DELIVERED.value and order.shipment is not None:
        return order.shipment.updated_at
    return None


def to_summary(order: Order) -> OrderSummary:
    data = OrderSummary.model_validate(order)
    data.item_count = sum(i.quantity for i in order.items)
    data.delivered_at = delivered_at(order)
    return data


def to_detail(order: Order) -> OrderDetail:
    data = OrderDetail.model_validate(order)
    data.item_count = sum(i.quantity for i in order.items)
    data.delivered_at = delivered_at(order)
    data.can_cancel = OrderStatus(order.order_status) in CUSTOMER_CANCELLABLE
    data.allowed_next_statuses = [s.value for s in allowed_transitions(OrderStatus(order.order_status))]
    return data


def ensure_owner_or_staff(order: Order, user: User) -> None:
    if order.user_id != user.id and user.role not in ("admin", "pharmacist"):
        raise ForbiddenError("You cannot view this order")
