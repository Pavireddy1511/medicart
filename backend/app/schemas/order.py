from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import OrderStatus, PaymentMethod
from app.schemas.common import Money, ORMModel


class OrderCreate(BaseModel):
    address_id: int
    payment_method: PaymentMethod
    prescription_id: int | None = None


class OrderCancelRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=255)


class OrderItemOut(ORMModel):
    id: int
    product_id: int | None
    product_name_snapshot: str
    pack_size_snapshot: str | None
    prescription_required: bool
    quantity: int
    price_snapshot: Money
    subtotal: Money


class PaymentOut(ORMModel):
    id: int
    payment_method: str
    transaction_reference: str | None
    payment_status: str
    amount: Money
    created_at: datetime


class ShipmentOut(ORMModel):
    id: int
    tracking_reference: str | None
    shipment_status: str
    updated_at: datetime


class OrderSummary(ORMModel):
    id: int
    order_number: str
    order_status: str
    payment_status: str
    payment_method: str
    order_total: Money
    item_count: int = 0
    created_at: datetime
    delivered_at: datetime | None = None
    items: list[OrderItemOut]


class OrderDetail(OrderSummary):
    subtotal: Money
    delivery_charge: Money
    address_snapshot: dict
    prescription_id: int | None
    cancellation_reason: str | None
    payments: list[PaymentOut]
    shipment: ShipmentOut | None
    updated_at: datetime
    can_cancel: bool = False
    allowed_next_statuses: list[str] = []


class OrderStatusUpdate(BaseModel):
    order_status: OrderStatus
    tracking_reference: str | None = Field(default=None, max_length=40)
    note: str | None = Field(default=None, max_length=255)
