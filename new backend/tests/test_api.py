import zlib

from fastapi.testclient import TestClient

from app import main


client = TestClient(main.app)


def png_bytes(trailing: bytes = b"") -> bytes:
    def chunk(kind: bytes, body: bytes) -> bytes:
        return len(body).to_bytes(4, "big") + kind + body + (zlib.crc32(kind + body) & 0xFFFFFFFF).to_bytes(4, "big")

    ihdr = (1).to_bytes(4, "big") + (1).to_bytes(4, "big") + bytes([8, 2, 0, 0, 0])
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00")) + chunk(b"IEND", b"") + trailing


def register(email: str = "person@example.com", password: str = "some-strong-password") -> dict:
    response = client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert response.status_code == 201, response.text
    return response.json()


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_health_is_public() -> None:
    response = client.get("/health")
    assert response.status_code == 200


def test_register_login_me_and_logout() -> None:
    credentials = register()
    token = credentials["access_token"]
    assert client.get("/api/v1/auth/me", headers=headers(token)).json()["email"] == "person@example.com"

    logged_in = client.post(
        "/api/v1/auth/login", json={"email": "person@example.com", "password": "some-strong-password"}
    )
    assert logged_in.status_code == 200
    assert client.post("/api/v1/auth/logout", headers=headers(token)).status_code == 204
    assert client.get("/api/v1/auth/me", headers=headers(token)).status_code == 401


def test_auth_rejects_bad_password_and_weak_password() -> None:
    register()
    bad = client.post("/api/v1/auth/login", json={"email": "person@example.com", "password": "wrong"})
    assert bad.status_code == 401
    weak = client.post("/api/v1/auth/register", json={"email": "other@example.com", "password": "short"})
    assert weak.status_code == 422


def test_upload_png_reports_structural_screening_only() -> None:
    token = register()["access_token"]
    response = client.post(
        "/api/v1/documents", headers=headers(token), files={"file": ("receipt.png", png_bytes(), "image/png")}
    )
    assert response.status_code == 202, response.text
    body = response.json()
    result = client.get(f"/api/v1/verifications/{body['verification_id']}", headers=headers(token)).json()
    assert result["document_type"] == "image/png"
    assert result["risk_level"] == "INSUFFICIENT_EVIDENCE"
    assert result["risk_score"] is None


def test_png_trailing_data_emits_signal_but_not_counterfeit_verdict() -> None:
    token = register()["access_token"]
    response = client.post(
        "/api/v1/documents", headers=headers(token), files={"file": ("sample.png", png_bytes(b"extra"), "image/png")}
    )
    assert response.status_code == 202
    verification_id = response.json()["verification_id"]
    result = client.get(f"/api/v1/verifications/{verification_id}", headers=headers(token)).json()
    assert "PNG_TRAILING_DATA" in {finding["rule_id"] for finding in result["findings"]}
    assert result["risk_level"] == "INSUFFICIENT_EVIDENCE"


def test_unsupported_signature_is_rejected() -> None:
    token = register()["access_token"]
    response = client.post(
        "/api/v1/documents", headers=headers(token), files={"file": ("thing.exe", b"MZbad", "image/png")}
    )
    assert response.status_code == 415


def test_tenant_isolation_prevents_document_access() -> None:
    token_one = register("one@example.com")["access_token"]
    uploaded = client.post(
        "/api/v1/documents", headers=headers(token_one), files={"file": ("sample.png", png_bytes(), "image/png")}
    )
    token_two = register("two@example.com")["access_token"]
    response = client.get(f"/api/v1/documents/{uploaded.json()['document_id']}", headers=headers(token_two))
    assert response.status_code == 404


def test_duplicate_registration_rejected() -> None:
    register()
    response = client.post(
        "/api/v1/auth/register", json={"email": "person@example.com", "password": "some-strong-password"}
    )
    assert response.status_code == 409
