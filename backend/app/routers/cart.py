from fastapi import APIRouter, status

from app.core.dependencies import CurrentUser, DbSession, SettingsDep
from app.schemas.cart import CartItemAdd, CartItemUpdate, CartOut
from app.services import cart_service

router = APIRouter(prefix="/cart", tags=["cart"])


@router.get("", response_model=CartOut)
def get_cart(user: CurrentUser, db: DbSession, settings: SettingsDep):
    return cart_service.build_cart_out(cart_service.get_cart(db, user), settings)


@router.post("/items", response_model=CartOut, status_code=status.HTTP_201_CREATED)
def add_item(data: CartItemAdd, user: CurrentUser, db: DbSession, settings: SettingsDep):
    cart = cart_service.add_item(db, user, data.product_id, data.quantity)
    return cart_service.build_cart_out(cart, settings)


@router.put("/items/{item_id}", response_model=CartOut)
def update_item(item_id: int, data: CartItemUpdate, user: CurrentUser, db: DbSession, settings: SettingsDep):
    cart = cart_service.update_item(db, user, item_id, data.quantity)
    return cart_service.build_cart_out(cart, settings)


@router.delete("/items/{item_id}", response_model=CartOut)
def remove_item(item_id: int, user: CurrentUser, db: DbSession, settings: SettingsDep):
    cart = cart_service.remove_item(db, user, item_id)
    return cart_service.build_cart_out(cart, settings)


@router.delete("", response_model=CartOut)
def clear_cart(user: CurrentUser, db: DbSession, settings: SettingsDep):
    cart = cart_service.get_cart(db, user)
    cart_service.clear_cart(db, cart)
    db.commit()
    return cart_service.build_cart_out(cart_service.get_cart(db, user), settings)
