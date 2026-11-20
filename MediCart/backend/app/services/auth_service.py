from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import ConflictError, ForbiddenError, UnauthorizedError
from app.core.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    password_needs_rehash,
    verify_password,
)
from app.models.cart import Cart
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.auth import ChangePasswordRequest, ProfileUpdate, RegisterRequest, TokenResponse
from app.services import audit_service

INVALID_CREDENTIALS = "Incorrect mobile number or password"


def get_by_mobile(db: Session, mobile_number: str) -> User | None:
    return db.scalar(select(User).where(User.mobile_number == mobile_number))


def register(db: Session, data: RegisterRequest, role: UserRole = UserRole.CUSTOMER) -> User:
    if get_by_mobile(db, data.mobile_number):
        raise ConflictError("An account with this mobile number already exists", code="mobile_taken")
    if data.email and db.scalar(select(User.id).where(User.email == data.email)):
        raise ConflictError("An account with this email already exists", code="email_taken")

    user = User(
        full_name=data.full_name,
        mobile_number=data.mobile_number,
        email=data.email,
        password_hash=hash_password(data.password),
        role=role.value,
        is_active=True,
    )
    user.cart = Cart()
    db.add(user)
    db.flush()
    audit_service.record(
        db, actor_id=user.id, action="user.registered", target_type="user", target_id=user.id
    )
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, mobile_number: str, password: str) -> User:
    user = get_by_mobile(db, mobile_number)
    if user is None or not verify_password(password, user.password_hash):
        raise UnauthorizedError(INVALID_CREDENTIALS, code="invalid_credentials")
    if not user.is_active:
        raise ForbiddenError("This account has been deactivated. Contact support.")
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
        db.commit()
    return user


def build_token_response(user: User) -> TokenResponse:
    settings = get_settings()
    return TokenResponse(
        access_token=create_access_token(user.id, user.role),
        refresh_token=create_refresh_token(user.id),
        expires_in=settings.access_token_expire_minutes * 60,
        user=user,
    )


def refresh_tokens(db: Session, refresh_token: str) -> TokenResponse:
    try:
        payload = decode_token(refresh_token, "refresh")
    except TokenError as exc:
        raise UnauthorizedError("Session expired. Please sign in again.") from exc
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise UnauthorizedError("Session expired. Please sign in again.")
    return build_token_response(user)


def update_profile(db: Session, user: User, data: ProfileUpdate) -> User:
    if data.full_name is not None:
        user.full_name = " ".join(data.full_name.split())
    if "email" in data.model_fields_set:
        if data.email and data.email != user.email:
            taken = db.scalar(select(User.id).where(User.email == data.email, User.id != user.id))
            if taken:
                raise ConflictError("An account with this email already exists", code="email_taken")
        user.email = data.email
    db.commit()
    db.refresh(user)
    return user


def change_password(db: Session, user: User, data: ChangePasswordRequest) -> None:
    if not verify_password(data.current_password, user.password_hash):
        raise UnauthorizedError("Current password is incorrect", code="invalid_credentials")
    user.password_hash = hash_password(data.new_password)
    audit_service.record(
        db, actor_id=user.id, action="user.password_changed", target_type="user", target_id=user.id
    )
    db.commit()
