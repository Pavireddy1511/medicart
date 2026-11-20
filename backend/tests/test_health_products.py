import csv

import pytest

from app.models.enums import MatchStatus
from app.services.matching_service import load_catalogue, match_name
from scripts.import_health_products import (
    CURATED_ORS,
    amazon_category,
    amazon_items,
    bigbasket_category,
    bigbasket_items,
    insert_items,
)
from scripts.seed import seed_categories


def _write_csv(path, header, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)
    return path


@pytest.fixture
def bigbasket_csv(tmp_path):
    header = [
        "index",
        "product",
        "category",
        "sub_category",
        "brand",
        "sale_price",
        "market_price",
        "type",
        "rating",
        "description",
    ]
    return _write_csv(
        tmp_path / "bb.csv",
        header,
        [
            [
                1,
                "Chyawanprash - Immunity Booster 500 g",
                "Beauty & Hygiene",
                "Health & Medicine",
                "Dabur",
                210,
                230,
                "Ayurveda",
                4.3,
                "Classic recipe. For Beauty tips, tricks & more visit https://bigbasket.blog/",
            ],
            [
                2,
                "Antiseptic Liquid",
                "Beauty & Hygiene",
                "Health & Medicine",
                "Dettol",
                95,
                99,
                "Antiseptics & Bandages",
                4.5,
                "",
            ],
            [
                3,
                "Neem Soap",
                "Beauty & Hygiene",
                "Bath & Hand Wash",
                "Margo",
                40,
                40,
                "Bathing Bars & Soaps",
                4.0,
                "",
            ],
            [
                4,
                "Basmati Rice",
                "Foodgrains, Oil & Masala",
                "Rice & Rice Products",
                "India Gate",
                120,
                150,
                "Basmati",
                4.1,
                "",
            ],
            [
                5,
                "Junior Horlicks Health Drink",
                "Beverages",
                "Health Drink, Supplement",
                "Horlicks",
                300,
                320,
                "Children (2-5 Yrs)",
                4.2,
                "",
            ],
        ],
    )


@pytest.fixture
def amazon_csv(tmp_path):
    header = [
        "name",
        "main_category",
        "sub_category",
        "image",
        "link",
        "ratings",
        "no_of_ratings",
        "discount_price",
        "actual_price",
        "id",
    ]
    return _write_csv(
        tmp_path / "amz.csv",
        header,
        [
            [
                "Omron Digital Thermometer MC-246 | Fast reading",
                "beauty & health",
                "Health & Personal Care",
                "",
                "",
                4.2,
                100,
                "₹199",
                "₹250",
                "a1",
            ],
            [
                "Harpic Bathroom Cleaner Liquid 1 L",
                "beauty & health",
                "Health & Personal Care",
                "",
                "",
                4.4,
                100,
                "₹340",
                "₹358",
                "a2",
            ],
            [
                "Glucon D Instant Energy Health Drink Nimbu Pani 1kg",
                "beauty & health",
                "Health & Personal Care",
                "",
                "",
                4.3,
                100,
                "",
                "₹399",
                "a3",
            ],
        ],
    )


def test_category_mapping_keeps_only_health_and_care_rows():
    assert bigbasket_category("Beauty & Hygiene", "Health & Medicine", "Antiseptics & Bandages") == "devices"
    assert bigbasket_category("Beauty & Hygiene", "Health & Medicine", "Ayurveda") == "groceries"
    assert bigbasket_category("Beauty & Hygiene", "Skin Care", "Face Cream") == "beauty"
    assert bigbasket_category("Baby Care", "Diapers & Wipes", "Wipes") == "personal-care"
    assert bigbasket_category("Foodgrains, Oil & Masala", "Rice & Rice Products", "Basmati") is None
    assert amazon_category("Omron Digital Thermometer") == "devices"
    assert amazon_category("Harpic Bathroom Cleaner") is None


def test_readers_parse_prices_and_strip_promotions(bigbasket_csv, amazon_csv):
    bb = {item.name: item for item in bigbasket_items(bigbasket_csv)}
    assert set(bb) == {
        "Chyawanprash - Immunity Booster 500 g",
        "Antiseptic Liquid",
        "Neem Soap",
        "Junior Horlicks Health Drink",
    }
    chyawan = bb["Chyawanprash - Immunity Booster 500 g"]
    assert (chyawan.price, chyawan.mrp, chyawan.pack_size) == (210.0, 230.0, "500 g")
    assert chyawan.description == "Classic recipe."

    amz = {item.name: item for item in amazon_items(amazon_csv)}
    assert set(amz) == {
        "Omron Digital Thermometer MC-246",
        "Glucon D Instant Energy Health Drink Nimbu Pani 1kg",
    }
    assert amz["Omron Digital Thermometer MC-246"].price == 199.0
    glucon = amz["Glucon D Instant Energy Health Drink Nimbu Pani 1kg"]
    assert glucon.price == glucon.mrp == 399.0  # no sale price: falls back to MRP


def test_import_is_additive_searchable_and_idempotent(client, db, bigbasket_csv, amazon_csv):
    categories = {c.slug: c.id for c in seed_categories(db).values()}
    db.commit()
    items = list(CURATED_ORS) + bigbasket_items(bigbasket_csv) + amazon_items(amazon_csv)
    added = insert_items(db, items, categories)
    assert added == len(CURATED_ORS) + 4 + 2
    assert insert_items(db, items, categories) == 0  # second run adds nothing

    ors = client.get("/api/medicines", params={"q": "ors juice"}).json()  # falls back to "ors"
    names = {m["medicine_name"] for m in ors["items"]}
    assert "Electral Powder Orange" in names and "ORSL Plus Electrolyte Drink Orange" in names
    assert all(not m["prescription_required"] for m in ors["items"])

    devices = client.get("/api/medicines", params={"category": "devices"}).json()
    assert {m["medicine_name"] for m in devices["items"]} >= {
        "Antiseptic Liquid",
        "Omron Digital Thermometer MC-246",
    }


def test_ors_on_a_prescription_matches_ors_powders(db):
    categories = {c.slug: c.id for c in seed_categories(db).values()}
    db.commit()
    insert_items(db, list(CURATED_ORS), categories)
    outcome = match_name("ORS", load_catalogue(db))
    assert outcome.status in {MatchStatus.EXACT, MatchStatus.POSSIBLE}
    assert all(c["formulation"] == "powder" for c in outcome.candidates[:3])
    assert "Electrolyte" not in outcome.candidates[0]["medicine_name"]  # drinks are not ORS
