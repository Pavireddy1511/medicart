"""Seed demonstration data.

All medicines, manufacturers, batch numbers and accounts here are fictional sample data
for a student project. Run from the backend folder:

    python -m scripts.seed            # add missing rows, keep existing ones
    python -m scripts.seed --reset    # wipe catalogue + demo accounts first
"""

import argparse
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, select  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.database.session import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Address,
    Cart,
    Inventory,
    Medicine,
    MedicineCategory,
    Product,
    User,
    UserRole,
)
from scripts.seed_data import CATEGORIES, DEMO_ACCOUNTS, MEDICINES  # noqa: E402
from scripts.seed_data_extra import EXTRA_MEDICINES  # noqa: E402


def seed_categories(db) -> dict[str, MedicineCategory]:
    existing = {c.slug: c for c in db.scalars(select(MedicineCategory)).all()}
    for order, item in enumerate(CATEGORIES):
        category = existing.get(item["slug"])
        if category is None:
            category = MedicineCategory(slug=item["slug"])
            db.add(category)
            existing[item["slug"]] = category
        category.name = item["name"]
        category.description = item["description"]
        category.icon = item["icon"]
        category.sort_order = order
        category.is_active = True
    db.flush()
    return existing


def seed_medicines(db, categories: dict[str, MedicineCategory]) -> int:
    created = 0
    existing_skus = set(db.scalars(select(Product.sku)).all())
    for entry in MEDICINES + EXTRA_MEDICINES:
        skus = [p["sku"] for p in entry["products"]]
        if all(sku in existing_skus for sku in skus):
            continue
        medicine = db.scalar(
            select(Medicine).where(
                Medicine.medicine_name == entry["medicine_name"],
                Medicine.strength.is_(entry.get("strength"))
                if entry.get("strength") is None
                else Medicine.strength == entry.get("strength"),
            )
        )
        if medicine is None:
            medicine = Medicine(
                medicine_name=entry["medicine_name"],
                generic_name=entry.get("generic_name"),
                brand_name=entry.get("brand_name"),
                strength=entry.get("strength"),
                formulation=entry.get("formulation"),
                manufacturer=entry.get("manufacturer"),
                description=entry.get("description"),
                prescription_required=entry.get("prescription_required", False),
                category_id=categories[entry["category"]].id,
                image_url=entry.get("image_url"),
                is_active=True,
            )
            db.add(medicine)
            db.flush()
            created += 1
        for product_in in entry["products"]:
            if product_in["sku"] in existing_skus:
                continue
            product = Product(
                medicine_id=medicine.id,
                sku=product_in["sku"],
                pack_size=product_in["pack_size"],
                mrp=Decimal(str(product_in["mrp"])),
                price=Decimal(str(product_in["price"])),
                is_active=True,
            )
            product.inventory = Inventory(
                available_quantity=product_in["stock"],
                batch_number=product_in.get("batch", f"DEMO-{product_in['sku'][-6:]}"),
                expiry_date=product_in.get("expiry", date(2027, 12, 31)),
            )
            db.add(product)
            existing_skus.add(product_in["sku"])
    db.flush()
    return created


def seed_accounts(db) -> int:
    created = 0
    for account in DEMO_ACCOUNTS:
        user = db.scalar(select(User).where(User.mobile_number == account["mobile_number"]))
        if user is None:
            user = User(
                full_name=account["full_name"],
                mobile_number=account["mobile_number"],
                email=account.get("email"),
                password_hash=hash_password(account["password"]),
                role=UserRole(account["role"]).value,
                is_active=True,
            )
            user.cart = Cart()
            db.add(user)
            db.flush()
            created += 1
            for addr in account.get("addresses", []):
                db.add(Address(user_id=user.id, **addr))
    db.flush()
    return created


def reset(db) -> None:
    demo_mobiles = [a["mobile_number"] for a in DEMO_ACCOUNTS]
    db.execute(delete(User).where(User.mobile_number.in_(demo_mobiles)))
    db.execute(delete(Medicine))
    db.execute(delete(MedicineCategory))
    db.flush()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed MediCart demo data")
    parser.add_argument("--reset", action="store_true", help="delete catalogue and demo accounts first")
    args = parser.parse_args()

    with SessionLocal() as db:
        if args.reset:
            reset(db)
        categories = seed_categories(db)
        medicines = seed_medicines(db, categories)
        accounts = seed_accounts(db)
        db.commit()

    print(f"Categories: {len(categories)} | new medicines: {medicines} | new demo accounts: {accounts}")
    print("Demo logins (mobile / password):")
    for account in DEMO_ACCOUNTS:
        print(f"  {account['role']:<10} {account['mobile_number']} / {account['password']}")


if __name__ == "__main__":
    main()
