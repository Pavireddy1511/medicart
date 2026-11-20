from decimal import Decimal
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, PlainSerializer

T = TypeVar("T")

Money = Annotated[
    Decimal,
    PlainSerializer(lambda v: float(round(v, 2)), return_type=float, when_used="json"),
]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


class Message(BaseModel):
    message: str
