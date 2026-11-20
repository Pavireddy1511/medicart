from tests.conftest import auth_headers


def test_cart_requires_auth(client):
    assert client.get("/api/cart").status_code == 401


def test_add_update_remove_items(client, customer, catalogue):
    product = catalogue["paracetamol"].products[0]
    headers = customer["headers"]

    add = client.post("/api/cart/items", headers=headers, json={"product_id": product.id, "quantity": 2})
    assert add.status_code == 201
    cart = add.json()
    assert cart["item_count"] == 2
    assert cart["subtotal"] == 37.0
    assert cart["delivery_charge"] == 40.0
    assert cart["total"] == 77.0
    assert cart["requires_prescription"] is False

    # adding the same product merges quantities
    cart = client.post(
        "/api/cart/items", headers=headers, json={"product_id": product.id, "quantity": 1}
    ).json()
    assert len(cart["items"]) == 1 and cart["items"][0]["quantity"] == 3

    item_id = cart["items"][0]["id"]
    cart = client.put(f"/api/cart/items/{item_id}", headers=headers, json={"quantity": 5}).json()
    assert cart["items"][0]["quantity"] == 5

    cart = client.delete(f"/api/cart/items/{item_id}", headers=headers).json()
    assert cart["items"] == [] and cart["total"] == 0.0


def test_stock_limit_enforced(client, customer, catalogue):
    product = catalogue["cetirizine"].products[0]  # stock 5
    response = client.post(
        "/api/cart/items", headers=customer["headers"], json={"product_id": product.id, "quantity": 6}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "insufficient_stock"


def test_free_delivery_threshold_and_rx_flag(client, customer, catalogue):
    headers = customer["headers"]
    amox = catalogue["amoxicillin"].products[0]  # 82.00, rx
    cart = client.post("/api/cart/items", headers=headers, json={"product_id": amox.id, "quantity": 7}).json()
    assert cart["subtotal"] == 574.0
    assert cart["delivery_charge"] == 0.0
    assert cart["requires_prescription"] is True


def test_cart_persists_across_logins(client, customer, catalogue):
    product = catalogue["paracetamol"].products[0]
    client.post(
        "/api/cart/items", headers=customer["headers"], json={"product_id": product.id, "quantity": 1}
    )
    client.post("/api/auth/logout", headers=customer["headers"])

    login = client.post(
        "/api/auth/login", json={"mobile_number": "9876543210", "password": "Secret123"}
    ).json()
    cart = client.get("/api/cart", headers=auth_headers(login["access_token"])).json()
    assert cart["item_count"] == 1
    assert cart["items"][0]["product"]["medicine_name"] == "Paracetamol 500"


def test_other_users_items_are_not_visible(client, customer, catalogue):
    product = catalogue["paracetamol"].products[0]
    cart = client.post("/api/cart/items", headers=customer["headers"], json={"product_id": product.id}).json()
    item_id = cart["items"][0]["id"]

    other = client.post(
        "/api/auth/register",
        json={
            "full_name": "Other",
            "mobile_number": "9123456789",
            "password": "Secret123",
            "confirm_password": "Secret123",
        },
    ).json()
    response = client.delete(f"/api/cart/items/{item_id}", headers=auth_headers(other["access_token"]))
    assert response.status_code == 404
