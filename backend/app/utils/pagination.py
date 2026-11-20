import math
from typing import Annotated

from fastapi import Query
from pydantic import BaseModel
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session


class PageParams(BaseModel):
    page: int = 1
    page_size: int = 20

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def page_params(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PageParams:
    return PageParams(page=page, page_size=page_size)


def paginate(db: Session, stmt: Select, params: PageParams) -> tuple[list, int]:
    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.offset(params.offset).limit(params.page_size)).unique().all()
    return list(rows), total


def page_count(total: int, page_size: int) -> int:
    return max(1, math.ceil(total / page_size)) if page_size else 1
