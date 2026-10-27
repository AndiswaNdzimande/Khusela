"""TASK-23: Auth – register, duplicate register, login, wrong password, protected route."""


def test_register_success(client):
    resp = client.post("/auth/register", json={"business_name": "Spaza A", "password": "pass1234"})
    assert resp.status_code == 201
    assert resp.json()["business_name"] == "Spaza A"


def test_register_duplicate(client):
    client.post("/auth/register", json={"business_name": "Spaza B", "password": "pass1234"})
    resp = client.post("/auth/register", json={"business_name": "Spaza B", "password": "other123"})
    assert resp.status_code == 409


def test_register_short_password(client):
    resp = client.post("/auth/register", json={"business_name": "Spaza C", "password": "short"})
    assert resp.status_code == 422


def test_login_success(client):
    client.post("/auth/register", json={"business_name": "Spaza D", "password": "pass1234"})
    resp = client.post("/auth/login", json={"business_name": "Spaza D", "password": "pass1234"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_login_wrong_password(client):
    client.post("/auth/register", json={"business_name": "Spaza E", "password": "pass1234"})
    resp = client.post("/auth/login", json={"business_name": "Spaza E", "password": "wrongpass"})
    assert resp.status_code == 401


def test_protected_route_no_token(client):
    """N4 fix: missing token must return 401, not 403."""
    resp = client.post("/check")
    assert resp.status_code == 401


def test_protected_route_bad_token(client):
    resp = client.post(
        "/check",
        headers={"Authorization": "Bearer not.a.real.token"},
    )
    assert resp.status_code == 401


def test_api_prefix_login(client):
    """N3 fix: /api/auth/login must work as well as /auth/login."""
    client.post("/auth/register", json={"business_name": "Spaza F", "password": "pass1234"})
    resp = client.post("/api/auth/login", json={"business_name": "Spaza F", "password": "pass1234"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()
