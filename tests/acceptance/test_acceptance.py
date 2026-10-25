"""TASK-06: the 8 Khusela acceptance tests (hour-40 gate).

Each test is self-contained: it clears the fingerprint store, submits the
screenshots it needs in order, and checks the verdict and reasons that a
seller would see. Uses the real OCR, pHash and rule engine (no Gemini).

Tests marked xfail are known engine gaps (owner: Ayanda, backend/engine).
They turn into XPASS as soon as the rule exists. The gate is met when no
test in this file is marked xfail any more.

Run from the repo root:
    python -m pytest tests/acceptance -q
"""
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

import integration  # noqa: E402
from ocr import available_backends  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"

pytestmark = pytest.mark.skipif(
    not available_backends() or not (FIXTURES / "manifest.csv").exists(),
    reason="needs Tesseract (or Docker) and tests/fixtures",
)

# Expected sale details per seller, as in tests/fixtures/manifest.csv
SALES = {
    "seller_a": dict(expected_amount="1800.00", expected_recipient="Thabo Sneakers", expected_reference="SNK1800"),
    "seller_b": dict(expected_amount="450.00", expected_recipient="Naledi Beauty Hub", expected_reference="BEAUTY450"),
    "seller_c": dict(expected_amount="325.50", expected_recipient="Mama Zodwa Spaza", expected_reference="SPAZA325"),
}


@pytest.fixture(autouse=True)
def clean_store():
    integration.reset_fingerprints()
    yield
    integration.reset_fingerprints()


def submit(filename, seller):
    """Send one fixture through the whole pipeline as the given seller."""
    return integration.check_payment(
        (FIXTURES / filename).read_bytes(),
        seller_id=seller,
        use_ai=False,
        **SALES[seller],
    )


def assert_safe_wording(res):
    """Every verdict must keep the bank reminder and never claim the money arrived."""
    assert res["bank_reminder"] == "Confirm the money in your banking app before you release goods."
    text = (res.get("explanation") or res.get("message") or "").lower()
    assert "has been paid" not in text and "payment received" not in text


def assert_outcome(res, verdict, reasons):
    assert res["verdict"] == verdict
    assert set(res["reasons"]) == set(reasons)
    assert_safe_wording(res)


# 1 -------------------------------------------------------------------------
def test_01_correct_payment_is_a_match():
    assert_outcome(submit("m01_match.png", "seller_a"), "MATCH", [])


# 2 -------------------------------------------------------------------------
def test_02_wrong_recipient_waits():
    assert_outcome(submit("n01_wrong_name.png", "seller_a"), "WAIT", ["recipient_mismatch"])


# 3 -------------------------------------------------------------------------
def test_03_wrong_amount_waits():
    assert_outcome(submit("a01_wrong_amount.png", "seller_a"), "WAIT", ["amount_mismatch"])


# 4 -------------------------------------------------------------------------
@pytest.mark.xfail(reason="engine never compares the reference (reference_mismatch)", strict=False)
def test_04_wrong_reference_waits():
    assert_outcome(submit("r02_wrong_reference.png", "seller_c"), "WAIT", ["reference_mismatch"])


# 5 -------------------------------------------------------------------------
def test_05_slip_reused_by_another_seller_is_stopped():
    submit("m01_match.png", "seller_a")  # the genuine seller is checked first
    assert_outcome(submit("u01_reused.jpg", "seller_b"), "STOP", ["duplicate_image"])


# 6 -------------------------------------------------------------------------
@pytest.mark.xfail(reason="same-seller repeat gives STOP; should be WAIT duplicate_same_seller", strict=False)
def test_06_same_seller_resend_waits_not_stops():
    submit("m01_match.png", "seller_a")
    assert_outcome(submit("d01_repeat_same_seller.png", "seller_a"), "WAIT", ["duplicate_same_seller"])


# 7 -------------------------------------------------------------------------
@pytest.mark.xfail(reason="blurry retake is called a duplicate (STOP); should be WAIT low_ocr_confidence", strict=False)
def test_07_blurry_retake_waits_for_a_clearer_photo():
    submit("m01_match.png", "seller_a")
    res = submit("b01_blurry.png", "seller_a")
    assert res["ocr_confidence"] < 0.5
    assert_outcome(res, "WAIT", ["low_ocr_confidence"])


def test_07b_blurry_photo_on_its_own_waits():
    """A blurry first-time photo (no earlier copy) must already be a WAIT."""
    res = submit("b02_blurry.png", "seller_c")
    assert res["ocr_confidence"] < 0.5
    assert res["verdict"] == "WAIT" and "low_ocr_confidence" in res["reasons"]


# 8 -------------------------------------------------------------------------
@pytest.mark.parametrize(
    "filename, seller, reason",
    [
        ("i01_injection.png", "seller_a", "amount_mismatch"),
        ("i02_injection.png", "seller_b", "recipient_mismatch"),
    ],
)
def test_08_text_inside_the_image_cannot_change_the_verdict(filename, seller, reason):
    assert_outcome(submit(filename, seller), "WAIT", [reason])
