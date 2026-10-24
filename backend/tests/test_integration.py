"""TASK-05: end-to-end checks of integration.check_payment and POST /check.

Runs every synthetic screenshot in tests/fixtures/manifest.csv through the
whole pipeline, in submission order, and compares with the manifest.

Skipped automatically when Tesseract or the fixtures are not available.
Cases marked xfail are real engine gaps, not test mistakes. They turn into
XPASS (shown in the report) as soon as the engine learns the missing rule.
"""
import csv
import json
import pathlib

import pytest

import integration
from ocr import available_backends

ROOT = pathlib.Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures"
SCHEMA = ROOT / "contracts" / "verdict.schema.json"
MANIFEST = FIXTURES / "manifest.csv"

needs_ocr = pytest.mark.skipif(not available_backends(), reason="No OCR backend (Tesseract or Docker)")
needs_fixtures = pytest.mark.skipif(not MANIFEST.exists(), reason="tests/fixtures not merged yet (TASK-03)")

# file -> why the engine cannot pass it yet (owner: Ayanda, engine/evaluate.py)
ENGINE_GAPS = {
    "r01_wrong_reference.png": "engine never compares the reference (reference_mismatch)",
    "r02_wrong_reference.png": "engine never compares the reference (reference_mismatch)",
    "d01_repeat_same_seller.png": "engine treats a same-seller repeat as STOP; should be WAIT duplicate_same_seller",
    "b01_blurry.png": "same-seller near-duplicate gives STOP; rule 2 says WAIT with low_ocr_confidence",
    "b02_blurry.png": "same-seller near-duplicate gives STOP; rule 2 says WAIT with low_ocr_confidence",
}


def _rows():
    if not MANIFEST.exists():
        return []
    with open(MANIFEST, newline="", encoding="utf-8") as fh:
        # REJECT rows (oversized, wrong type) never reach OCR; the upload tests cover them.
        return [r for r in csv.DictReader(fh) if r["expected_verdict"] != "REJECT"]


def _reasons(text):
    return {r for r in (text or "").replace(";", ",").split(",") if r}


@pytest.fixture(scope="module")
def results():
    """Submit the whole manifest once, in order, so duplicates behave."""
    integration.reset_fingerprints()
    out = {}
    for row in _rows():
        out[row["file"]] = integration.check_payment(
            (FIXTURES / row["file"]).read_bytes(),
            expected_amount=row["expected_amount"],
            expected_recipient=row["expected_recipient"],
            expected_reference=row["expected_reference"],
            seller_id=row["seller_id"],
            use_ai=False,
        )
    yield out
    integration.reset_fingerprints()


def _case(row):
    marks = []
    if row["file"] in ENGINE_GAPS:
        marks.append(pytest.mark.xfail(reason=ENGINE_GAPS[row["file"]], strict=False))
    return pytest.param(row, id=row["file"], marks=marks)


@needs_ocr
@needs_fixtures
@pytest.mark.parametrize("row", [_case(r) for r in _rows()])
def test_manifest_verdict(row, results):
    got = results[row["file"]]
    assert got["verdict"] == row["expected_verdict"]
    assert set(got["reasons"]) == _reasons(row["expected_reasons"])


@needs_ocr
@needs_fixtures
def test_every_result_follows_the_contract(results):
    schema = json.loads(SCHEMA.read_text(encoding="utf-8")) if SCHEMA.exists() else None
    for name, res in results.items():
        assert res["bank_reminder"] == "Confirm the money in your banking app before you release goods."
        assert res["explanation_source"] in {"template", "gemini"}
        assert set(res["extracted"]) == {"amount", "recipient", "reference"}
        assert 0.0 <= res["ocr_confidence"] <= 1.0
        assert set(res["duplicate"]) == {"found", "same_seller"}
        if schema:
            assert set(schema["required"]) <= set(res), name
            allowed = set(schema["properties"]["reasons"]["items"]["enum"])
            assert set(res["reasons"]) <= allowed, name


@needs_ocr
@needs_fixtures
def test_check_ids_are_unique(results):
    ids = [r["check_id"] for r in results.values()]
    assert len(ids) == len(set(ids))


# ---- upload rejection (no OCR needed) -------------------------------------
def test_oversized_upload_is_rejected():
    with pytest.raises(integration.UploadRejected) as err:
        integration.validate_upload(b"\0" * (integration.MAX_UPLOAD_BYTES + 1))
    assert err.value.code == "file_too_large"


def test_text_file_is_rejected():
    with pytest.raises(integration.UploadRejected) as err:
        integration.validate_upload(b"this is not an image")
    assert err.value.code == "unsupported_type"


# ---- HTTP layer -----------------------------------------------------------
@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from main import app

    integration.reset_fingerprints()
    return TestClient(app)


@needs_ocr
@needs_fixtures
@pytest.mark.parametrize("path", ["/check", "/api/check"])
def test_http_match(client, path):
    row = next(r for r in _rows() if r["file"] == "m01_match.png")
    resp = client.post(
        path,
        files={"image": ("m01.png", (FIXTURES / row["file"]).read_bytes(), "image/png")},
        data={"expected_amount": row["expected_amount"], "expected_recipient": row["expected_recipient"],
              "expected_reference": row["expected_reference"], "seller_id": row["seller_id"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["verdict"] == "MATCH" and body["reasons"] == []
    assert body["extracted"]["recipient"] == "Thabo Sneakers"


def test_http_rejects_text_file(client):
    resp = client.post(
        "/check",
        files={"image": ("note.txt", b"hello", "text/plain")},
        data={"expected_amount": "1800", "expected_recipient": "Thabo Sneakers"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "unsupported_type"
