import json
from pathlib import Path

import pytest

from ocr.extract import (
    ExtractedFields,
    extract_amount,
    extract_fields,
    extract_recipient,
    extract_reference,
    parse_amount,
)

FIXTURES = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "synthetic"
    / "ocr_texts.json"
)
SYNTHETIC_CASES = json.loads(FIXTURES.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("R1,800.00", 1800.0),
        ("R 1 800.00", 1800.0),
        ("1800.00", 1800.0),
        ("R1 800", 1800.0),
        ("1 800,00", 1800.0),
        ("1.800,00", 1800.0),
        ("ZAR 2 450.50", 2450.5),
        ("R\u00a01\u00a0800.00", 1800.0),
        ("R0.00", None),
        ("0.00", None),
        ("", None),
        ("not an amount", None),
    ],
)
def test_parse_amount_formats(raw, expected):
    assert parse_amount(raw) == expected


@pytest.mark.parametrize(
    "case",
    SYNTHETIC_CASES,
    ids=[case["id"] for case in SYNTHETIC_CASES],
)
def test_synthetic_ocr_set(case):
    fields = extract_fields(case["text"])
    expected = case["expected"]

    assert fields.amount == expected["amount"]
    assert fields.reference == expected["reference"]
    assert (fields.recipient or "").casefold() == (expected["recipient"] or "").casefold()


def test_fee_and_balance_are_not_selected_as_amount():
    text = "Amount: R1,800.00\nFee: R0.00\nBalance: R25,000.00"

    assert extract_amount(text) == 1800.0


def test_reference_that_looks_like_money_is_not_an_amount():
    text = "Payment to: Thabo Sneakers\nReference: 1800.00"

    assert extract_amount(text) is None
    assert extract_reference(text) == "1800.00"


def test_currency_in_reference_is_not_an_amount():
    text = "Payment to: Thabo Sneakers\nReference: R1,800.00"

    assert extract_amount(text) is None


def test_balance_alone_is_not_an_amount():
    assert extract_amount("Available balance: R25,000.00") is None


def test_plain_decimal_amount_without_labels():
    assert extract_amount("1800.00") == 1800.0


@pytest.mark.parametrize("text", ["R1,800", "R 1 800.00", "1800.00"])
def test_task_amount_formats_end_to_end(text):
    assert extract_amount(text) == 1800.0


def test_recipient_can_be_on_the_next_line():
    text = "Amount: R1,800.00\nTo\nThabo Sneakers\nReference\nSNK1800"

    assert extract_recipient(text) == "Thabo Sneakers"
    assert extract_reference(text) == "SNK1800"


def test_recipient_stops_before_reference_on_same_line():
    text = "TO: THABO SNEAKERS Reference: SNK1800\nAmount: R1,800.00"

    assert extract_recipient(text) == "THABO SNEAKERS"


def test_inline_payment_sentence():
    text = "You paid R1,800.00 to Thabo Sneakers on 23 Oct 2026"

    fields = extract_fields(text)

    assert fields.amount == 1800.0
    assert fields.recipient == "Thabo Sneakers"


def test_empty_text_returns_no_fields():
    fields = extract_fields("")

    assert fields == ExtractedFields(amount=None, recipient=None, reference=None)


def test_as_dict_matches_verdict_contract_shape():
    fields = extract_fields(
        "Amount: R1,800.00\nTo: Thabo Sneakers\nReference: SNK1800"
    )

    assert fields.as_dict() == {
        "amount": 1800.0,
        "recipient": "Thabo Sneakers",
        "reference": "SNK1800",
    }
    assert fields.is_complete is True
