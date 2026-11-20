from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.dependencies import AdminUser, DbSession
from app.schemas.admin import (
    AdminCategoryOut,
    AdminMedicineOut,
    AdminOrderOut,
    AdminPrescriptionListItem,
    AdminUserOut,
    AdminUserUpdate,
    AuditLogOut,
    CategoryIn,
    CategoryUpdate,
    DashboardOut,
    InventoryUpdate,
    MedicineCreate,
    MedicineUpdate,
    ProductIn,
    ProductUpdate,
)
from app.schemas.common import Message, Page
from app.schemas.order import OrderDetail, OrderStatusUpdate
from app.schemas.prescription import VerificationDetail
from app.services import admin_service, order_service, verification_service
from app.utils.pagination import PageParams, page_count, page_params

router = APIRouter(prefix="/admin", tags=["admin"])
Paging = Annotated[PageParams, Depends(page_params)]


def _page(items, total, params: PageParams, model):
    return Page[model](
        items=items,
        total=total,
        page=params.page,
        page_size=params.page_size,
        pages=page_count(total, params.page_size),
    )


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(_: AdminUser, db: DbSession):
    return admin_service.dashboard(db)


# users
@router.get("/users", response_model=Page[AdminUserOut])
def list_users(
    _: AdminUser,
    db: DbSession,
    params: Paging,
    q: Annotated[str | None, Query(max_length=120)] = None,
    role: Annotated[str | None, Query(max_length=20)] = None,
):
    items, total = admin_service.list_users(db, params, q, role)
    return _page(items, total, params, AdminUserOut)


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def update_user(user_id: int, data: AdminUserUpdate, admin: AdminUser, db: DbSession):
    return admin_service.update_user(db, admin, user_id, data)


# categories
@router.get("/categories", response_model=list[AdminCategoryOut])
def list_categories(_: AdminUser, db: DbSession):
    return admin_service.list_categories(db)


@router.post("/categories", response_model=AdminCategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(data: CategoryIn, admin: AdminUser, db: DbSession):
    return admin_service.create_category(db, admin, data)


@router.put("/categories/{category_id}", response_model=AdminCategoryOut)
def update_category(category_id: int, data: CategoryUpdate, admin: AdminUser, db: DbSession):
    return admin_service.update_category(db, admin, category_id, data)


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: int, admin: AdminUser, db: DbSession):
    admin_service.delete_category(db, admin, category_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# medicines & products
@router.get("/medicines", response_model=Page[AdminMedicineOut])
def list_medicines(
    _: AdminUser,
    db: DbSession,
    params: Paging,
    q: Annotated[str | None, Query(max_length=120)] = None,
    category_id: int | None = None,
    include_inactive: bool = True,
):
    items, total = admin_service.list_medicines(db, params, q, category_id, include_inactive)
    return _page(items, total, params, AdminMedicineOut)


@router.post("/medicines", response_model=AdminMedicineOut, status_code=status.HTTP_201_CREATED)
def create_medicine(data: MedicineCreate, admin: AdminUser, db: DbSession):
    return admin_service.create_medicine(db, admin, data)


@router.get("/medicines/{medicine_id}", response_model=AdminMedicineOut)
def get_medicine(medicine_id: int, _: AdminUser, db: DbSession):
    return admin_service.get_medicine(db, medicine_id)


@router.put("/medicines/{medicine_id}", response_model=AdminMedicineOut)
def update_medicine(medicine_id: int, data: MedicineUpdate, admin: AdminUser, db: DbSession):
    return admin_service.update_medicine(db, admin, medicine_id, data)


@router.delete("/medicines/{medicine_id}", response_model=Message)
def delete_medicine(medicine_id: int, admin: AdminUser, db: DbSession):
    outcome = admin_service.delete_medicine(db, admin, medicine_id)
    if outcome == "deleted":
        return Message(message="Medicine deleted")
    return Message(message="Medicine has past orders, so it was deactivated instead of deleted")


@router.post(
    "/medicines/{medicine_id}/products",
    response_model=AdminMedicineOut,
    status_code=status.HTTP_201_CREATED,
)
def add_product(medicine_id: int, data: ProductIn, admin: AdminUser, db: DbSession):
    return admin_service.add_product(db, admin, medicine_id, data)


@router.put("/products/{product_id}", response_model=AdminMedicineOut)
def update_product(product_id: int, data: ProductUpdate, admin: AdminUser, db: DbSession):
    return admin_service.update_product(db, admin, product_id, data)


@router.put("/products/{product_id}/inventory", response_model=AdminMedicineOut)
def update_inventory(product_id: int, data: InventoryUpdate, admin: AdminUser, db: DbSession):
    return admin_service.update_inventory(db, admin, product_id, data)


# orders
@router.get("/orders", response_model=Page[AdminOrderOut])
def list_orders(
    _: AdminUser,
    db: DbSession,
    params: Paging,
    status_filter: Annotated[str | None, Query(alias="status", max_length=40)] = None,
    q: Annotated[str | None, Query(max_length=120)] = None,
):
    items, total = admin_service.list_orders(db, params, status_filter, q)
    return _page(items, total, params, AdminOrderOut)


@router.get("/orders/{order_id}", response_model=OrderDetail)
def get_order(order_id: int, _: AdminUser, db: DbSession):
    return order_service.to_detail(admin_service.get_order(db, order_id))


@router.patch("/orders/{order_id}/status", response_model=OrderDetail)
def update_order_status(order_id: int, data: OrderStatusUpdate, admin: AdminUser, db: DbSession):
    return order_service.to_detail(admin_service.update_order_status(db, admin, order_id, data))


# prescriptions
@router.get("/prescriptions", response_model=Page[AdminPrescriptionListItem])
def list_prescriptions(
    _: AdminUser,
    db: DbSession,
    params: Paging,
    status_filter: Annotated[str | None, Query(alias="status", max_length=40)] = None,
):
    items, total = admin_service.list_prescriptions(db, params, status_filter)
    return _page(items, total, params, AdminPrescriptionListItem)


@router.get("/prescriptions/{prescription_id}", response_model=VerificationDetail)
def get_prescription(prescription_id: int, _: AdminUser, db: DbSession):
    return verification_service.get_request(db, prescription_id)


# audit
@router.get("/audit-logs", response_model=list[AuditLogOut])
def audit_logs(_: AdminUser, db: DbSession, limit: Annotated[int, Query(ge=1, le=500)] = 100):
    return admin_service.recent_audit_logs(db, limit)
