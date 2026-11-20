from tests.conftest import auth_headers, register


def test_register_returns_tokens_and_customer_role(client):
    data = register(client)
    assert data["token_type"] == "bearer"
    assert data["access_token"] and data["refresh_token"]
    assert data["user"]["role"] == "customer"
    assert data["user"]["mobile_number"] == "9876543210"


def test_register_normalises_mobile_with_country_code(client):
    data = register(client, mobile="+91 98765 43210")
    assert data["user"]["mobile_number"] == "9876543210"


def test_duplicate_mobile_rejected(client):
    register(client)
    response = client.post(
        "/api/auth/register",
        json={
            "full_name": "Someone Else",
            "mobile_number": "9876543210",
            "password": "Another123",
            "confirm_password": "Another123",
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "mobile_taken"


def test_weak_password_and_bad_mobile_rejected(client):
    response = client.post(
        "/api/auth/register",
        json={
            "full_name": "Weak",
            "mobile_number": "12345",
            "password": "short",
            "confirm_password": "short",
        },
    )
    assert response.status_code == 422
    fields = {f["field"] for f in response.json()["error"]["details"]}
    assert "mobile_number" in fields
    assert "password" in fields


def test_login_success_and_wrong_password(client):
    register(client)
    ok = client.post("/api/auth/login", json={"mobile_number": "9876543210", "password": "Secret123"})
    assert ok.status_code == 200
    bad = client.post("/api/auth/login", json={"mobile_number": "9876543210", "password": "Wrong123"})
    assert bad.status_code == 401
    assert bad.json()["error"]["code"] == "invalid_credentials"
    unknown = client.post("/api/auth/login", json={"mobile_number": "9111111111", "password": "Secret123"})
    assert unknown.status_code == 401


def test_me_requires_token(client):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers=auth_headers("garbage")).status_code == 401
    data = register(client)
    me = client.get("/api/auth/me", headers=auth_headers(data["access_token"]))
    assert me.status_code == 200
    assert me.json()["id"] == data["user"]["id"]


def test_refresh_token_issues_new_pair(client):
    data = register(client)
    response = client.post("/api/auth/refresh", json={"refresh_token": data["refresh_token"]})
    assert response.status_code == 200
    assert response.json()["access_token"]
    # an access token is not accepted as a refresh token
    bad = client.post("/api/auth/refresh", json={"refresh_token": data["access_token"]})
    assert bad.status_code == 401


def test_customer_cannot_access_admin_or_pharmacist_routes(client, customer):
    assert client.get("/api/admin/dashboard", headers=customer["headers"]).status_code == 403
    assert client.get("/api/pharmacist/verification-requests", headers=customer["headers"]).status_code == 403


def test_pharmacist_cannot_access_admin_routes(client, pharmacist):
    assert (
        client.get("/api/pharmacist/verification-requests", headers=pharmacist["headers"]).status_code == 200
    )
    assert client.get("/api/admin/dashboard", headers=pharmacist["headers"]).status_code == 403


def test_admin_can_access_dashboard_and_promote_users(client, admin, customer):
    assert client.get("/api/admin/dashboard", headers=admin["headers"]).status_code == 200
    response = client.patch(
        f"/api/admin/users/{customer['user']['id']}",
        headers=admin["headers"],
        json={"role": "pharmacist"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "pharmacist"


def test_registration_cannot_choose_role(client):
    response = client.post(
        "/api/auth/register",
        json={
            "full_name": "Sneaky",
            "mobile_number": "9876500000",
            "password": "Secret123",
            "confirm_password": "Secret123",
            "role": "admin",
        },
    )
    assert response.status_code == 201
    assert response.json()["user"]["role"] == "customer"


def test_change_password_and_profile_update(client, customer):
    response = client.put(
        "/api/auth/me", headers=customer["headers"], json={"full_name": "Renamed User", "email": "a@b.com"}
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "Renamed User"
    change = client.post(
        "/api/auth/change-password",
        headers=customer["headers"],
        json={
            "current_password": "Secret123",
            "new_password": "NewPass456",
            "confirm_password": "NewPass456",
        },
    )
    assert change.status_code == 204
    login = client.post("/api/auth/login", json={"mobile_number": "9876543210", "password": "NewPass456"})
    assert login.status_code == 200


def test_deactivated_user_is_blocked(client, admin, customer):
    client.patch(
        f"/api/admin/users/{customer['user']['id']}", headers=admin["headers"], json={"is_active": False}
    )
    assert client.get("/api/auth/me", headers=customer["headers"]).status_code == 403
    login = client.post("/api/auth/login", json={"mobile_number": "9876543210", "password": "Secret123"})
    assert login.status_code == 403
