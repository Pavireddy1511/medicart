from pydantic import BaseModel, Field

from app.schemas.common import Money


class CartItemAdd(BaseModel):
    product_id: int
    quantity: int = Field(default=1, ge=1, le=20)


class CartItemUpdate(BaseModel):
    quantity: int = Field(ge=1, le=20)


class CartProductOut(BaseModel):
    id: int
    sku: str
    pack_size: str
    mrp: Money
    price: Money
    available_quantity: int
    is_active: bool
    medicine_id: int
    medicine_name: str
    brand_name: str | None
    strength: str | None
    formulation: str | None
    prescription_required: bool
    image_url: str | None


class CartItemOut(BaseModel):
    id: int
    product_id: int
    quantity: int
    price_snapshot: Money
    unit_price: Money
    line_total: Money
    price_changed: bool
    in_stock: bool
    product: CartProductOut


class CartOut(BaseModel):
    id: int
    items: list[CartItemOut]
    item_count: int
    subtotal: Money
    delivery_charge: Money
    total: Money
    free_delivery_above: Money
    requires_prescription: bool
    has_unavailable_items: bool
