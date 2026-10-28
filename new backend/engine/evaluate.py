from __future__ import annotations

import re

from engine.templates import get_template


def normalize_amount(amount_str: object) -> float:
    if amount_str is None or amount_str == "":
        return 0.0
    if isinstance(amount_str, (int, float)):
        return float(amount_str)

    clean_str = re.sub(r"[^\d,.]", "", str(amount_str))
    if not clean_str:
        return 0.0

    if "," in clean_str and "." in clean_str:
        if clean_str.rfind(",") > clean_str.rfind("."):
            clean_str = clean_str.replace(".", "").replace(",", ".")
        else:
            clean_str = clean_str.replace(",", "")
    elif "," in clean_str:
        if clean_str.count(",") == 1 and len(clean_str.split(",")[-1]) == 3:
            clean_str = clean_str.replace(",", "")
        else:
            clean_str = clean_str.replace(",", ".")

    try:
        return float(clean_str)
    except ValueError:
        return 0.0


def normalize_name(name_str: object) -> str:
    if not name_str:
        return ""
    return re.sub(r"[^a-z0-9]", "", str(name_str).lower())


def evaluate(extracted: dict, expected: dict, ocr_confidence: float, dup_result: dict) -> dict:
    reasons: list[str] = []
    verdict = "MATCH"

    is_duplicate = dup_result.get("found", False)
    same_seller = dup_result.get("same_seller", False)

    if is_duplicate and not same_seller:
        return {
            "verdict": "STOP",
            "reasons": ["duplicate_image"],
            "explanation": get_template("STOP_DUPLICATE"),
            "confidence": ocr_confidence,
            "is_duplicate": True,
        }

    if ocr_confidence < 0.5:
        return {
            "verdict": "WAIT",
            "reasons": ["low_ocr_confidence"],
            "explanation": get_template("STOP_UNREADABLE"),
            "confidence": ocr_confidence,
            "is_duplicate": is_duplicate,
        }

    if is_duplicate and same_seller:
        verdict = "WAIT"
        reasons.append("duplicate_same_seller")

    expected_amount = normalize_amount(expected.get("amount"))
    extracted_amount = normalize_amount(extracted.get("amount"))
    if expected_amount != extracted_amount:
        verdict = "WAIT"
        reasons.append("amount_mismatch")

    expected_name = normalize_name(expected.get("recipient"))
    extracted_name = normalize_name(extracted.get("recipient"))
    if expected_name and expected_name != extracted_name:
        verdict = "WAIT"
        reasons.append("recipient_mismatch")

    expected_ref = normalize_name(expected.get("reference"))
    extracted_ref = normalize_name(extracted.get("reference"))
    if expected_ref and extracted_ref and expected_ref != extracted_ref:
        verdict = "WAIT"
        reasons.append("reference_mismatch")
    elif expected_ref and not extracted_ref:
        verdict = "WAIT"
        reasons.append("field_not_found")

    if verdict == "MATCH":
        explanation = get_template("MATCH")
    elif "amount_mismatch" in reasons:
        explanation = get_template("WAIT_AMOUNT")
    elif "recipient_mismatch" in reasons:
        explanation = get_template("WAIT_NAME")
    elif "reference_mismatch" in reasons:
        explanation = get_template("WAIT_REFERENCE")
    else:
        explanation = get_template("MATCH")

    return {
        "verdict": verdict,
        "reasons": reasons,
        "explanation": explanation,
        "confidence": ocr_confidence,
        "is_duplicate": is_duplicate,
    }
