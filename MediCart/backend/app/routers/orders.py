from fastapi import APIRouter, status

from app.core.dependencies import CurrentUser, DbSession, SettingsDep
from app.schemas.order import OrderCancelRequest, OrderCreate, OrderDetail, OrderSummary
from app.services import order_service

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderDetail, status_code=status.HTTP_201_CREATED)
def place_order(data: OrderCreate, user: CurrentUser, db: DbSession, settings: SettingsDep):
    order = order_service.place_order(db, user, data, settings)
    return order_service.to_detail(order)


@router.get("", response_model=list[OrderSummary])
def list_orders(user: CurrentUser, db: DbSession):
    return [order_service.to_summary(o) for o in order_service.list_orders(db, user)]


@router.get("/{order_id}", response_model=OrderDetail)
def get_order(order_id: int, user: CurrentUser, db: DbSession):
    return order_service.to_detail(order_service.get_order(db, user, order_id))


@router.post("/{order_id}/cancel", response_model=OrderDetail)
def cancel_order(order_id: int, data: OrderCancelRequest, user: CurrentUser, db: DbSession):
    return order_service.to_detail(order_service.cancel_order(db, user, order_id, data.reason))
