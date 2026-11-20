from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    event,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base
from app.models.base import TimestampMixin


class MedicineCategory(TimestampMixin, Base):
    __tablename__ = "medicine_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    icon: Mapped[str | None] = mapped_column(String(40), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    medicines: Mapped[list["Medicine"]] = relationship(back_populates="category")


class Medicine(TimestampMixin, Base):
    __tablename__ = "medicines"
    __table_args__ = (
        Index("ix_medicines_medicine_name", "medicine_name"),
        Index("ix_medicines_generic_name", "generic_name"),
        Index("ix_medicines_brand_name", "brand_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    medicine_name: Mapped[str] = mapped_column(String(150), nullable=False)
    generic_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    brand_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    strength: Mapped[str | None] = mapped_column(String(50), nullable=True)
    formulation: Mapped[str | None] = mapped_column(String(50), nullable=True)
    manufacturer: Mapped[str | None] = mapped_column(String(120), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    prescription_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("medicine_categories.id", ondelete="SET NULL"), index=True, nullable=True
    )
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # matching helpers: normalised name, salts as written, normalised salts joined by "|"
    search_name: Mapped[str | None] = mapped_column(String(150), index=True, nullable=True)
    composition: Mapped[str | None] = mapped_column(String(300), nullable=True)
    composition_key: Mapped[str | None] = mapped_column(String(300), index=True, nullable=True)
    therapeutic_class: Mapped[str | None] = mapped_column(String(80), nullable=True)
    # ranking hint among equivalent brands (products per manufacturer from the import, or sales)
    popularity: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False, index=True)

    category: Mapped[MedicineCategory | None] = relationship(back_populates="medicines")
    products: Mapped[list["Product"]] = relationship(
        back_populates="medicine", cascade="all, delete-orphan", order_by="Product.price"
    )


class Product(TimestampMixin, Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    medicine_id: Mapped[int] = mapped_column(
        ForeignKey("medicines.id", ondelete="CASCADE"), index=True, nullable=False
    )
    sku: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    pack_size: Mapped[str] = mapped_column(String(60), nullable=False)
    mrp: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    medicine: Mapped[Medicine] = relationship(back_populates="products")
    inventory: Mapped["Inventory | None"] = relationship(
        back_populates="product", uselist=False, cascade="all, delete-orphan"
    )

    @property
    def available_quantity(self) -> int:
        return self.inventory.available_quantity if self.inventory else 0

    @property
    def discount_percent(self) -> int:
        if self.mrp and self.mrp > self.price:
            return int(round((self.mrp - self.price) / self.mrp * 100))
        return 0


class Inventory(Base):
    __tablename__ = "inventory"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    available_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    batch_number: Mapped[str | None] = mapped_column(String(40), nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    product: Mapped[Product] = relationship(back_populates="inventory")


@event.listens_for(Medicine, "before_insert")
@event.listens_for(Medicine, "before_update")
def _fill_search_fields(_mapper, _connection, target: Medicine) -> None:
    """Keep the normalised matching columns in step with the editable name fields."""
    from app.utils.text import normalise_name

    target.search_name = normalise_name(target.medicine_name)[:150] or None
    if target.generic_name and not target.composition_key:
        salts = [normalise_name(p) for p in target.generic_name.split("+") if p.strip()]
        target.composition_key = "|".join(s for s in salts if s)[:300] or None
