from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_khusela_register_login_and_check_persists() -> None:
    registered = client.post(
        "/auth/register",
        json={"business_name": "Thabo Sneakers", "password": "password123"},
    )
    assert registered.status_code == 201, registered.text
    token = registered.json()["access_token"]
    assert registered.json()["business_name"] == "Thabo Sneakers"

    login = client.post("/api/auth/login", json={"business_name": "Thabo Sneakers", "password": "password123"})
    assert login.status_code == 200
    token = login.json()["access_token"]

    response = client.post(
        "/api/check",
        headers={"Authorization": f"Bearer {token}"},
        data={
            "expected_amount": "1800.00",
            "expected_recipient": "Thabo Sneakers",
            "expected_reference": "SNK1800",
        },
        files={"image": ("slip.png", b"not-a-real-image", "image/png")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["verdict"] in {"WAIT", "STOP", "MATCH"}
    assert "check_id" in body
    assert body["reasons"]


def test_khusela_duplicate_registration() -> None:
    payload = {"business_name": "Naledi Beauty Hub", "password": "password123"}
    assert client.post("/auth/register", json=payload).status_code == 201
    assert client.post("/auth/register", json=payload).status_code == 409
