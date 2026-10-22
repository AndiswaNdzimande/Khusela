# backend/engine/evaluate.py
import re
from .templates import get_template

def normalize_amount(amount_str: str) -> float:
    """
    Cleans currency strings. 
    Turns "R1,800.00" or "R 1 800" or "1800.00" into 1800.0
    """
    if not amount_str:
        return 0.0
    # Remove everything except digits and decimal points
    clean_str = re.sub(r'[^\d.]', '', str(amount_str))
    try:
        return float(clean_str)
    except ValueError:
        return 0.0

def normalize_name(name_str: str) -> str:
    """
    Cleans names for comparison. 
    Lowercases, removes spaces, and ignores common punctuation.
    """
    if not name_str:
        return ""
    return re.sub(r'[^a-z0-9]', '', str(name_str).lower())

def evaluate(extracted: dict, expected: dict, ocr_confidence: float, dup_result: dict) -> dict:
    """
    TASK-10 & TASK-11: Deterministic rule engine.
    """
    reasons = []
    verdict = "MATCH"
    is_duplicate = dup_result.get("found", False)

    # 1. DUPLICATE CHECK (The highest priority STOP condition)
    if is_duplicate:
        return {
            "verdict": "STOP",
            "reasons": ["duplicate_image"],
            "explanation": get_template("STOP_DUPLICATE"),
            "confidence": ocr_confidence,
            "is_duplicate": True
        }

    # 2. OCR CONFIDENCE CHECK
    # If the image is too blurry to read reliably, we cannot trust the text.
    if ocr_confidence < 0.5:
        return {
            "verdict": "WAIT",
            "reasons": ["low_ocr_confidence"],
            "explanation": get_template("STOP_UNREADABLE"),
            "confidence": ocr_confidence,
            "is_duplicate": False
        }

    # 3. AMOUNT MATCHING
    expected_amount = normalize_amount(expected.get("amount"))
    extracted_amount = normalize_amount(extracted.get("amount"))

    if expected_amount != extracted_amount:
        verdict = "WAIT"
        reasons.append("amount_mismatch")

    # 4. RECIPIENT NAME MATCHING
    expected_name = normalize_name(expected.get("recipient"))
    extracted_name = normalize_name(extracted.get("recipient"))

    # We only check name if the expected name was actually provided
    if expected_name and expected_name != extracted_name:
        verdict = "WAIT"
        reasons.append("recipient_mismatch")

    # 5. GENERATE EXPLANATION
    # Pick the most relevant template based on the verdict
    if verdict == "MATCH":
        explanation = get_template("MATCH")
    elif "amount_mismatch" in reasons:
        explanation = get_template("WAIT_AMOUNT")
    elif "recipient_mismatch" in reasons:
        explanation = get_template("WAIT_NAME")
    else:
        explanation = get_template("MATCH") # Fallback

    return {
        "verdict": verdict,
        "reasons": reasons,
        "explanation": explanation,
        "confidence": ocr_confidence,
        "is_duplicate": is_duplicate
    }