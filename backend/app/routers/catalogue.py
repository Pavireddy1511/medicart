from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.dependencies import DbSession
from app.schemas.catalogue import (
    CategoryOut,
    HomeFeedOut,
    MedicineDetail,
    MedicineSearchParams,
    MedicineSummary,
    ProductOut,
    medicine_search_params,
)
from app.schemas.common import Page
from app.services import catalogue_service
from app.utils.pagination import page_count

router = APIRouter(tags=["catalogue"])

SearchParams = Annotated[MedicineSearchParams, Depends(medicine_search_params)]


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: DbSession):
    return catalogue_service.list_categories(db)


@router.get("/home", response_model=HomeFeedOut)
def home_feed(db: DbSession):
    return catalogue_service.home_feed(db)


def _search(db, params: MedicineSearchParams) -> Page[MedicineSummary]:
    items, total = catalogue_service.search_medicines(db, params)
    return Page[MedicineSummary](
        items=[MedicineSummary.model_validate(m) for m in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
        pages=page_count(total, params.page_size),
    )


@router.get("/medicines", response_model=Page[MedicineSummary])
def list_medicines(db: DbSession, params: SearchParams):
    return _search(db, params)


@router.get("/medicines/search", response_model=Page[MedicineSummary])
def search_medicines(db: DbSession, params: SearchParams):
    return _search(db, params)


@router.get("/medicines/{medicine_id}", response_model=MedicineDetail)
def get_medicine(medicine_id: int, db: DbSession):
    return catalogue_service.get_medicine(db, medicine_id)


@router.get("/products/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: DbSession):
    return catalogue_service.get_product(db, product_id)
