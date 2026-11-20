from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import AddressType
from app.schemas.common import ORMModel
from app.utils.validators import normalise_mobile, validate_pincode


class AddressBase(BaseModel):
    recipient_name: str = Field(min_length=2, max_length=120)
    mobile_number: str
    house_building: str = Field(min_length=1, max_length=150)
    street: str = Field(min_length=1, max_length=150)
    landmark: str | None = Field(default=None, max_length=150)
    city: str = Field(min_length=1, max_length=80)
    state: str = Field(min_length=1, max_length=80)
    pincode: str
    address_type: AddressType = AddressType.HOME
    is_default: bool = False

    @field_validator("mobile_number")
    @classmethod
    def _mobile(cls, value: str) -> str:
        return normalise_mobile(value)

    @field_validator("pincode")
    @classmethod
    def _pincode(cls, value: str) -> str:
        return validate_pincode(value)

    @field_validator("landmark", mode="before")
    @classmethod
    def _blank_landmark(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value


class AddressCreate(AddressBase):
    pass


class AddressUpdate(BaseModel):
    recipient_name: str | None = Field(default=None, min_length=2, max_length=120)
    mobile_number: str | None = None
    house_building: str | None = Field(default=None, min_length=1, max_length=150)
    street: str | None = Field(default=None, min_length=1, max_length=150)
    landmark: str | None = Field(default=None, max_length=150)
    city: str | None = Field(default=None, min_length=1, max_length=80)
    state: str | None = Field(default=None, min_length=1, max_length=80)
    pincode: str | None = None
    address_type: AddressType | None = None
    is_default: bool | None = None

    @field_validator("mobile_number")
    @classmethod
    def _mobile(cls, value: str | None) -> str | None:
        return normalise_mobile(value) if value else value

    @field_validator("pincode")
    @classmethod
    def _pincode(cls, value: str | None) -> str | None:
        return validate_pincode(value) if value else value


class AddressOut(ORMModel):
    id: int
    recipient_name: str
    mobile_number: str
    house_building: str
    street: str
    landmark: str | None
    city: str
    state: str
    pincode: str
    address_type: str
    is_default: bool
    created_at: datetime
