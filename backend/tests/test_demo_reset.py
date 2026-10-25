"""Recommendation 1: /api/demo/reset must be locked behind KHUSELA_DEMO_KEY."""
from fastapi.testclient import TestClient

import integration
from main import app

client = TestClient(app)


def test_reset_hidden_when_no_key_configured(monkeypatch):
    monkeypatch.delenv("KHUSELA_DEMO_KEY", raising=False)
    assert client.post("/api/demo/reset").status_code == 404
    # Even a guessed header cannot open it when no key is set.
    assert client.post("/api/demo/reset", headers={"X-Demo-Key": ""}).status_code == 404


def test_reset_rejects_missing_or_wrong_key(monkeypatch):
    monkeypatch.setenv("KHUSELA_DEMO_KEY", "s3cret")
    assert client.post("/api/demo/reset").status_code == 403
    assert client.post("/api/demo/reset", headers={"X-Demo-Key": "nope"}).status_code == 403


def test_reset_works_with_right_key_and_clears_store(monkeypatch):
    monkeypatch.setenv("KHUSELA_DEMO_KEY", "s3cret")
    integration.save_fingerprint("ffffffffffffffff", "sellerA")
    r = client.post("/api/demo/reset", headers={"X-Demo-Key": "s3cret"})
    assert r.status_code == 200
    assert integration.find_duplicates("ffffffffffffffff", "sellerB")["found"] is False
