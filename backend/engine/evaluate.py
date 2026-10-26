import re
from .templates import get_template

def normalize_amount(amount_str: str) -> float:
    if not amount_str:
        return 0.0
    # Remove everything except digits, commas, and periods
    clean_str = re.sub(r'[^\d,.]', '', str(amount_str))
    # Handle South African comma decimals (e.g., 1800,00 -> 1800.00)
    clean_str = clean_str.replace(',', '.')
    try:
        return float(clean_str)
    except ValueError:
        return 0.0

def normalize_name(name_str: str) -> str:
    if not name_str:
        return ""
    return re.sub(r'[^a-z0-9]', '', str(name_str).lower())

def evaluate(extracted: dict, expected: dict, ocr_confidence: float, dup_result: dict) -> dict:
    reasons = []
    verdict = "MATCH"
    
    is_duplicate = dup_result.get("found", False)
    same_seller = dup_result.get("same_seller", False)

    # 1. CROSS-SELLER DUPLICATE (The ONLY hard STOP)
    if is_duplicate and not same_seller:
        return {
            "verdict": "STOP",
            "reasons": ["duplicate_image"],
            "explanation": "This exact screenshot was submitted by another seller. It is a known fake. Do not release goods.",
            "confidence": ocr_confidence,
            "is_duplicate": True
        }

    # 2. OCR CONFIDENCE CHECK
    if ocr_confidence < 0.5:
        return {
            "verdict": "WAIT",
            "reasons": ["low_ocr_confidence"],
            "explanation": get_template("STOP_UNREADABLE"),
            "confidence": ocr_confidence,
            "is_duplicate": False
        }

    # 3. SAME-SELLER REPEAT (WAIT, not STOP)
    if is_duplicate and same_seller:
        verdict = "WAIT"
        reasons.append("duplicate_same_seller")

    # 4. AMOUNT MATCHING
    expected_amount = normalize_amount(expected.get("amount"))
    extracted_amount = normalize_amount(extracted.get("amount"))

    if expected_amount != extracted_amount:
        verdict = "WAIT"
        reasons.append("amount_mismatch")

    # 5. RECIPIENT NAME MATCHING
    expected_name = normalize_name(expected.get("recipient"))
    extracted_name = normalize_name(extracted.get("recipient"))

    if expected_name and expected_name != extracted_name:
        verdict = "WAIT"
        reasons.append("recipient_mismatch")
        
    # 6. REFERENCE MATCHING (NEW)
    expected_ref = normalize_name(expected.get("reference"))
    extracted_ref = normalize_name(extracted.get("reference"))
    
    if expected_ref and expected_ref != extracted_ref:
        verdict = "WAIT"
        reasons.append("reference_mismatch")

    # 7. GENERATE EXPLANATION
    if verdict == "MATCH":
        explanation = get_template("MATCH")
    elif "amount_mismatch" in reasons:
        explanation = get_template("WAIT_AMOUNT")
    elif "recipient_mismatch" in reasons:
        explanation = get_template("WAIT_NAME")
    elif "reference_mismatch" in reasons:
        explanation = "The payment reference does not match your sale. Verify the funds in your bank."
    else:
        explanation = get_template("MATCH")

    return {
        "verdict": verdict,
        "reasons": reasons,
        "explanation": explanation,
        "confidence": ocr_confidence,
        "is_duplicate": is_duplicate
    }