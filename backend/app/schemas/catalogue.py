from datetime import datetime
from typing import Annotated, Literal

from fastapi import Query
from pydantic import BaseModel, computed_field, field_validator

from app.schemas.common import Money, ORMModel


def only_active_products(value):
    """ORM relationships hold every product; customers should only see active ones."""
    if isinstance(value, list):
        return [p for p in value if getattr(p, "is_active", True)]
    return value


SortOption = Literal["relevance", "price_asc", "price_desc", "name_asc", "name_desc", "newest"]


class CategoryOut(ORMModel):
    id: int
    name: str
    slug: str
    description: str | None
    icon: str | None
    sort_order: int
    medicine_count: int = 0


class ProductOut(ORMModel):
    id: int
    sku: str
    pack_size: str
    mrp: Money
    price: Money
    discount_percent: int
    is_active: bool
    available_quantity: int

    @computed_field
    @property
    def in_stock(self) -> bool:
        return self.is_active and self.available_quantity > 0


class MedicineSummary(ORMModel):
    id: int
    medicine_name: str
    generic_name: str | None
    brand_name: str | None
    strength: str | None
    formulation: str | None
    manufacturer: str | None
    prescription_required: bool
    composition: str | None = None
    image_url: str | None
    is_active: bool
    category: CategoryOut | None
    products: list[ProductOut]

    _active_products = field_validator("products", mode="before")(only_active_products)


class MedicineDetail(MedicineSummary):
    description: str | None
    created_at: datetime


class MedicineSearchParams(BaseModel):
    q: str | None = None
    category: str | None = None
    min_price: float | None = None
    max_price: float | None = None
    in_stock: bool | None = None
    prescription_required: bool | None = None
    sort: SortOption = "relevance"
    page: int = 1
    page_size: int = 20


def medicine_search_params(
    q: Annotated[str | None, Query(max_length=120)] = None,
    category: Annotated[str | None, Query(max_length=80)] = None,
    min_price: Annotated[float | None, Query(ge=0)] = None,
    max_price: Annotated[float | None, Query(ge=0)] = None,
    in_stock: bool | None = None,
    prescription_required: bool | None = None,
    sort: SortOption = "relevance",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=60)] = 20,
) -> MedicineSearchParams:
    return MedicineSearchParams(
        q=q.strip() if q else None,
        category=category,
        min_price=min_price,
        max_price=max_price,
        in_stock=in_stock,
        prescription_required=prescription_required,
        sort=sort,
        page=page,
        page_size=page_size,
    )


class HomeFeedOut(BaseModel):
    categories: list[CategoryOut]
    featured: list[MedicineSummary]
    deals: list[MedicineSummary]
    popular: list[MedicineSummary]
