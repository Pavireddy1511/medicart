from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings, get_settings
from app.core.exceptions import ConflictError, NotFoundError
from app.models.cart import Cart, CartItem
from app.models.catalogue import Product
from app.models.user import User
from app.schemas.cart import CartItemOut, CartOut, CartProductOut
from app.services.catalogue_service import get_product


def _cart_query(user_id: int):
    return (
        select(Cart)
        .where(Cart.user_id == user_id)
        .options(
            selectinload(Cart.items)
            .selectinload(CartItem.product)
            .options(selectinload(Product.inventory), selectinload(Product.medicine))
        )
    )


def get_cart(db: Session, user: User) -> Cart:
    cart = db.scalar(_cart_query(user.id))
    if cart is None:
        cart = Cart(user_id=user.id)
        db.add(cart)
        db.commit()
        cart = db.scalar(_cart_query(user.id))
    return cart


def _reload(db: Session, user: User) -> Cart:
    db.commit()
    db.expire_all()
    return get_cart(db, user)


def _check_stock(product: Product, quantity: int) -> None:
    available = product.available_quantity
    if quantity > available:
        raise ConflictError(
            f"Only {available} unit(s) of {product.medicine.medicine_name} are available",
            code="insufficient_stock",
            details={"product_id": product.id, "available_quantity": available},
        )


def add_item(db: Session, user: User, product_id: int, quantity: int) -> Cart:
    cart = get_cart(db, user)
    product = get_product(db, product_id)
    existing = next((i for i in cart.items if i.product_id == product.id), None)
    new_quantity = quantity + (existing.quantity if existing else 0)
    if new_quantity > 20:
        raise ConflictError("You can order at most 20 units of an item", code="quantity_limit")
    _check_stock(product, new_quantity)
    if existing:
        existing.quantity = new_quantity
        existing.price_snapshot = product.price
    else:
        db.add(
            CartItem(
                cart_id=cart.id,
                product_id=product.id,
                quantity=quantity,
                price_snapshot=product.price,
            )
        )
    return _reload(db, user)


def update_item(db: Session, user: User, item_id: int, quantity: int) -> Cart:
    cart = get_cart(db, user)
    item = next((i for i in cart.items if i.id == item_id), None)
    if item is None:
        raise NotFoundError("Cart item not found")
    _check_stock(item.product, quantity)
    item.quantity = quantity
    item.price_snapshot = item.product.price
    return _reload(db, user)


def remove_item(db: Session, user: User, item_id: int) -> Cart:
    cart = get_cart(db, user)
    item = next((i for i in cart.items if i.id == item_id), None)
    if item is None:
        raise NotFoundError("Cart item not found")
    db.delete(item)
    return _reload(db, user)


def clear_cart(db: Session, cart: Cart) -> None:
    for item in list(cart.items):
        db.delete(item)
    db.flush()


def delivery_charge_for(subtotal: Decimal, settings: Settings) -> Decimal:
    if subtotal <= 0:
        return Decimal("0.00")
    return Decimal("0.00") if subtotal >= settings.delivery_free_above else settings.delivery_charge


def build_cart_out(cart: Cart, settings: Settings | None = None) -> CartOut:
    settings = settings or get_settings()
    items: list[CartItemOut] = []
    subtotal = Decimal("0.00")
    requires_rx = False
    unavailable = False

    for item in cart.items:
        product = item.product
        medicine = product.medicine
        unit_price = Decimal(product.price)
        line_total = unit_price * item.quantity
        in_stock = product.is_active and medicine.is_active and product.available_quantity >= item.quantity
        unavailable = unavailable or not in_stock
        requires_rx = requires_rx or medicine.prescription_required
        subtotal += line_total
        items.append(
            CartItemOut(
                id=item.id,
                product_id=product.id,
                quantity=item.quantity,
                price_snapshot=Decimal(item.price_snapshot),
                unit_price=unit_price,
                line_total=line_total,
                price_changed=Decimal(item.price_snapshot) != unit_price,
                in_stock=in_stock,
                product=CartProductOut(
                    id=product.id,
                    sku=product.sku,
                    pack_size=product.pack_size,
                    mrp=Decimal(product.mrp),
                    price=unit_price,
                    available_quantity=product.available_quantity,
                    is_active=product.is_active and medicine.is_active,
                    medicine_id=medicine.id,
                    medicine_name=medicine.medicine_name,
                    brand_name=medicine.brand_name,
                    strength=medicine.strength,
                    formulation=medicine.formulation,
                    prescription_required=medicine.prescription_required,
                    image_url=medicine.image_url,
                ),
            )
        )

    delivery = delivery_charge_for(subtotal, settings)
    return CartOut(
        id=cart.id,
        items=items,
        item_count=sum(i.quantity for i in items),
        subtotal=subtotal,
        delivery_charge=delivery,
        total=subtotal + delivery,
        free_delivery_above=settings.delivery_free_above,
        requires_prescription=requires_rx,
        has_unavailable_items=unavailable,
    )
