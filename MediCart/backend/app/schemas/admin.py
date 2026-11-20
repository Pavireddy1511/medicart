from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.models.enums import UserRole
from app.schemas.auth import UserOut
from app.schemas.common import Money
from app.schemas.order import OrderSummary


class PrescriptionStats(BaseModel):
    total: int
    awaiting_confirmation: int
    pending_verification: int
    approved: int
    rejected: int
    clarification_requested: int
    uncertain_items: int
    ai_fallback: int


class LowStockItem(BaseModel):
    product_id: int
    medicine_name: str
    pack_size: str
    available_quantity: int


class DashboardOut(BaseModel):
    total_customers: int
    total_medicines: int
    total_products: int
    total_orders: int
    pending_orders: int
    completed_orders: int
    cancelled_orders: int
    simulated_revenue: Money
    prescriptions: PrescriptionStats
    recent_orders: list["AdminOrderOut"]
    low_stock: list[LowStockItem]
    orders_by_status: dict[str, int]


class AdminUserOut(UserOut):
    order_count: int = 0
    updated_at: datetime


class AdminUserUpdate(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None


class CategoryIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    slug: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=255)
    icon: str | None = Field(default=None, max_length=40)
    sort_order: int = 0
    is_active: bool = True


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    slug: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=255)
    icon: str | None = Field(default=None, max_length=40)
    sort_order: int | None = None
    is_active: bool | None = None


class ProductIn(BaseModel):
    sku: str | None = Field(default=None, max_length=40)
    pack_size: str = Field(min_length=1, max_length=60)
    mrp: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    is_active: bool = True
    available_quantity: int = Field(default=0, ge=0)
    batch_number: str | None = Field(default=None, max_length=40)
    expiry_date: date | None = None

    @model_validator(mode="after")
    def _price_not_above_mrp(self) -> "ProductIn":
        if self.price > self.mrp:
            raise ValueError("Selling price cannot be higher than MRP")
        return self


class ProductUpdate(BaseModel):
    pack_size: str | None = Field(default=None, min_length=1, max_length=60)
    mrp: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    price: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    is_active: bool | None = None


class InventoryUpdate(BaseModel):
    available_quantity: int = Field(ge=0)
    batch_number: str | None = Field(default=None, max_length=40)
    expiry_date: date | None = None


class MedicineBase(BaseModel):
    medicine_name: str = Field(min_length=2, max_length=150)
    generic_name: str | None = Field(default=None, max_length=150)
    brand_name: str | None = Field(default=None, max_length=120)
    strength: str | None = Field(default=None, max_length=50)
    formulation: str | None = Field(default=None, max_length=50)
    manufacturer: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=5000)
    prescription_required: bool = False
    category_id: int | None = None
    image_url: str | None = Field(default=None, max_length=500)
    is_active: bool = True


class MedicineCreate(MedicineBase):
    products: list[ProductIn] = Field(min_length=1)


class MedicineUpdate(BaseModel):
    medicine_name: str | None = Field(default=None, min_length=2, max_length=150)
    generic_name: str | None = Field(default=None, max_length=150)
    brand_name: str | None = Field(default=None, max_length=120)
    strength: str | None = Field(default=None, max_length=50)
    formulation: str | None = Field(default=None, max_length=50)
    manufacturer: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=5000)
    prescription_required: bool | None = None
    category_id: int | None = None
    image_url: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None


class InventoryOut(BaseModel):
    model_config = {"from_attributes": True}

    available_quantity: int
    batch_number: str | None
    expiry_date: date | None


class AdminProductOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    sku: str
    pack_size: str
    mrp: Money
    price: Money
    discount_percent: int
    is_active: bool
    available_quantity: int
    inventory: InventoryOut | None


class AdminCategoryOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    name: str
    slug: str
    description: str | None
    icon: str | None
    sort_order: int
    is_active: bool
    medicine_count: int = 0


class AdminMedicineOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    medicine_name: str
    generic_name: str | None
    brand_name: str | None
    strength: str | None
    formulation: str | None
    manufacturer: str | None
    description: str | None
    prescription_required: bool
    category_id: int | None
    image_url: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    products: list[AdminProductOut]


class AdminOrderOut(OrderSummary):
    customer_name: str = ""
    customer_mobile: str = ""
    allowed_next_statuses: list[str] = []


class AdminPrescriptionListItem(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    processing_status: str
    document_type: str
    ai_review_status: str
    ocr_engine: str | None
    ocr_confidence: float | None
    user_confirmation_status: str
    pharmacist_verification_status: str
    created_at: datetime
    item_count: int = 0
    uncertain_item_count: int = 0
    customer_name: str = ""


class AuditLogOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    actor_id: int | None
    actor_name: str | None = None
    action: str
    target_type: str
    target_id: int | None
    meta: dict | None
    created_at: datetime
