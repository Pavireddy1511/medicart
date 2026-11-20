from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base
from app.models.address import Address
from app.models.base import TimestampMixin
from app.models.catalogue import Product
from app.models.enums import OrderStatus, PaymentStatus, ShipmentStatus
from app.models.prescription import Prescription
from app.models.user import User


class Order(TimestampMixin, Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_number: Mapped[str] = mapped_column(String(24), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    address_id: Mapped[int | None] = mapped_column(
        ForeignKey("addresses.id", ondelete="SET NULL"), nullable=True
    )
    address_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    prescription_id: Mapped[int | None] = mapped_column(
        ForeignKey("prescriptions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    delivery_charge: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    order_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(20), nullable=False)
    payment_status: Mapped[str] = mapped_column(
        String(20), default=PaymentStatus.PENDING.value, nullable=False
    )
    order_status: Mapped[str] = mapped_column(
        String(40), default=OrderStatus.PLACED.value, nullable=False, index=True
    )
    cancellation_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user: Mapped[User] = relationship()
    address: Mapped[Address | None] = relationship()
    prescription: Mapped[Prescription | None] = relationship()
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="OrderItem.id"
    )
    payments: Mapped[list["Payment"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="Payment.id"
    )
    shipment: Mapped["Shipment | None"] = relationship(
        back_populates="order", uselist=False, cascade="all, delete-orphan"
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), index=True, nullable=False
    )
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    product_name_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    pack_size_snapshot: Mapped[str | None] = mapped_column(String(60), nullable=True)
    prescription_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price_snapshot: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    order: Mapped[Order] = relationship(back_populates="items")
    product: Mapped[Product | None] = relationship()


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), index=True, nullable=False
    )
    payment_method: Mapped[str] = mapped_column(String(20), nullable=False)
    transaction_reference: Mapped[str | None] = mapped_column(
        String(60), unique=True, nullable=True
    )
    payment_status: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    order: Mapped[Order] = relationship(back_populates="payments")


class Shipment(Base):
    __tablename__ = "shipments"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    tracking_reference: Mapped[str | None] = mapped_column(String(40), nullable=True)
    shipment_status: Mapped[str] = mapped_column(
        String(30), default=ShipmentStatus.PENDING.value, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    order: Mapped[Order] = relationship(back_populates="shipment")
