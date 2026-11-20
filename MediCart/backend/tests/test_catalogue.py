def test_categories_include_counts(client, catalogue):
    response = client.get("/api/categories")
    assert response.status_code == 200
    by_slug = {c["slug"]: c for c in response.json()}
    assert by_slug["general"]["medicine_count"] == 2
    assert by_slug["specialist"]["medicine_count"] == 2


def test_search_by_name_brand_and_generic(client, catalogue):
    assert client.get("/api/medicines", params={"q": "paracet"}).json()["total"] == 1
    assert client.get("/api/medicines/search", params={"q": "allerfree"}).json()["total"] == 1
    assert client.get("/api/medicines", params={"q": "hydrochloride"}).json()["total"] == 2
    assert client.get("/api/medicines", params={"q": "nothing-here"}).json()["total"] == 0


def test_filters_and_sorting(client, catalogue):
    specialist = client.get("/api/medicines", params={"category": "specialist"}).json()
    assert {m["medicine_name"] for m in specialist["items"]} == {"Amoxicillin 500", "Metformin 500"}

    cheap = client.get("/api/medicines", params={"max_price": 20}).json()
    assert {m["medicine_name"] for m in cheap["items"]} == {"Paracetamol 500", "Cetirizine 10"}

    rx_only = client.get("/api/medicines", params={"prescription_required": "true"}).json()
    assert all(m["prescription_required"] for m in rx_only["items"]) and rx_only["total"] == 2

    by_price = client.get("/api/medicines", params={"sort": "price_desc"}).json()["items"]
    prices = [m["products"][0]["price"] for m in by_price]
    assert prices == sorted(prices, reverse=True)


def test_detail_hides_inactive_products_and_404s_inactive_medicine(client, db, catalogue):
    medicine = catalogue["paracetamol"]
    detail = client.get(f"/api/medicines/{medicine.id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["products"][0]["in_stock"] is True
    assert body["products"][0]["discount_percent"] == 16
    assert body["category"]["slug"] == "general"

    medicine.is_active = False
    db.commit()
    assert client.get(f"/api/medicines/{medicine.id}").status_code == 404
    assert client.get("/api/medicines", params={"q": "paracet"}).json()["total"] == 0


def test_in_stock_filter(client, db, catalogue):
    product = catalogue["cetirizine"].products[0]
    product.inventory.available_quantity = 0
    db.commit()
    names = {
        m["medicine_name"] for m in client.get("/api/medicines", params={"in_stock": "true"}).json()["items"]
    }
    assert "Cetirizine 10" not in names
    assert "Paracetamol 500" in names


def test_home_feed_shape(client, catalogue):
    body = client.get("/api/home").json()
    assert {"categories", "featured", "deals", "popular"} <= set(body)
    assert all(not m["prescription_required"] for m in body["featured"])
