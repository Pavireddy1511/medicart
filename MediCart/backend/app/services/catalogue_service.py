import time

from sqlalchemy import Select, case, desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.models.catalogue import Inventory, Medicine, MedicineCategory, Product
from app.models.order import OrderItem
from app.schemas.catalogue import CategoryOut, HomeFeedOut, MedicineSearchParams, MedicineSummary


def _medicine_options(stmt: Select) -> Select:
    return stmt.options(
        selectinload(Medicine.products).selectinload(Product.inventory),
        selectinload(Medicine.category),
    )


def _has_active_product():
    return select(Product.id).where(Product.medicine_id == Medicine.id, Product.is_active.is_(True)).exists()


def _min_price_subquery():
    return (
        select(func.min(Product.price))
        .where(Product.medicine_id == Medicine.id, Product.is_active.is_(True))
        .scalar_subquery()
    )


def list_categories(db: Session) -> list[CategoryOut]:
    counts = (
        select(Medicine.category_id, func.count(Medicine.id).label("n"))
        .where(Medicine.is_active.is_(True))
        .group_by(Medicine.category_id)
        .subquery()
    )
    rows = db.execute(
        select(MedicineCategory, func.coalesce(counts.c.n, 0))
        .outerjoin(counts, counts.c.category_id == MedicineCategory.id)
        .where(MedicineCategory.is_active.is_(True))
        .order_by(MedicineCategory.sort_order, MedicineCategory.name)
    ).all()
    result = []
    for category, count in rows:
        item = CategoryOut.model_validate(category)
        item.medicine_count = int(count)
        result.append(item)
    return result


def search_medicines(db: Session, params: MedicineSearchParams) -> tuple[list[Medicine], int]:
    """All words must match. When a multi-word query finds nothing ("ors juice"), the trailing
    words are dropped one at a time until something matches."""
    tokens = params.q.split()[:6] if params.q else []
    rows, total = _search(db, params, tokens)
    while total == 0 and len(tokens) > 1:
        tokens = tokens[:-1]
        rows, total = _search(db, params, tokens)
    return rows, total


def _search(db: Session, params: MedicineSearchParams, tokens: list[str]) -> tuple[list[Medicine], int]:
    stmt = select(Medicine).where(Medicine.is_active.is_(True), _has_active_product())

    if tokens:
        for token in tokens:
            like = f"%{token}%"
            stmt = stmt.where(
                # only trigram-indexed columns: names carry strength and form words already
                or_(
                    Medicine.medicine_name.ilike(like),
                    Medicine.brand_name.ilike(like),
                    Medicine.generic_name.ilike(like),
                    Medicine.composition_key.ilike(like),
                )
            )

    if params.category:
        stmt = stmt.join(MedicineCategory, Medicine.category_id == MedicineCategory.id).where(
            MedicineCategory.slug == params.category
        )

    if params.min_price is not None or params.max_price is not None:
        price_filter = select(Product.id).where(
            Product.medicine_id == Medicine.id, Product.is_active.is_(True)
        )
        if params.min_price is not None:
            price_filter = price_filter.where(Product.price >= params.min_price)
        if params.max_price is not None:
            price_filter = price_filter.where(Product.price <= params.max_price)
        stmt = stmt.where(price_filter.exists())

    if params.in_stock:
        stmt = stmt.where(
            select(Inventory.id)
            .join(Product, Product.id == Inventory.product_id)
            .where(
                Product.medicine_id == Medicine.id,
                Product.is_active.is_(True),
                Inventory.available_quantity > 0,
            )
            .exists()
        )

    if params.prescription_required is not None:
        stmt = stmt.where(Medicine.prescription_required.is_(params.prescription_required))

    min_price = _min_price_subquery()
    if params.sort == "price_asc":
        stmt = stmt.order_by(min_price.asc(), Medicine.medicine_name)
    elif params.sort == "price_desc":
        stmt = stmt.order_by(min_price.desc(), Medicine.medicine_name)
    elif params.sort == "name_desc":
        stmt = stmt.order_by(Medicine.medicine_name.desc())
    elif params.sort == "newest":
        stmt = stmt.order_by(Medicine.created_at.desc(), Medicine.id.desc())
    elif params.sort == "relevance" and tokens:
        phrase = " ".join(tokens).lower()
        prefix = f"{phrase}%"
        rank = case(
            # the whole word first ("ORS Powder" before "Orsacot")
            (or_(Medicine.search_name == phrase, Medicine.search_name.like(f"{phrase} %")), 0),
            # then the main ingredient, e.g. "ors" for Electral Powder
            (or_(Medicine.composition_key == phrase, Medicine.composition_key.like(f"{phrase}|%")), 1),
            (Medicine.medicine_name.ilike(prefix), 2),
            (Medicine.brand_name.ilike(prefix), 3),
            (Medicine.generic_name.ilike(prefix), 4),
            else_=5,
        )
        stmt = stmt.order_by(rank, Medicine.medicine_name)
    else:
        stmt = stmt.order_by(Medicine.medicine_name)

    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    offset = (params.page - 1) * params.page_size
    rows = db.scalars(_medicine_options(stmt).offset(offset).limit(params.page_size)).all()
    return list(rows), int(total)


def get_medicine(db: Session, medicine_id: int, *, include_inactive: bool = False) -> Medicine:
    stmt = _medicine_options(select(Medicine).where(Medicine.id == medicine_id))
    if not include_inactive:
        stmt = stmt.where(Medicine.is_active.is_(True))
    medicine = db.scalar(stmt)
    if medicine is None:
        raise NotFoundError("Medicine not found")
    return medicine


def get_medicines_by_ids(db: Session, ids: list[int]) -> dict[int, Medicine]:
    if not ids:
        return {}
    rows = db.scalars(_medicine_options(select(Medicine).where(Medicine.id.in_(set(ids))))).all()
    return {m.id: m for m in rows}


def get_product(db: Session, product_id: int) -> Product:
    product = db.scalar(
        select(Product)
        .where(Product.id == product_id)
        .options(selectinload(Product.inventory), selectinload(Product.medicine))
    )
    if product is None or not product.is_active or not product.medicine.is_active:
        raise NotFoundError("Product not found")
    return product


_HOME_CACHE: dict[str, tuple[float, HomeFeedOut]] = {}
HOME_CACHE_SECONDS = 60


def invalidate_home_cache() -> None:
    _HOME_CACHE.clear()


def _shuffle(column):
    # deterministic spread across the catalogue without a per-request random()
    return (column * 7919) % 10007


def home_feed(db: Session) -> HomeFeedOut:
    now = time.monotonic()
    cached = _HOME_CACHE.get("feed")
    if get_settings().app_env != "test" and cached and now - cached[0] < HOME_CACHE_SECONDS:
        return cached[1]

    stocked = (
        select(Product.medicine_id)
        .join(Inventory, Inventory.product_id == Product.id)
        .where(Product.is_active.is_(True), Inventory.available_quantity > 0)
    )
    active = Medicine.is_active.is_(True)

    deal_rows = db.execute(
        select(Product.medicine_id)
        .join(Inventory, Inventory.product_id == Product.id)
        .join(Medicine, Medicine.id == Product.medicine_id)
        .where(
            active,
            Product.is_active.is_(True),
            Inventory.available_quantity > 0,
            Product.mrp > Product.price,
        )
        .order_by(((Product.mrp - Product.price) / Product.mrp).desc(), Product.id)
        .limit(40)
    ).all()
    deal_ids = list(dict.fromkeys(row[0] for row in deal_rows))[:8]

    featured_ids = list(
        db.scalars(
            select(Medicine.id)
            .where(
                active,
                Medicine.prescription_required.is_(False),
                Medicine.id.in_(stocked),
                Medicine.id.not_in(deal_ids or [0]),
            )
            .order_by(_shuffle(Medicine.id))
            .limit(8)
        ).all()
    )

    sales = (
        select(Product.medicine_id, func.sum(OrderItem.quantity).label("sold"))
        .join(Product, Product.id == OrderItem.product_id)
        .group_by(Product.medicine_id)
        .subquery()
    )
    popular_ids = list(
        db.scalars(
            select(Medicine.id)
            .outerjoin(sales, sales.c.medicine_id == Medicine.id)
            .where(active, Medicine.id.in_(stocked))
            .order_by(desc(func.coalesce(sales.c.sold, 0)), _shuffle(Medicine.id + 3))
            .limit(8)
        ).all()
    )

    medicines = get_medicines_by_ids(db, [*deal_ids, *featured_ids, *popular_ids])

    def pick(ids: list[int]) -> list[MedicineSummary]:
        return [MedicineSummary.model_validate(medicines[i]) for i in ids if i in medicines]

    feed = HomeFeedOut(
        categories=list_categories(db),
        featured=pick(featured_ids),
        deals=pick(deal_ids),
        popular=pick(popular_ids),
    )
    _HOME_CACHE["feed"] = (now, feed)
    return feed
