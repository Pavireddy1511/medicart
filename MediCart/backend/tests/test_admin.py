from tests.conftest import add_address


def test_admin_lists_and_detail_endpoints(client, admin, customer, catalogue):
    headers = admin["headers"]
    medicines = client.get("/api/admin/medicines", headers=headers)
    assert medicines.status_code == 200, medicines.text
    assert medicines.json()["total"] == 4
    first = medicines.json()["items"][0]
    assert first["products"][0]["inventory"]["available_quantity"] >= 0

    assert (
        client.get(f"/api/admin/medicines/{catalogue['paracetamol'].id}", headers=headers).status_code == 200
    )
    assert client.get("/api/admin/categories", headers=headers).json()[0]["medicine_count"] == 2
    users = client.get("/api/admin/users", headers=headers, params={"role": "customer"}).json()
    assert users["total"] == 1 and users["items"][0]["mobile_number"] == "9876543210"
    assert client.get("/api/admin/orders", headers=headers).json()["total"] == 0
    assert client.get("/api/admin/prescriptions", headers=headers).json()["total"] == 0
    assert client.get("/api/admin/audit-logs", headers=headers).status_code == 200


def test_admin_medicine_lifecycle(client, admin, catalogue):
    headers = admin["headers"]
    created = client.post(
        "/api/admin/medicines",
        headers=headers,
        json={
            "medicine_name": "Ibuprofen 400",
            "generic_name": "Ibuprofen",
            "brand_name": "Flexiban",
            "strength": "400 mg",
            "formulation": "tablet",
            "prescription_required": False,
            "category_id": catalogue["general"].id,
            "is_active": True,
            "products": [
                {"pack_size": "Strip of 10", "mrp": 26, "price": 22, "available_quantity": 15},
                {
                    "pack_size": "Strip of 20",
                    "mrp": 50,
                    "price": 40,
                    "available_quantity": 0,
                    "sku": "IBU-20",
                },
            ],
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    medicine_id = body["id"]
    assert len(body["products"]) == 2
    assert body["products"][0]["sku"].startswith("MC-")
    assert {p["sku"] for p in body["products"]} >= {"IBU-20"}

    # visible in the storefront, only the in-stock pack counts as available
    public = client.get(f"/api/medicines/{medicine_id}").json()
    assert public["products"][0]["in_stock"] is True

    bad_price = client.post(
        f"/api/admin/medicines/{medicine_id}/products",
        headers=headers,
        json={"pack_size": "Strip of 30", "mrp": 10, "price": 12, "available_quantity": 1},
    )
    assert bad_price.status_code == 422

    product_id = body["products"][0]["id"]
    updated = client.put(f"/api/admin/products/{product_id}", headers=headers, json={"price": 20}).json()
    assert any(p["id"] == product_id and p["price"] == 20.0 for p in updated["products"])

    stocked = client.put(
        f"/api/admin/products/{product_id}/inventory",
        headers=headers,
        json={"available_quantity": 3, "batch_number": "B-1"},
    ).json()
    assert next(p for p in stocked["products"] if p["id"] == product_id)["available_quantity"] == 3

    renamed = client.put(
        f"/api/admin/medicines/{medicine_id}",
        headers=headers,
        json={"medicine_name": "Ibuprofen 400 SR", "is_active": False},
    ).json()
    assert renamed["medicine_name"] == "Ibuprofen 400 SR" and renamed["is_active"] is False
    assert client.get(f"/api/medicines/{medicine_id}").status_code == 404

    deleted = client.delete(f"/api/admin/medicines/{medicine_id}", headers=headers)
    assert deleted.status_code == 200 and deleted.json()["message"] == "Medicine deleted"
    assert client.get(f"/api/admin/medicines/{medicine_id}", headers=headers).status_code == 404


def test_medicine_with_orders_is_deactivated_not_deleted(client, admin, customer, catalogue):
    headers = customer["headers"]
    product = catalogue["paracetamol"].products[0]
    client.post("/api/cart/items", headers=headers, json={"product_id": product.id, "quantity": 1})
    address_id = add_address(client, headers)
    assert (
        client.post(
            "/api/orders", headers=headers, json={"address_id": address_id, "payment_method": "cod"}
        ).status_code
        == 201
    )

    deleted = client.delete(f"/api/admin/medicines/{catalogue['paracetamol'].id}", headers=admin["headers"])
    assert deleted.status_code == 200
    assert "deactivated" in deleted.json()["message"]
    still_there = client.get(
        f"/api/admin/medicines/{catalogue['paracetamol'].id}", headers=admin["headers"]
    ).json()
    assert still_there["is_active"] is False
    # order history keeps the snapshot
    orders = client.get("/api/orders", headers=headers).json()
    assert orders[0]["items"][0]["product_name_snapshot"].startswith("Paracetamol")


def test_category_crud_and_guard(client, admin, catalogue):
    headers = admin["headers"]
    created = client.post(
        "/api/admin/categories", headers=headers, json={"name": "Baby care", "icon": "sparkles"}
    )
    assert created.status_code == 201 and created.json()["slug"] == "baby-care"
    category_id = created.json()["id"]

    duplicate = client.post("/api/admin/categories", headers=headers, json={"name": "Baby care"})
    assert duplicate.status_code == 409

    updated = client.put(
        f"/api/admin/categories/{category_id}", headers=headers, json={"sort_order": 9, "is_active": False}
    )
    assert updated.json()["sort_order"] == 9
    assert all(c["slug"] != "baby-care" for c in client.get("/api/categories").json())

    in_use = client.delete(f"/api/admin/categories/{catalogue['general'].id}", headers=headers)
    assert in_use.status_code == 409 and in_use.json()["error"]["code"] == "category_in_use"
    assert client.delete(f"/api/admin/categories/{category_id}", headers=headers).status_code == 204


def test_admin_cannot_demote_or_deactivate_self(client, admin):
    me = admin["user"]["id"]
    assert (
        client.patch(
            f"/api/admin/users/{me}", headers=admin["headers"], json={"role": "customer"}
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/api/admin/users/{me}", headers=admin["headers"], json={"is_active": False}
        ).status_code
        == 403
    )
