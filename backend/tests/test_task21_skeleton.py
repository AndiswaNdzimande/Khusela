"""TASK-21: GET /health and basic app structure."""


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_docs_available(client):
    resp = client.get("/docs")
    assert resp.status_code == 200


def test_check_requires_auth(client):
    resp = client.post("/check")
    assert resp.status_code in (401, 403, 422)
