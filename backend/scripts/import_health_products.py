"""Add general health products: ORS, health drinks, supplements, personal care and first aid.

The medicine datasets only cover prescription-style allopathic products, so everyday health items
come from separate sources:

  --bigbasket  "BigBasket Products.csv"   Kaggle: surajjha101/bigbasket-entire-product-list-28k-datapoints
               (Beauty & Hygiene, Baby Care and health drinks only; groceries and household skipped)
  --amazon     "Modified_Final_Dataset.csv"   Hugging Face: SageLiao/Amazon-product-healthcare
               (health-relevant rows only: devices, first aid, health drinks, supplements, personal care)
  built in     a short curated list of ORS powders and electrolyte drinks; no open dataset lists them,
               so names are real brands and prices are approximate demo values

    python -m scripts.import_health_products --bigbasket <csv> --amazon <csv>

The import is additive and idempotent: rows are keyed by SKU (BB-, AMZ-, OTC- prefixes) and
existing SKUs are skipped. Nothing here is marked as prescription-only.
"""

import argparse
import csv
import hashlib
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import insert, select, text  # noqa: E402

from app.database.session import SessionLocal, engine  # noqa: E402
from app.models import Inventory, Medicine, Product  # noqa: E402
from app.utils.text import normalise_name  # noqa: E402
from scripts.import_catalogue import NAME_STRENGTH, form_from_name, refresh_popularity  # noqa: E402
from scripts.seed import seed_categories  # noqa: E402

csv.field_size_limit(10_000_000)

GENERAL, SPECIALIST, BEAUTY, PERSONAL, WELLNESS, DEVICES = (
    "general-medicines",
    "specialist",
    "beauty",
    "personal-care",
    "groceries",
    "devices",
)


@dataclass
class HealthItem:
    sku: str
    name: str
    brand: str | None
    category: str
    price: float
    mrp: float
    pack_size: str = "1 pack"
    description: str | None = None
    generic: str | None = None
    composition: str | None = None
    composition_key: str | None = None
    formulation: str | None = None
    strength: str | None = None
    kind: str | None = None  # stored in therapeutic_class, e.g. "Ayurveda", "ORS"


# ----------------------------------------------------------------------------- curated ORS

ORS_POWDER_SALTS = "Sodium chloride + Potassium chloride + Sodium citrate + Dextrose"
ORS_POWDER_KEY = "ors|sodium chloride|potassium chloride|sodium citrate|dextrose"
ORS_POWDER_TEXT = (
    "Oral rehydration salts (WHO formula) to replace fluids and electrolytes lost through diarrhoea, "
    "vomiting or heat. Dissolve one sachet in the volume of clean drinking water stated on the pack. "
    "Demo listing: curated product, approximate price."
)
ELECTROLYTE_DRINK_TEXT = (
    "Ready-to-drink electrolyte beverage for hydration after exercise, heat or mild dehydration. "
    "It is not a substitute for WHO-formula ORS during diarrhoea; use ORS powder for that. "
    "Demo listing: curated product, approximate price."
)


def _ors(sku, name, brand, pack, mrp, price, category, *, powder):
    return HealthItem(
        sku=f"OTC-{sku}",
        name=name,
        brand=brand,
        category=category,
        price=price,
        mrp=mrp,
        pack_size=pack,
        description=ORS_POWDER_TEXT if powder else ELECTROLYTE_DRINK_TEXT,
        generic="Oral rehydration salts" if powder else "Electrolyte drink",
        composition=ORS_POWDER_SALTS if powder else "Water + Electrolytes + Dextrose",
        composition_key=ORS_POWDER_KEY if powder else "electrolyte drink",
        formulation="powder" if powder else "liquid",
        kind="ORS" if powder else "Electrolyte drink",
    )


CURATED_ORS: list[HealthItem] = [
    _ors(
        "ORS-ELECTRAL-OR",
        "Electral Powder Orange",
        "Electral",
        "Sachet of 21.8 g",
        22.0,
        22.0,
        GENERAL,
        powder=True,
    ),
    _ors(
        "ORS-ELECTRAL-AP",
        "Electral Powder Apple",
        "Electral",
        "Sachet of 21.8 g",
        22.0,
        22.0,
        GENERAL,
        powder=True,
    ),
    _ors(
        "ORS-ELECTRAL-10",
        "Electral Powder Orange (Pack of 10)",
        "Electral",
        "10 sachets of 21.8 g",
        220.0,
        199.0,
        GENERAL,
        powder=True,
    ),
    _ors(
        "ORS-MOREPEN",
        "Dr Morepen ORS Powder Orange",
        "Dr Morepen",
        "Sachet of 21.8 g",
        25.0,
        23.0,
        GENERAL,
        powder=True,
    ),
    _ors(
        "ORS-PROLYTE-PW",
        "Prolyte ORS Powder Refreshing Orange",
        "Prolyte",
        "Sachet of 21 g",
        25.0,
        24.0,
        GENERAL,
        powder=True,
    ),
    _ors(
        "ORS-ELECTRORUSH-PW",
        "Electrorush ORS Powder",
        "Electrorush",
        "Sachet of 21 g",
        25.0,
        23.0,
        GENERAL,
        powder=True,
    ),
    _ors(
        "ORS-WHO-PLAIN",
        "ORS Powder WHO Formula Plain",
        "ORS",
        "Sachet of 21 g",
        20.0,
        19.0,
        GENERAL,
        powder=True,
    ),
    _ors(
        "ORS-ORSL-OR",
        "ORSL Plus Electrolyte Drink Orange",
        "ORSL",
        "Tetra pack of 200 ml",
        40.0,
        38.0,
        WELLNESS,
        powder=False,
    ),
    _ors(
        "ORS-ORSL-AP",
        "ORSL Electrolyte Drink Apple",
        "ORSL",
        "Tetra pack of 200 ml",
        40.0,
        38.0,
        WELLNESS,
        powder=False,
    ),
    _ors(
        "ORS-ORSL-LM",
        "ORSL Electrolyte Drink Lemon",
        "ORSL",
        "Tetra pack of 200 ml",
        40.0,
        38.0,
        WELLNESS,
        powder=False,
    ),
    _ors(
        "ORS-ENERZAL-OR",
        "Enerzal Electrolyte Energy Drink Orange",
        "Enerzal",
        "Tetra pack of 200 ml",
        35.0,
        33.0,
        WELLNESS,
        powder=False,
    ),
    _ors(
        "ORS-PROLYTE-RTD",
        "Prolyte ORS Ready to Drink Nimbu Paani",
        "Prolyte",
        "Bottle of 200 ml",
        40.0,
        38.0,
        WELLNESS,
        powder=False,
    ),
    _ors(
        "ORS-ELECTRORUSH-RTD",
        "Electrorush ORS Drink Cola",
        "Electrorush",
        "Tetra pack of 200 ml",
        35.0,
        33.0,
        WELLNESS,
        powder=False,
    ),
]


# ----------------------------------------------------------------------------- BigBasket

BIGBASKET_SUB = {
    "Skin Care": BEAUTY,
    "Hair Care": BEAUTY,
    "Makeup": BEAUTY,
    "Fragrances & Deos": BEAUTY,
    "Men's Grooming": BEAUTY,
    "Bath & Hand Wash": PERSONAL,
    "Oral Care": PERSONAL,
    "Feminine Hygiene": PERSONAL,
    "Mothers & Maternity": PERSONAL,
}
BIGBASKET_HEALTH_TYPE = {
    "Everyday Medicine": GENERAL,
    "Face Masks & Safety Gears": DEVICES,
    "Antiseptics & Bandages": DEVICES,
    "Cotton & Ear Buds": DEVICES,
    "Adult Diapers": PERSONAL,
    "Sexual Wellness": PERSONAL,
    "Intimate Wash & Care": PERSONAL,
    "Sanitary Napkins": PERSONAL,
    "Bathing Bars & Soaps": PERSONAL,
    "Face Care": BEAUTY,
    "Hair Oil & Serum": BEAUTY,
}
PROMO = re.compile(r"\s*(For (Beauty|more) tips.*$|https?://\S+)", re.IGNORECASE)
PACK_IN_NAME = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:ml|l|ltr|g|gm|kg|pcs?|pieces?|tablets?|capsules?|sachets?|strips?|n)\b",
    re.IGNORECASE,
)


def _money(value) -> float | None:
    try:
        number = float(str(value).replace("₹", "").replace(",", "").strip())
    except ValueError:
        return None
    return round(number, 2) if number > 0 else None


def _clean(value: str | None) -> str:
    return " ".join((value or "").split())


def _sku(prefix: str, *parts: str) -> str:
    digest = hashlib.blake2b("|".join(parts).lower().encode("utf-8"), digest_size=6).hexdigest()
    return f"{prefix}-{digest}"


def bigbasket_category(category: str, sub_category: str, kind: str) -> str | None:
    """Catalogue slug for a BigBasket row, or None when it is not a health or care product."""
    if category == "Beauty & Hygiene":
        if sub_category == "Health & Medicine":
            return BIGBASKET_HEALTH_TYPE.get(kind, WELLNESS)
        return BIGBASKET_SUB.get(sub_category)
    if category == "Baby Care":
        if sub_category == "Baby Food & Formula":
            return WELLNESS
        return None if sub_category == "Atta, Flours & Sooji" else PERSONAL
    if category == "Beverages" and sub_category == "Health Drink, Supplement":
        return WELLNESS
    return None


def bigbasket_items(path: Path) -> list[HealthItem]:
    items: list[HealthItem] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            slug = bigbasket_category(
                _clean(row.get("category")), _clean(row.get("sub_category")), _clean(row.get("type"))
            )
            name = _clean(row.get("product"))
            price = _money(row.get("sale_price"))
            if slug is None or not name or price is None:
                continue
            mrp = max(_money(row.get("market_price")) or price, price)
            brand = _clean(row.get("brand")) or None
            pack = PACK_IN_NAME.search(name)
            description = PROMO.sub("", _clean(row.get("description"))).strip() or None
            items.append(
                HealthItem(
                    sku=_sku("BB", brand or "", name),
                    name=name[:150],
                    brand=brand[:120] if brand else None,
                    category=slug,
                    price=price,
                    mrp=mrp,
                    pack_size=(pack.group(0) if pack else "1 pack")[:60],
                    description=description,
                    formulation=form_from_name(name, ""),
                    strength=(NAME_STRENGTH.search(name).group(0) if NAME_STRENGTH.search(name) else None),
                    kind=_clean(row.get("type"))[:80] or None,
                )
            )
    return items


# ----------------------------------------------------------------------------- Amazon India

AMAZON_GROUPS: list[tuple[str, re.Pattern]] = [
    (
        DEVICES,
        re.compile(
            r"thermometer|sphygmo|blood pressure|bp monitor|nebuli[sz]er|glucometer|glucose monitor|"
            r"test strips|oximeter|weighing scale|weight scale|heating pad|hot water bag|first aid|"
            r"bandage|plaster|face mask|n95|steam vaporizer|vaporiser|massager|knee support|"
            r"back support|lumbo|cervical",
            re.IGNORECASE,
        ),
    ),
    (
        WELLNESS,
        re.compile(
            r"glucon|complan|horlicks|bournvita|pediasure|ensure|protein|whey|multivitamin|vitamin|"
            r"omega|fish oil|chyawanprash|ors\b|electrolyte|supplement|ashwagandha|giloy|immunity|"
            r"health drink|energy drink|nutrition",
            re.IGNORECASE,
        ),
    ),
    (
        PERSONAL,
        re.compile(
            r"toothpaste|toothbrush|mouthwash|soap|body wash|hand wash|sanitizer|sanitiser|"
            r"sanitary|pads|tampon|menstrual|diaper|intimate|deodorant|antiseptic",
            re.IGNORECASE,
        ),
    ),
    (
        BEAUTY,
        re.compile(
            r"face wash|cleanser|sunscreen|moisturi[sz]|lotion|serum|shampoo|conditioner|hair oil|"
            r"face cream|lip balm|body cream",
            re.IGNORECASE,
        ),
    ),
]


def amazon_category(name: str) -> str | None:
    for slug, pattern in AMAZON_GROUPS:
        if pattern.search(name):
            return slug
    return None


def amazon_items(path: Path) -> list[HealthItem]:
    items: list[HealthItem] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            full_name = _clean(row.get("name"))
            slug = amazon_category(full_name)
            mrp = _money(row.get("actual_price"))
            price = _money(row.get("discount_price")) or mrp
            if slug is None or not full_name or price is None:
                continue
            # Amazon titles carry marketing text after "|" or "-"; keep the product part
            name = re.split(r"\s+\|\s+|\|", full_name)[0].strip(" ,-")[:150]
            brand = name.split()[0].strip(",'") if name else None
            pack = PACK_IN_NAME.search(full_name)
            items.append(
                HealthItem(
                    sku=_sku("AMZ", _clean(row.get("id")) or full_name),
                    name=name,
                    brand=brand[:120] if brand else None,
                    category=slug,
                    price=price,
                    mrp=max(mrp or price, price),
                    pack_size=(pack.group(0) if pack else "1 unit")[:60],
                    description=full_name if len(full_name) > len(name) else None,
                    formulation=form_from_name(name, ""),
                    strength=(NAME_STRENGTH.search(name).group(0) if NAME_STRENGTH.search(name) else None),
                    kind=_clean(row.get("sub_category"))[:80] or None,
                )
            )
    return items


# ----------------------------------------------------------------------------- insert


def insert_items(db, items: list[HealthItem], categories: dict[str, int]) -> int:
    existing_skus = set(db.scalars(select(Product.sku)).all())
    seen_names: set[str] = set()
    next_medicine = (db.scalar(select(Medicine.id).order_by(Medicine.id.desc()).limit(1)) or 0) + 1
    next_product = (db.scalar(select(Product.id).order_by(Product.id.desc()).limit(1)) or 0) + 1
    next_inventory = (db.scalar(select(Inventory.id).order_by(Inventory.id.desc()).limit(1)) or 0) + 1
    medicines, products, stock = [], [], []
    for item in items:
        name_key = f"{(item.brand or '').lower()}|{item.name.lower()}"
        if item.sku in existing_skus or name_key in seen_names:
            continue
        existing_skus.add(item.sku)
        seen_names.add(name_key)
        seed = int(hashlib.blake2b(item.sku.encode(), digest_size=4).hexdigest(), 16)
        medicines.append(
            {
                "id": next_medicine,
                "medicine_name": item.name,
                "generic_name": item.generic,
                "brand_name": item.brand,
                "strength": item.strength[:50] if item.strength else None,
                "formulation": item.formulation,
                "manufacturer": item.brand,
                "description": item.description,
                "prescription_required": False,
                "category_id": categories[item.category],
                "image_url": None,
                "is_active": True,
                "search_name": normalise_name(item.name)[:150],
                "composition": item.composition,
                "composition_key": item.composition_key,
                "therapeutic_class": item.kind,
                "popularity": 0,
            }
        )
        products.append(
            {
                "id": next_product,
                "medicine_id": next_medicine,
                "sku": item.sku[:40],
                "pack_size": item.pack_size,
                "mrp": item.mrp,
                "price": item.price,
                "is_active": True,
            }
        )
        stock.append(
            {
                "id": next_inventory,
                "product_id": next_product,
                "available_quantity": 0 if seed % 41 == 0 else 10 + seed % 150,
                "batch_number": f"B{seed % 9000 + 1000}",
                "expiry_date": None,
            }
        )
        next_medicine += 1
        next_product += 1
        next_inventory += 1
    for start in range(0, len(medicines), 2000):
        db.execute(insert(Medicine), medicines[start : start + 2000])
        db.execute(insert(Product), products[start : start + 2000])
        db.execute(insert(Inventory), stock[start : start + 2000])
        db.commit()
    if engine.dialect.name == "postgresql":
        for table in ("medicines", "products", "inventory"):
            db.execute(
                text(
                    f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), COALESCE((SELECT MAX(id) FROM {table}), 1))"
                )
            )
        db.commit()
    return len(medicines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Import general health products")
    parser.add_argument("--bigbasket", type=Path, help="BigBasket Products.csv")
    parser.add_argument("--amazon", type=Path, help="Modified_Final_Dataset.csv (Amazon healthcare)")
    parser.add_argument("--no-curated", action="store_true", help="skip the built-in ORS list")
    args = parser.parse_args()

    started = time.perf_counter()
    items: list[HealthItem] = [] if args.no_curated else list(CURATED_ORS)
    if args.bigbasket:
        items += bigbasket_items(args.bigbasket)
    if args.amazon:
        items += amazon_items(args.amazon)
    by_category: dict[str, int] = {}
    for item in items:
        by_category[item.category] = by_category.get(item.category, 0) + 1
    print("candidates:", len(items), by_category)

    with SessionLocal() as db:
        categories = {c.slug: c.id for c in seed_categories(db).values()}
        db.commit()
        added = insert_items(db, items, categories)
        refresh_popularity(db)
    print(f"added {added:,} products in {time.perf_counter() - started:.0f}s")


if __name__ == "__main__":
    main()
