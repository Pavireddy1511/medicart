import os

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("JWT_SECRET", "unit-test-secret-not-for-production-0123456789")
os.environ.setdefault("OCR_ENGINE", "none")
os.environ.setdefault("GROQ_API_KEY", "")
os.environ.setdefault("GROQ_MODEL", "")

from decimal import Decimal  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import delete  # noqa: E402

from app.database.session import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Inventory, Medicine, MedicineCategory, Product  # noqa: E402
from app.routers.auth import login_limiter, register_limiter  # noqa: E402
from app.routers.prescriptions import analyse_limiter  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def _clean_tables():
    yield
    with SessionLocal() as db:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(delete(table))
        db.commit()
    login_limiter.reset()
    register_limiter.reset()
    analyse_limiter.reset()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def make_medicine(
    db,
    name,
    *,
    category: MedicineCategory,
    price="50.00",
    mrp="60.00",
    stock=10,
    rx=False,
    strength="500 mg",
    brand=None,
    generic=None,
    sku=None,
) -> Medicine:
    medicine = Medicine(
        medicine_name=name,
        generic_name=generic,
        brand_name=brand,
        strength=strength,
        formulation="tablet",
        manufacturer="Test Labs",
        prescription_required=rx,
        category_id=category.id,
        is_active=True,
    )
    product = Product(
        sku=sku or f"SKU-{name.replace(' ', '-').upper()}",
        pack_size="Strip of 10",
        mrp=Decimal(mrp),
        price=Decimal(price),
        is_active=True,
    )
    product.inventory = Inventory(available_quantity=stock)
    medicine.products.append(product)
    db.add(medicine)
    db.commit()
    db.refresh(medicine)
    return medicine


@pytest.fixture
def catalogue(db):
    general = MedicineCategory(name="General", slug="general", sort_order=0)
    specialist = MedicineCategory(name="Specialist", slug="specialist", sort_order=1)
    db.add_all([general, specialist])
    db.commit()
    return {
        "general": general,
        "specialist": specialist,
        "paracetamol": make_medicine(
            db,
            "Paracetamol 500",
            category=general,
            price="18.50",
            mrp="22.00",
            stock=50,
            brand="Febrinil",
            generic="Paracetamol",
        ),
        "cetirizine": make_medicine(
            db,
            "Cetirizine 10",
            category=general,
            price="19.00",
            mrp="28.00",
            stock=5,
            strength="10 mg",
            brand="Allerfree",
            generic="Cetirizine hydrochloride",
        ),
        "amoxicillin": make_medicine(
            db,
            "Amoxicillin 500",
            category=specialist,
            price="82.00",
            mrp="95.00",
            stock=20,
            rx=True,
            brand="Amoxiva",
            generic="Amoxicillin",
        ),
        "metformin": make_medicine(
            db,
            "Metformin 500",
            category=specialist,
            price="36.00",
            mrp="42.00",
            stock=30,
            rx=True,
            brand="Glucomet",
            generic="Metformin hydrochloride",
        ),
    }


def register(client, mobile="9876543210", password="Secret123", name="Test User"):
    response = client.post(
        "/api/auth/register",
        json={
            "full_name": name,
            "mobile_number": mobile,
            "password": password,
            "confirm_password": password,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def customer(client):
    data = register(client)
    return {
        "token": data["access_token"],
        "headers": auth_headers(data["access_token"]),
        "user": data["user"],
    }


def promote(db, user_id: int, role: str) -> None:
    from app.models import User

    user = db.get(User, user_id)
    user.role = role
    db.commit()


@pytest.fixture
def admin(client, db):
    data = register(client, mobile="9000000001", name="Admin")
    promote(db, data["user"]["id"], "admin")
    login = client.post(
        "/api/auth/login", json={"mobile_number": "9000000001", "password": "Secret123"}
    ).json()
    return {
        "token": login["access_token"],
        "headers": auth_headers(login["access_token"]),
        "user": login["user"],
    }


@pytest.fixture
def pharmacist(client, db):
    data = register(client, mobile="9000000002", name="Pharmacist")
    promote(db, data["user"]["id"], "pharmacist")
    login = client.post(
        "/api/auth/login", json={"mobile_number": "9000000002", "password": "Secret123"}
    ).json()
    return {
        "token": login["access_token"],
        "headers": auth_headers(login["access_token"]),
        "user": login["user"],
    }


def add_address(client, headers) -> int:
    response = client.post(
        "/api/addresses",
        headers=headers,
        json={
            "recipient_name": "Test User",
            "mobile_number": "9876543210",
            "house_building": "12",
            "street": "Main Street",
            "city": "Hyderabad",
            "state": "Telangana",
            "pincode": "500001",
            "address_type": "home",
            "is_default": True,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]
