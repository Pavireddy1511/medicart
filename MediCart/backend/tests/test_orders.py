import pytest

from tests.conftest import add_address


def _fill_cart(client, headers, product_id, quantity=2):
    response = client.post(
        "/api/cart/items", headers=headers, json={"product_id": product_id, "quantity": quantity}
    )
    assert response.status_code == 201, response.text


def test_place_cod_order_decrements_stock_and_clears_cart(client, db, customer, catalogue):
    headers = customer["headers"]
    product = catalogue["paracetamol"].products[0]
    _fill_cart(client, headers, product.id, 3)
    address_id = add_address(client, headers)

    response = client.post(
        "/api/orders", headers=headers, json={"address_id": address_id, "payment_method": "cod"}
    )
    assert response.status_code == 201, response.text
    order = response.json()
    assert order["order_status"] == "placed"
    assert order["payment_status"] == "cod_pending"
    assert order["subtotal"] == 55.5 and order["delivery_charge"] == 40.0 and order["order_total"] == 95.5
    assert order["items"][0]["quantity"] == 3
    assert order["address_snapshot"]["city"] == "Hyderabad"
    assert order["order_number"].startswith("MC")

    db.expire_all()
    assert db.get(type(product), product.id).inventory.available_quantity == 47
    assert client.get("/api/cart", headers=headers).json()["items"] == []

    listing = client.get("/api/orders", headers=headers).json()
    assert len(listing) == 1 and listing[0]["item_count"] == 3


def test_simulated_online_payment_is_marked_paid(client, customer, catalogue):
    headers = customer["headers"]
    _fill_cart(client, headers, catalogue["paracetamol"].products[0].id)
    address_id = add_address(client, headers)
    order = client.post(
        "/api/orders", headers=headers, json={"address_id": address_id, "payment_method": "simulated_online"}
    ).json()
    assert order["payment_status"] == "paid"
    assert order["payments"][0]["transaction_reference"].startswith("SIM-")


def test_empty_cart_and_foreign_address_rejected(client, customer, catalogue):
    headers = customer["headers"]
    address_id = add_address(client, headers)
    empty = client.post(
        "/api/orders", headers=headers, json={"address_id": address_id, "payment_method": "cod"}
    )
    assert empty.status_code == 422 and empty.json()["error"]["code"] == "cart_empty"

    _fill_cart(client, headers, catalogue["paracetamol"].products[0].id)
    missing = client.post("/api/orders", headers=headers, json={"address_id": 9999, "payment_method": "cod"})
    assert missing.status_code == 404


def test_rx_item_requires_confirmed_prescription(client, customer, catalogue):
    headers = customer["headers"]
    _fill_cart(client, headers, catalogue["amoxicillin"].products[0].id, 1)
    address_id = add_address(client, headers)
    response = client.post(
        "/api/orders", headers=headers, json={"address_id": address_id, "payment_method": "cod"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "prescription_required"


def test_stock_revalidated_at_checkout(client, db, customer, catalogue):
    headers = customer["headers"]
    product = catalogue["cetirizine"].products[0]
    _fill_cart(client, headers, product.id, 4)
    product.inventory.available_quantity = 2
    db.commit()
    address_id = add_address(client, headers)
    response = client.post(
        "/api/orders", headers=headers, json={"address_id": address_id, "payment_method": "cod"}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "insufficient_stock"


def test_customer_cancel_restocks_and_refunds(client, db, customer, catalogue):
    headers = customer["headers"]
    product = catalogue["paracetamol"].products[0]
    _fill_cart(client, headers, product.id, 2)
    address_id = add_address(client, headers)
    order = client.post(
        "/api/orders", headers=headers, json={"address_id": address_id, "payment_method": "simulated_online"}
    ).json()

    cancelled = client.post(
        f"/api/orders/{order['id']}/cancel", headers=headers, json={"reason": "Changed my mind"}
    )
    assert cancelled.status_code == 200
    body = cancelled.json()
    assert body["order_status"] == "cancelled"
    assert body["payment_status"] == "refunded"
    assert body["can_cancel"] is False
    assert any(p["payment_status"] == "refunded" for p in body["payments"])
    db.expire_all()
    assert db.get(type(product), product.id).inventory.available_quantity == 50

    again = client.post(f"/api/orders/{order['id']}/cancel", headers=headers, json={})
    assert again.status_code == 409


@pytest.mark.parametrize("path", ["processing", "packed", "shipped", "delivered"])
def test_admin_status_flow(client, customer, admin, catalogue, path):
    headers = customer["headers"]
    _fill_cart(client, headers, catalogue["paracetamol"].products[0].id)
    address_id = add_address(client, headers)
    order = client.post(
        "/api/orders", headers=headers, json={"address_id": address_id, "payment_method": "cod"}
    ).json()

    flow = ["processing", "packed", "shipped", "delivered"]
    for status in flow[: flow.index(path) + 1]:
        response = client.patch(
            f"/api/admin/orders/{order['id']}/status", headers=admin["headers"], json={"order_status": status}
        )
        assert response.status_code == 200, response.text
        body = response.json()
    assert body["order_status"] == path
    if path == "shipped":
        assert body["shipment"]["tracking_reference"]
        assert body["shipment"]["shipment_status"] == "in_transit"
    if path == "delivered":
        assert body["payment_status"] == "paid"  # COD collected
        assert body["can_cancel"] is False


def test_admin_can_mark_delivered_directly_and_customer_sees_it(client, customer, admin, catalogue):
    headers = customer["headers"]
    _fill_cart(client, headers, catalogue["paracetamol"].products[0].id)
    address_id = add_address(client, headers)
    order = client.post(
        "/api/orders", headers=headers, json={"address_id": address_id, "payment_method": "cod"}
    ).json()
    assert order["order_status"] == "placed"
    assert "delivered" in order["allowed_next_statuses"]
    assert "cancelled" in order["allowed_next_statuses"]

    delivered = client.patch(
        f"/api/admin/orders/{order['id']}/status",
        headers=admin["headers"],
        json={"order_status": "delivered"},
    )
    assert delivered.status_code == 200, delivered.text
    body = delivered.json()
    assert body["order_status"] == "delivered"
    assert body["payment_status"] == "paid"  # COD collected on delivery
    assert body["shipment"]["shipment_status"] == "delivered"
    assert body["shipment"]["tracking_reference"]
    assert body["delivered_at"] is not None
    assert body["allowed_next_statuses"] == []

    history = client.get("/api/orders", headers=headers).json()
    assert history[0]["order_status"] == "delivered" and history[0]["delivered_at"] is not None
    admin_list = client.get("/api/admin/orders", headers=admin["headers"]).json()["items"]
    assert admin_list[0]["delivered_at"] is not None and admin_list[0]["allowed_next_statuses"] == []


def test_final_and_backward_transitions_rejected(client, customer, admin, catalogue):
    headers = customer["headers"]
    _fill_cart(client, headers, catalogue["paracetamol"].products[0].id)
    address_id = add_address(client, headers)
    order = client.post(
        "/api/orders", headers=headers, json={"address_id": address_id, "payment_method": "cod"}
    ).json()
    url = f"/api/admin/orders/{order['id']}/status"
    assert client.patch(url, headers=admin["headers"], json={"order_status": "shipped"}).status_code == 200

    backwards = client.patch(url, headers=admin["headers"], json={"order_status": "processing"})
    assert backwards.status_code == 409
    assert backwards.json()["error"]["code"] == "invalid_transition"
    assert backwards.json()["error"]["details"]["allowed"] == ["delivered"]  # no cancelling once shipped

    client.patch(url, headers=admin["headers"], json={"order_status": "delivered"})
    final = client.patch(url, headers=admin["headers"], json={"order_status": "cancelled"})
    assert final.status_code == 409 and final.json()["error"]["details"]["allowed"] == []


def test_customer_cannot_read_someone_elses_order(client, customer, catalogue):
    headers = customer["headers"]
    _fill_cart(client, headers, catalogue["paracetamol"].products[0].id)
    address_id = add_address(client, headers)
    order = client.post(
        "/api/orders", headers=headers, json={"address_id": address_id, "payment_method": "cod"}
    ).json()

    other = client.post(
        "/api/auth/register",
        json={
            "full_name": "Other",
            "mobile_number": "9123456789",
            "password": "Secret123",
            "confirm_password": "Secret123",
        },
    ).json()
    response = client.get(
        f"/api/orders/{order['id']}", headers={"Authorization": f"Bearer {other['access_token']}"}
    )
    assert response.status_code == 404
