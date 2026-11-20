from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.address import Address
from app.models.user import User
from app.schemas.address import AddressCreate, AddressUpdate

MAX_ADDRESSES = 10


def list_addresses(db: Session, user: User) -> list[Address]:
    return list(
        db.scalars(
            select(Address)
            .where(Address.user_id == user.id)
            .order_by(Address.is_default.desc(), Address.created_at.desc())
        ).all()
    )


def get_address(db: Session, user: User, address_id: int) -> Address:
    address = db.scalar(select(Address).where(Address.id == address_id, Address.user_id == user.id))
    if address is None:
        raise NotFoundError("Address not found")
    return address


def _clear_default(db: Session, user: User, except_id: int | None = None) -> None:
    stmt = update(Address).where(Address.user_id == user.id).values(is_default=False)
    if except_id is not None:
        stmt = stmt.where(Address.id != except_id)
    db.execute(stmt)


def create_address(db: Session, user: User, data: AddressCreate) -> Address:
    existing = list_addresses(db, user)
    if len(existing) >= MAX_ADDRESSES:
        raise NotFoundError(
            f"You can save up to {MAX_ADDRESSES} addresses", code="limit_reached", status_code=400
        )
    make_default = data.is_default or not existing
    address = Address(user_id=user.id, **data.model_dump(exclude={"is_default"}))
    address.address_type = data.address_type.value
    address.is_default = make_default
    db.add(address)
    db.flush()
    if make_default:
        _clear_default(db, user, except_id=address.id)
    db.commit()
    db.refresh(address)
    return address


def update_address(db: Session, user: User, address_id: int, data: AddressUpdate) -> Address:
    address = get_address(db, user, address_id)
    changes = data.model_dump(exclude_unset=True)
    make_default = changes.pop("is_default", None)
    for field, value in changes.items():
        setattr(address, field, value.value if hasattr(value, "value") else value)
    if make_default:
        _clear_default(db, user, except_id=address.id)
        address.is_default = True
    db.commit()
    db.refresh(address)
    return address


def delete_address(db: Session, user: User, address_id: int) -> None:
    address = get_address(db, user, address_id)
    was_default = address.is_default
    db.delete(address)
    db.flush()
    if was_default:
        replacement = db.scalar(
            select(Address).where(Address.user_id == user.id).order_by(Address.created_at.desc()).limit(1)
        )
        if replacement:
            replacement.is_default = True
    db.commit()


def set_default(db: Session, user: User, address_id: int) -> Address:
    address = get_address(db, user, address_id)
    _clear_default(db, user, except_id=address.id)
    address.is_default = True
    db.commit()
    db.refresh(address)
    return address
