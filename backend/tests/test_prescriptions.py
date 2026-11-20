import io

import cv2
import numpy as np
import pytest

from app.ai.groq_client import GroqUnavailable
from app.computer_vision.ocr.base import OCREngine, OCRLine, OCRResult
from app.core.config import get_settings
from tests.conftest import add_address


def _png(lines: list[str]) -> bytes:
    image = np.full((400, 900, 3), 255, dtype=np.uint8)
    for i, text in enumerate(lines):
        cv2.putText(image, text, (20, 60 + i * 55), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 0, 0), 2)
    ok, buffer = cv2.imencode(".png", image)
    assert ok
    return buffer.tobytes()


class FakeEngine(OCREngine):
    name = "fake"

    def __init__(self, lines):
        self._lines = lines

    def is_available(self):
        return True

    def recognise(self, image):
        return OCRResult(
            engine=self.name,
            lines=[
                OCRLine(
                    text=t,
                    confidence=0.93,
                    box=[[0, i * 10], [10, i * 10], [10, i * 10 + 8], [0, i * 10 + 8]],
                )
                for i, t in enumerate(self._lines)
            ],
        )


@pytest.fixture
def strict_review(monkeypatch):
    """Run a test with REQUIRE_PHARMACIST_APPROVAL switched on."""
    monkeypatch.setattr(get_settings(), "require_pharmacist_approval", True)


@pytest.fixture
def fake_ocr(monkeypatch):
    def _install(lines):
        monkeypatch.setattr(
            "app.services.prescription_service.get_engine", lambda settings: FakeEngine(lines)
        )

    return _install


def _upload(client, headers, content: bytes, filename="rx.png", content_type="image/png", **form):
    return client.post(
        "/api/prescriptions/analyse",
        headers=headers,
        files={"file": (filename, io.BytesIO(content), content_type)},
        data=form,
    )


def test_rejects_wrong_file_types(client, customer):
    txt = _upload(
        client, customer["headers"], b"hello world", filename="notes.txt", content_type="text/plain"
    )
    assert txt.status_code == 422
    assert txt.json()["error"]["code"] == "unsupported_file_type"

    disguised = _upload(client, customer["headers"], b"not really an image", filename="x.png")
    assert disguised.status_code == 422

    empty = _upload(client, customer["headers"], b"", filename="x.png")
    assert empty.status_code == 422


def test_rejects_oversized_upload(client, customer, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    big = _png(["Paracetamol"]) + b"\0" * (1024 * 1024 + 10)
    response = _upload(client, customer["headers"], big)
    assert response.status_code == 413


def test_requires_login(client):
    assert _upload(client, {}, _png(["x"])).status_code == 401


def test_analyse_without_ocr_engine_still_creates_reviewable_prescription(client, customer, catalogue):
    response = _upload(client, customer["headers"], _png(["Paracetamol 500"]))
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["processing"]["ocr_available"] is False
    assert body["prescription"]["items"] == []
    assert body["prescription"]["ai_review_status"] == "skipped"
    assert any("No OCR engine" in n for n in body["processing"]["notes"])
    assert len(body["preview_images"]) == 1 and body["preview_images"][0].startswith(
        "data:image/jpeg;base64,"
    )
    assert body["prescription"]["original_image_retained"] is False


def test_pipeline_matches_catalogue_and_flags_uncertainty(client, customer, catalogue, fake_ocr):
    fake_ocr(
        [
            "Dr. Demo Clinic",
            "Rx",
            "Tab Paracetamol 500mg 1-0-1 x 5 days",
            "Cap Amoxicilin 500 mg TDS 7 days",
            "Tab Unknownium 20mg OD",
        ]
    )
    response = _upload(client, customer["headers"], _png(["ignored"]), document_type="printed")
    assert response.status_code == 201, response.text
    body = response.json()
    rx = body["prescription"]
    assert body["processing"]["ocr_engine"] == "fake"
    assert rx["document_type"] == "printed"
    assert rx["ai_review_status"] == "unavailable"  # Groq not configured in tests
    assert rx["user_confirmation_status"] == "pending"
    assert rx["show_handwriting_disclaimer"] is False
    assert "Paracetamol 500mg" in body["extracted_text"]

    by_name = {i["extracted_name"]: i for i in rx["items"]}
    assert set(by_name) == {"Paracetamol", "Amoxicilin", "Unknownium"}

    pcm = by_name["Paracetamol"]
    assert pcm["match_status"] == "exact"
    assert pcm["matched_medicine"]["id"] == catalogue["paracetamol"].id
    assert pcm["frequency_text"] == "1-0-1"
    assert pcm["can_add_to_cart"] is False  # nothing is added before confirmation

    amox = by_name["Amoxicilin"]
    assert amox["match_status"] == "possible"
    assert amox["matched_medicine"] is None
    assert amox["candidates"][0]["medicine_name"] == "Amoxicillin 500"

    unknown = by_name["Unknownium"]
    assert unknown["match_status"] == "none"
    assert "match" in unknown["uncertain_fields"]
    assert any("could not be matched" in w for w in rx["warnings"])


def test_handwritten_hint_shows_disclaimer(client, customer, catalogue, fake_ocr):
    fake_ocr(["Tab Paracetamol 500mg"])
    body = _upload(client, customer["headers"], _png(["x"]), document_type="handwritten").json()
    assert body["prescription"]["document_type"] == "handwritten"
    assert body["prescription"]["show_handwriting_disclaimer"] is True
    assert "Handwritten prescription recognition" in body["prescription"]["handwriting_disclaimer"]


def test_groq_failure_falls_back_to_rules(client, customer, catalogue, fake_ocr, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "groq_api_key", "test-key")
    monkeypatch.setattr(settings, "groq_model", "test-model")

    def _boom(text, settings):
        raise GroqUnavailable("timeout", "Groq did not answer in time")

    monkeypatch.setattr("app.ai.structuring.structure_with_groq", _boom)
    fake_ocr(["Tab Paracetamol 500mg 1-0-1"])
    body = _upload(client, customer["headers"], _png(["x"])).json()
    assert body["prescription"]["ai_review_status"] == "fallback"
    assert body["processing"]["ai_source"] == "fallback"
    assert any("Groq did not answer" in n for n in body["processing"]["notes"])
    assert body["prescription"]["items"][0]["extracted_name"] == "Paracetamol"


def test_groq_success_path_is_guarded(client, customer, catalogue, fake_ocr, monkeypatch):
    from app.ai.schemas import ExtractedMedicine, StructuredPrescription

    settings = get_settings()
    monkeypatch.setattr(settings, "groq_api_key", "test-key")
    monkeypatch.setattr(settings, "groq_model", "test-model")

    def _fake_groq(text, settings):
        return (
            StructuredPrescription(
                medicines=[
                    ExtractedMedicine(
                        extracted_name="Paracetamol",
                        strength="500 mg",
                        frequency_text="1-0-1",
                        uncertain_fields=[],
                        requires_review=False,
                    ),
                    ExtractedMedicine(extracted_name="Atorvastatin", strength="10 mg", requires_review=False),
                ],
                overall_review_required=False,
            ),
            "test-model",
        )

    monkeypatch.setattr("app.ai.structuring.structure_with_groq", _fake_groq)
    fake_ocr(["Tab Paracetamol 500mg 1-0-1"])
    body = _upload(client, customer["headers"], _png(["x"])).json()
    rx = body["prescription"]
    assert rx["ai_review_status"] == "completed"
    assert rx["ai_model"] == "test-model"
    invented = next(i for i in rx["items"] if i["extracted_name"] == "Atorvastatin")
    assert "extracted_name" in invented["uncertain_fields"]
    assert invented["strength_text"] is None
    assert invented["uncertainty_status"] == "uncertain"


def _analysed(client, customer, fake_ocr, lines):
    fake_ocr(lines)
    return _upload(client, customer["headers"], _png(["x"]), document_type="printed").json()["prescription"]


def test_confirm_flow_and_pharmacist_gate(client, customer, pharmacist, catalogue, fake_ocr, strict_review):
    rx = _analysed(client, customer, fake_ocr, ["Tab Paracetamol 500mg 1-0-1", "Cap Amoxicilin 500mg TDS"])
    items = {i["extracted_name"]: i for i in rx["items"]}
    amox = items["Amoxicilin"]

    confirm = client.post(
        "/api/prescriptions/confirm",
        headers=customer["headers"],
        json={
            "prescription_id": rx["id"],
            "items": [
                {
                    "item_id": items["Paracetamol"]["id"],
                    "extracted_name": "Paracetamol",
                    "strength_text": "500 mg",
                    "matched_medicine_id": catalogue["paracetamol"].id,
                    "included": True,
                },
                {
                    "item_id": amox["id"],
                    "extracted_name": "Amoxicillin",
                    "strength_text": "500 mg",
                    "matched_medicine_id": catalogue["amoxicillin"].id,
                    "included": True,
                },
            ],
            "customer_notes": "Please check the antibiotic",
        },
    )
    assert confirm.status_code == 200, confirm.text
    body = confirm.json()
    assert body["user_confirmation_status"] == "confirmed"
    assert body["pharmacist_verification_status"] == "pending"
    by_name = {i["extracted_name"]: i for i in body["items"]}
    assert by_name["Paracetamol"]["can_add_to_cart"] is True
    assert by_name["Amoxicillin"]["can_add_to_cart"] is False
    assert by_name["Amoxicillin"]["blocked_reason"] == "Awaiting pharmacist verification"
    assert by_name["Amoxicillin"]["user_edited"] is True

    # the customer cannot approve their own prescription
    self_approve = client.post(
        "/api/pharmacist/verification",
        headers=customer["headers"],
        json={"prescription_id": rx["id"], "status": "approved"},
    )
    assert self_approve.status_code == 403

    queue = client.get("/api/pharmacist/verification-requests", headers=pharmacist["headers"]).json()
    assert [q["prescription_id"] for q in queue] == [rx["id"]]
    assert queue[0]["rx_item_count"] == 1
    assert queue[0]["customer_mobile_masked"].endswith("3210") and queue[0][
        "customer_mobile_masked"
    ].startswith("*")

    detail = client.get(
        f"/api/pharmacist/verification-requests/{rx['id']}", headers=pharmacist["headers"]
    ).json()
    assert detail["original_image_retained"] is False
    assert "Paracetamol" in detail["extracted_text"]

    needs_note = client.post(
        "/api/pharmacist/verification",
        headers=pharmacist["headers"],
        json={"prescription_id": rx["id"], "status": "rejected"},
    )
    assert needs_note.status_code == 422

    approved = client.post(
        "/api/pharmacist/verification",
        headers=pharmacist["headers"],
        json={"prescription_id": rx["id"], "status": "approved", "notes": "Matches the prescription"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["pharmacist_verification_status"] == "approved"
    assert approved.json()["verifications"][0]["pharmacist_name"] == "Pharmacist"

    after = client.get(f"/api/prescriptions/{rx['id']}", headers=customer["headers"]).json()
    assert all(i["can_add_to_cart"] for i in after["items"])

    twice = client.post(
        "/api/pharmacist/verification",
        headers=pharmacist["headers"],
        json={"prescription_id": rx["id"], "status": "rejected", "notes": "x"},
    )
    assert twice.status_code == 409


def test_order_waits_for_verification_then_moves_on(
    client, customer, pharmacist, catalogue, fake_ocr, strict_review
):
    rx = _analysed(client, customer, fake_ocr, ["Cap Amoxicillin 500mg TDS"])
    item = rx["items"][0]
    assert item["match_status"] == "exact"
    client.post(
        "/api/prescriptions/confirm",
        headers=customer["headers"],
        json={
            "prescription_id": rx["id"],
            "items": [
                {
                    "item_id": item["id"],
                    "extracted_name": "Amoxicillin",
                    "matched_medicine_id": catalogue["amoxicillin"].id,
                }
            ],
        },
    )
    headers = customer["headers"]
    product = catalogue["amoxicillin"].products[0]
    client.post("/api/cart/items", headers=headers, json={"product_id": product.id, "quantity": 1})
    address_id = add_address(client, headers)

    # no prescription_id: the confirmed prescription covering the Rx item is linked automatically
    order = client.post(
        "/api/orders", headers=headers, json={"address_id": address_id, "payment_method": "cod"}
    )
    assert order.status_code == 201, order.text
    assert order.json()["prescription_id"] == rx["id"]
    assert order.json()["order_status"] == "verification_pending"

    client.post(
        "/api/pharmacist/verification",
        headers=pharmacist["headers"],
        json={"prescription_id": rx["id"], "status": "approved", "notes": "ok"},
    )
    moved = client.get(f"/api/orders/{order.json()['id']}", headers=headers).json()
    assert moved["order_status"] == "verified"


def test_rejected_prescription_cancels_waiting_order(
    client, db, customer, pharmacist, catalogue, fake_ocr, strict_review
):
    rx = _analysed(client, customer, fake_ocr, ["Cap Amoxicillin 500mg TDS"])
    item = rx["items"][0]
    client.post(
        "/api/prescriptions/confirm",
        headers=customer["headers"],
        json={
            "prescription_id": rx["id"],
            "items": [
                {
                    "item_id": item["id"],
                    "extracted_name": "Amoxicillin",
                    "matched_medicine_id": catalogue["amoxicillin"].id,
                }
            ],
        },
    )
    headers = customer["headers"]
    product = catalogue["amoxicillin"].products[0]
    client.post("/api/cart/items", headers=headers, json={"product_id": product.id, "quantity": 2})
    address_id = add_address(client, headers)
    order = client.post(
        "/api/orders",
        headers=headers,
        json={"address_id": address_id, "payment_method": "simulated_online", "prescription_id": rx["id"]},
    ).json()

    client.post(
        "/api/pharmacist/verification",
        headers=pharmacist["headers"],
        json={"prescription_id": rx["id"], "status": "rejected", "notes": "Illegible"},
    )
    after = client.get(f"/api/orders/{order['id']}", headers=headers).json()
    assert after["order_status"] == "cancelled"
    assert after["payment_status"] == "refunded"
    db.expire_all()
    assert db.get(type(product), product.id).inventory.available_quantity == 20

    reuse = client.post(
        "/api/orders",
        headers=headers,
        json={"address_id": address_id, "payment_method": "cod", "prescription_id": rx["id"]},
    )
    assert reuse.status_code == 422  # cart is empty now, but a rejected rx would also be refused


def test_manual_items_can_be_added_when_ocr_finds_nothing(client, customer, catalogue, fake_ocr):
    rx = _analysed(client, customer, fake_ocr, ["illegible scribble"])
    body = client.post(
        "/api/prescriptions/confirm",
        headers=customer["headers"],
        json={
            "prescription_id": rx["id"],
            "items": [
                {"item_id": i["id"], "extracted_name": i["extracted_name"], "included": False}
                for i in rx["items"]
            ],
            "new_items": [
                {"extracted_name": "Cetirizine 10", "matched_medicine_id": catalogue["cetirizine"].id}
            ],
        },
    ).json()
    added = [i for i in body["items"] if i["included"]]
    assert len(added) == 1 and added[0]["can_add_to_cart"] is True
    assert body["pharmacist_verification_status"] == "not_required"


def test_admin_sees_prescriptions_and_customer_list_is_scoped(client, customer, admin, catalogue, fake_ocr):
    _analysed(client, customer, fake_ocr, ["Tab Paracetamol 500mg"])
    mine = client.get("/api/prescriptions", headers=customer["headers"]).json()
    assert len(mine) == 1 and mine[0]["item_count"] == 1
    listing = client.get("/api/admin/prescriptions", headers=admin["headers"]).json()
    assert listing["total"] == 1 and listing["items"][0]["customer_name"] == "Test User"
    stats = client.get("/api/admin/dashboard", headers=admin["headers"]).json()["prescriptions"]
    assert stats["total"] == 1 and stats["awaiting_confirmation"] == 1


def _confirm_all(client, customer, rx, catalogue_ids, **extra):
    items = []
    for item in rx["items"]:
        medicine_id = catalogue_ids.get(item["extracted_name"])
        items.append(
            {
                "item_id": item["id"],
                "extracted_name": item["extracted_name"],
                "matched_medicine_id": medicine_id,
                "included": True,
            }
        )
    return client.post(
        "/api/prescriptions/confirm",
        headers=customer["headers"],
        json={"prescription_id": rx["id"], "items": items, **extra},
    )


def test_confirm_adds_items_to_cart_and_orders_without_pharmacist(client, customer, catalogue, fake_ocr):
    rx = _analysed(
        client,
        customer,
        fake_ocr,
        ["Tab Paracetamol 500mg 1-0-1", "Cap Amoxicillin 500mg TDS", "Tab Zyxwvut 5mg"],
    )
    ids = {"Paracetamol": catalogue["paracetamol"].id, "Amoxicillin": catalogue["amoxicillin"].id}
    response = _confirm_all(client, customer, rx, ids)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["pharmacist_verification_status"] == "not_required"
    assert sorted(a["medicine_name"] for a in body["cart_added"]) == ["Amoxicillin 500", "Paracetamol 500"]
    assert [s["name"] for s in body["cart_skipped"]] == ["Zyxwvut"]  # no catalogue match
    rx_item = next(i for i in body["items"] if i["extracted_name"] == "Amoxicillin")
    assert rx_item["can_add_to_cart"] is True  # Rx medicine allowed without a pharmacist

    cart = client.get("/api/cart", headers=customer["headers"]).json()
    assert cart["item_count"] == 2 and cart["requires_prescription"] is True

    # confirming again does not double the cart
    again = _confirm_all(client, customer, rx, ids).json()
    assert again["cart_added"] == []
    assert {s["reason"] for s in again["cart_skipped"]} >= {"Already in your cart"}
    assert client.get("/api/cart", headers=customer["headers"]).json()["item_count"] == 2

    address_id = add_address(client, customer["headers"])
    order = client.post(
        "/api/orders", headers=customer["headers"], json={"address_id": address_id, "payment_method": "cod"}
    )
    assert order.status_code == 201, order.text
    assert order.json()["order_status"] == "placed"
    assert order.json()["prescription_id"] == rx["id"]


def test_optional_review_holds_the_order_until_approved(client, customer, pharmacist, catalogue, fake_ocr):
    rx = _analysed(client, customer, fake_ocr, ["Cap Amoxicillin 500mg TDS"])
    body = _confirm_all(
        client, customer, rx, {"Amoxicillin": catalogue["amoxicillin"].id}, request_pharmacist_review=True
    ).json()
    assert body["pharmacist_verification_status"] == "pending"
    assert len(body["cart_added"]) == 1  # still added; the order waits instead

    address_id = add_address(client, customer["headers"])
    order = client.post(
        "/api/orders", headers=customer["headers"], json={"address_id": address_id, "payment_method": "cod"}
    ).json()
    assert order["order_status"] == "verification_pending"

    client.post(
        "/api/pharmacist/verification",
        headers=pharmacist["headers"],
        json={"prescription_id": rx["id"], "status": "approved", "notes": "ok"},
    )
    assert (
        client.get(f"/api/orders/{order['id']}", headers=customer["headers"]).json()["order_status"]
        == "verified"
    )


def test_confirm_can_skip_adding_to_cart(client, customer, catalogue, fake_ocr):
    rx = _analysed(client, customer, fake_ocr, ["Tab Paracetamol 500mg"])
    body = _confirm_all(
        client, customer, rx, {"Paracetamol": catalogue["paracetamol"].id}, add_to_cart=False
    ).json()
    assert body["cart_added"] == [] and body["cart_skipped"] == []
    assert client.get("/api/cart", headers=customer["headers"]).json()["item_count"] == 0
