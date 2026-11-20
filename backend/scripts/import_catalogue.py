"""Load the catalogue from the Kaggle Indian medicine datasets.

    python -m scripts.import_catalogue --az <A_Z_medicines_dataset_of_India.csv> \
        --usage <medicine_dataset.csv> [--limit 20000] [--reset]

Sources (CSV files, download from Kaggle):
  * shudhanshusingh/az-medicine-dataset-of-india        product, price, pack, manufacturer, salts
  * shudhanshusingh/250k-medicines-usage-side-effects-and-substitutes
                                                        uses, side effects, therapeutic class

Prices are taken as MRP. Stock levels and the small demo discounts are generated, and the
prescription flag is a heuristic (therapeutic class + salt keywords), not a legal schedule.
"""

import argparse
import csv
import hashlib
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, insert, select, text, update  # noqa: E402

from app.database.session import SessionLocal, engine  # noqa: E402
from app.models import Inventory, Medicine, OrderItem, Product  # noqa: E402
from app.utils.text import normalise_name  # noqa: E402
from scripts.seed import seed_categories  # noqa: E402

csv.field_size_limit(10_000_000)

FORMS = {
    "tablet": "tablet",
    "tablets": "tablet",
    "tab": "tablet",
    "capsule": "capsule",
    "capsules": "capsule",
    "syrup": "syrup",
    "suspension": "suspension",
    "injection": "injection",
    "cream": "cream",
    "gel": "gel",
    "ointment": "ointment",
    "lotion": "lotion",
    "drop": "drops",
    "drops": "drops",
    "inhaler": "inhaler",
    "powder": "powder",
    "sachet": "sachet",
    "solution": "solution",
    "spray": "spray",
    "soap": "soap",
    "shampoo": "shampoo",
    "oil": "oil",
    "liquid": "liquid",
    "kit": "kit",
    "patch": "patch",
    "granules": "granules",
    "lozenges": "lozenges",
    "lozenge": "lozenges",
    "infusion": "infusion",
    "respules": "respules",
    "rotacaps": "rotacaps",
    "transpules": "respules",
    "paste": "paste",
    "mouthwash": "mouthwash",
    "expectorant": "syrup",
    "pessary": "pessary",
    "suppository": "suppository",
    "nebuliser": "solution",
    "eye": "drops",
    "ear": "drops",
    "nasal": "spray",
}
FORM_WORDS = set(FORMS) | {"sr", "dt", "xr", "er", "cr", "md", "od", "mr", "pr", "ds", "forte", "plus", "duo"}

RX_CLASSES = {
    "ANTI INFECTIVES",
    "CARDIAC",
    "ANTI DIABETIC",
    "NEURO CNS",
    "HORMONES",
    "GYNAECOLOGICAL",
    "ANTI NEOPLASTICS",
    "BLOOD RELATED",
    "UROLOGY",
    "ANTI MALARIALS",
    "VACCINES",
    "OPHTHAL",
    "OPHTHAL OTOLOGICALS",
    "OTOLOGICALS",
    "SEX STIMULANTS REJUVENATORS",
}
RX_SALT_HINTS = (
    "cillin",
    "mycin",
    "floxacin",
    "cycline",
    "cef",
    "penem",
    "conazole",
    "metformin",
    "glipt",
    "glimepiride",
    "gliclazide",
    "insulin",
    "sartan",
    "pril",
    "olol",
    "statin",
    "zepam",
    "zolam",
    "tramadol",
    "codeine",
    "prednis",
    "dexameth",
    "hydrocortisone",
    "betameth",
    "thyroxine",
    "clopidogrel",
    "warfarin",
    "amlodipine",
    "atenolol",
    "metoprolol",
    "furosemide",
    "torsemide",
    "sertraline",
    "escitalopram",
    "fluoxetine",
    "olanzapine",
    "risperidone",
    "phenytoin",
    "valpro",
    "levetiracetam",
    "gabapentin",
    "pregabalin",
    "isotretinoin",
    "finasteride",
    "tadalafil",
    "sildenafil",
)
CATEGORY_BY_CLASS = {
    "DERMA": "beauty",
    "VITAMINS MINERALS NUTRIENTS": "groceries",
    "PAIN ANALGESICS": "general-medicines",
    "GASTRO INTESTINAL": "general-medicines",
    "RESPIRATORY": "general-medicines",
    "STOMATOLOGICALS": "personal-care",
    "OTHERS": "general-medicines",
}
STRENGTH_IN_SALT = re.compile(r"\(([^)]*)\)")
NAME_STRENGTH = re.compile(r"\d+(?:\.\d+)?\s*(?:mg|mcg|ml|iu|%|gm|g)\b", re.IGNORECASE)


def _hash(value: str) -> int:
    return int(hashlib.blake2b(value.encode("utf-8"), digest_size=4).hexdigest(), 16)


def brand_from_name(name: str) -> str:
    tokens = []
    for token in name.split():
        low = token.lower().strip(".,")
        if any(ch.isdigit() for ch in token) or low in FORM_WORDS or low in {"mg", "ml", "mcg", "iu", "%"}:
            break
        tokens.append(token)
        if len(tokens) == 3:
            break
    return " ".join(tokens) or name.split()[0]


def form_from_name(name: str, pack_label: str) -> str | None:
    for token in reversed(name.lower().replace("/", " ").split()):
        token = token.strip(".,()")
        if token in FORMS:
            return FORMS[token]
    for token in pack_label.lower().split():
        if token in FORMS:
            return FORMS[token]
    return None


def parse_salts(*parts: str) -> tuple[list[str], list[str]]:
    """Return (salt names, strengths) from 'Amoxycillin (500mg)' style strings."""
    salts, strengths = [], []
    for part in parts:
        part = (part or "").strip()
        if not part or part.lower() == "nan":
            continue
        inner = STRENGTH_IN_SALT.search(part)
        salt = STRENGTH_IN_SALT.sub("", part).strip(" +,")
        if salt:
            salts.append(" ".join(salt.split()))
        if inner and inner.group(1).strip():
            strengths.append(inner.group(1).strip())
    return salts, strengths


def is_prescription(
    therapeutic_class: str | None, habit_forming: str | None, salts: list[str], form: str | None
) -> bool:
    if (habit_forming or "").strip().lower() == "yes":
        return True
    joined = " ".join(salts).lower()
    topical = form in {"cream", "gel", "ointment", "lotion", "soap", "shampoo", "oil", "paste", "mouthwash"}
    if therapeutic_class in RX_CLASSES and not (topical and therapeutic_class == "ANTI INFECTIVES"):
        return True
    if therapeutic_class == "DERMA":
        return any(h in joined for h in ("prednis", "betameth", "clobetasol", "mometasone", "isotretinoin"))
    if topical:
        return False
    return any(hint in joined for hint in RX_SALT_HINTS)


def category_for(therapeutic_class: str | None, rx: bool) -> str:
    if therapeutic_class in CATEGORY_BY_CLASS:
        return CATEGORY_BY_CLASS[therapeutic_class]
    if therapeutic_class in RX_CLASSES or rx:
        return "specialist"
    return "general-medicines"


def load_usage(path: Path) -> dict[str, dict]:
    usage: dict[str, dict] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            key = (row.get("name") or "").strip().lower()
            if not key or key in usage:
                continue
            uses = [row.get(f"use{i}", "") for i in range(5)]
            effects = [row.get(f"sideEffect{i}", "") for i in range(5)]
            usage[key] = {
                "class": (row.get("Therapeutic Class") or "").strip() or None,
                "habit": row.get("Habit Forming"),
                "uses": [u.strip() for u in uses if u and u.strip()],
                "effects": [e.strip() for e in effects if e and e.strip()],
            }
    return usage


def build_rows(az_path: Path, usage: dict[str, dict], categories: dict[str, int], limit: int | None):
    seen: set[str] = set()
    with az_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if limit is not None and len(seen) >= limit:
                break
            if (row.get("Is_discontinued") or "").strip().lower() == "true":
                continue
            name = " ".join((row.get("name") or "").split())
            key = name.lower()
            if not name or key in seen:
                continue
            try:
                price = round(float(row.get("price(₹)") or 0), 2)
            except ValueError:
                continue
            if price <= 0:
                continue
            seen.add(key)

            salts, strengths = parse_salts(
                row.get("short_composition1", ""), row.get("short_composition2", "")
            )
            info = usage.get(key, {})
            form = form_from_name(name, row.get("pack_size_label", "") or "")
            rx = is_prescription(info.get("class"), info.get("habit"), salts, form)
            strength = " / ".join(strengths) if strengths else (NAME_STRENGTH.search(name) or [None])[0]
            if strength and not isinstance(strength, str):
                strength = strength.group(0)
            description_parts = []
            if info.get("uses"):
                description_parts.append("Used for: " + "; ".join(info["uses"][:3]) + ".")
            if info.get("effects"):
                description_parts.append("Common side effects: " + ", ".join(info["effects"][:5]) + ".")
            description = " ".join(description_parts) or None

            yield {
                "medicine": {
                    "medicine_name": name[:150],
                    "generic_name": (" + ".join(salts) or None) and " + ".join(salts)[:150],
                    "brand_name": brand_from_name(name)[:120],
                    "strength": (strength or None) and str(strength)[:50],
                    "formulation": form,
                    "manufacturer": (" ".join((row.get("manufacturer_name") or "").split()) or None)
                    and row.get("manufacturer_name").strip()[:120],
                    "description": description,
                    "prescription_required": rx,
                    "category_id": categories[category_for(info.get("class"), rx)],
                    "image_url": None,
                    "is_active": True,
                    "search_name": normalise_name(name)[:150],
                    "composition": (
                        " + ".join(f"{s} ({t})" for s, t in zip(salts, strengths, strict=False))
                        if len(strengths) == len(salts)
                        else " + ".join(salts)
                    )[:300]
                    or None,
                    "composition_key": "|".join(normalise_name(s) for s in salts)[:300] or None,
                    "therapeutic_class": info.get("class"),
                },
                "pack_size": (row.get("pack_size_label") or "1 unit").strip()[:60],
                "mrp": price,
                "source_id": row.get("id") or key,
            }


def refresh_popularity(db) -> int:
    """Products per manufacturer: used to rank equivalent brands when matching prescriptions."""
    if engine.dialect.name == "postgresql":
        sql = """
            UPDATE medicines SET popularity = counts.n
            FROM (SELECT manufacturer, COUNT(*) AS n FROM medicines
                  WHERE manufacturer IS NOT NULL GROUP BY manufacturer) AS counts
            WHERE medicines.manufacturer = counts.manufacturer
        """
    else:
        sql = """
            UPDATE medicines SET popularity = (
                SELECT COUNT(*) FROM medicines AS m2 WHERE m2.manufacturer = medicines.manufacturer
            ) WHERE manufacturer IS NOT NULL
        """
    updated = db.execute(text(sql)).rowcount
    db.commit()
    return updated


def reset_catalogue(db) -> tuple[int, int]:
    referenced = select(Product.medicine_id).where(
        Product.id.in_(select(OrderItem.product_id).where(OrderItem.product_id.is_not(None)))
    )
    deactivated = db.execute(
        update(Medicine).where(Medicine.id.in_(referenced)).values(is_active=False)
    ).rowcount
    deleted = db.execute(delete(Medicine).where(Medicine.id.not_in(referenced))).rowcount
    db.flush()
    return deleted, deactivated


def main() -> None:
    parser = argparse.ArgumentParser(description="Import the Kaggle medicine catalogue")
    parser.add_argument("--az", required=True, type=Path, help="A_Z_medicines_dataset_of_India.csv")
    parser.add_argument("--usage", type=Path, help="medicine_dataset.csv (250K usage/side effects)")
    parser.add_argument("--limit", type=int, help="import at most this many products")
    parser.add_argument("--reset", action="store_true", help="remove the existing catalogue first")
    parser.add_argument("--batch", type=int, default=5000)
    args = parser.parse_args()

    started = time.perf_counter()
    usage = load_usage(args.usage) if args.usage else {}
    print(f"usage records: {len(usage):,}")

    with SessionLocal() as db:
        if args.reset:
            deleted, deactivated = reset_catalogue(db)
            print(f"reset: deleted {deleted:,} medicines, deactivated {deactivated:,} with order history")
        categories = {c.slug: c.id for c in seed_categories(db).values()}
        db.commit()

        next_medicine = (db.scalar(select(Medicine.id).order_by(Medicine.id.desc()).limit(1)) or 0) + 1
        next_product = (db.scalar(select(Product.id).order_by(Product.id.desc()).limit(1)) or 0) + 1
        next_inventory = (db.scalar(select(Inventory.id).order_by(Inventory.id.desc()).limit(1)) or 0) + 1
        existing_skus = set(db.scalars(select(Product.sku)).all())

        medicines, products, stock = [], [], []
        total = 0

        def flush():
            nonlocal medicines, products, stock
            if not medicines:
                return
            db.execute(insert(Medicine), medicines)
            db.execute(insert(Product), products)
            db.execute(insert(Inventory), stock)
            db.commit()
            medicines, products, stock = [], [], []

        for item in build_rows(args.az, usage, categories, args.limit):
            sku = f"AZ-{item['source_id']}"
            if sku in existing_skus:
                continue
            existing_skus.add(sku)
            seed = _hash(sku)
            discount = (0, 0.05, 0.10, 0.15)[seed % 4] if seed % 3 == 0 else 0
            price = round(item["mrp"] * (1 - discount), 2)
            quantity = 0 if seed % 37 == 0 else 5 + seed % 140

            medicine_id, product_id, inventory_id = next_medicine, next_product, next_inventory
            next_medicine += 1
            next_product += 1
            next_inventory += 1
            medicines.append({"id": medicine_id, **item["medicine"]})
            products.append(
                {
                    "id": product_id,
                    "medicine_id": medicine_id,
                    "sku": sku,
                    "pack_size": item["pack_size"],
                    "mrp": item["mrp"],
                    "price": price,
                    "is_active": True,
                }
            )
            stock.append(
                {
                    "id": inventory_id,
                    "product_id": product_id,
                    "available_quantity": quantity,
                    "batch_number": f"B{seed % 9000 + 1000}",
                    "expiry_date": None,
                }
            )
            total += 1
            if len(medicines) >= args.batch:
                flush()
                print(f"  inserted {total:,} ...", end="\r")
        flush()

        refresh_popularity(db)
        if engine.dialect.name == "postgresql":
            for table in ("medicines", "products", "inventory"):
                db.execute(
                    text(
                        f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), COALESCE((SELECT MAX(id) FROM {table}), 1))"
                    )
                )
            db.commit()

    categories_count = len(categories)
    print(
        f"\nimported {total:,} products into {categories_count} categories in {time.perf_counter() - started:.0f}s"
    )


if __name__ == "__main__":
    main()
