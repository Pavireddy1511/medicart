from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.schemas.common import ORMModel
from app.utils.validators import normalise_mobile, validate_password


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    mobile_number: str
    email: EmailStr | None = None
    password: str
    confirm_password: str

    @field_validator("full_name")
    @classmethod
    def _clean_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if len(value) < 2:
            raise ValueError("Enter your full name")
        return value

    @field_validator("mobile_number")
    @classmethod
    def _mobile(cls, value: str) -> str:
        return normalise_mobile(value)

    @field_validator("email", mode="before")
    @classmethod
    def _blank_email(cls, value):
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        return value.strip().lower()

    @field_validator("password")
    @classmethod
    def _password(cls, value: str) -> str:
        return validate_password(value)

    @model_validator(mode="after")
    def _passwords_match(self) -> "RegisterRequest":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class LoginRequest(BaseModel):
    mobile_number: str
    password: str = Field(min_length=1, max_length=128)

    @field_validator("mobile_number")
    @classmethod
    def _mobile(cls, value: str) -> str:
        return normalise_mobile(value)


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(ORMModel):
    id: int
    full_name: str
    mobile_number: str
    email: str | None
    role: str
    is_active: bool
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    email: EmailStr | None = None

    @field_validator("email", mode="before")
    @classmethod
    def _blank_email(cls, value):
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        return value.strip().lower()


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str

    @field_validator("new_password")
    @classmethod
    def _password(cls, value: str) -> str:
        return validate_password(value)

    @model_validator(mode="after")
    def _passwords_match(self) -> "ChangePasswordRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self
