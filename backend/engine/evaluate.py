"""Deterministic rule engine (TASK-10 / TASK-11).

The engine is pure logic: no model, no network, no randomness. Given the
fields OCR read from a screenshot, the sale the seller expected and the
duplicate lookup result, it returns STOP / WAIT / MATCH with a plain-English
sentence built from the actual values.

Order of priority:

1. duplicate proof      -> STOP (another seller) / WAIT (same seller)
2. unreadable screenshot -> WAIT (low OCR confidence)
3. field mismatches      -> WAIT (amount, recipient, reference, unreadable)
4. nothing wrong         -> MATCH (never "PAID", never "VERIFIED")
"""

import re
from typing import Any

from .templates import get_template

<<<<<<< HEAD
BANK_REMINDER = "Check your banking app first."


def normalize_amount(amount_str: Any) -> float:
    """
    Cleans currency strings.
    Turns "R1,800.00" or "R 1 800" or "1800.00" into 1800.0
    """
    if not amount_str:
        return 0.0
    # Remove everything except digits and decimal points
    clean_str = re.sub(r"[^\d.]", "", str(amount_str))
=======
def normalize_amount(amount_str: str) -> float:
    if not amount_str:
        return 0.0

    # Remove everything except digits, commas, and periods
    clean_str = re.sub(r'[^\d,.]', '', str(amount_str))

    if ',' in clean_str and '.' in clean_str:
        # Both exist. Whichever is LAST is the decimal separator.
        if clean_str.rfind(',') > clean_str.rfind('.'):
            # European: 1.800,00
            clean_str = clean_str.replace('.', '').replace(',', '.')
        else:
            # SA/UK: 1,800.00 or 1,234,567.89
            clean_str = clean_str.replace(',', '')

    elif ',' in clean_str:
        # Only comma exists. Is it a decimal (1800,00) or thousands (R1,800)?
        if clean_str.count(',') == 1 and len(clean_str.split(',')[-1]) == 3:
            clean_str = clean_str.replace(',', '')   # "1,800" -> 1800
        else:
            clean_str = clean_str.replace(',', '.')  # "1800,00" -> 1800.00

>>>>>>> aba3f0e96c9b960aa272c9eec4807c3b8cc2fdaf
    try:
        return float(clean_str)
    except ValueError:
        return 0.0


<<<<<<< HEAD
def normalize_name(name_str: Any) -> str:
    """
    Cleans names for comparison.
    Lowercases, removes spaces, and ignores common punctuation.
    """
=======
def normalize_name(name_str: str) -> str:
>>>>>>> aba3f0e96c9b960aa272c9eec4807c3b8cc2fdaf
    if not name_str:
        return ""
    return re.sub(r"[^a-z0-9]", "", str(name_str).lower())


<<<<<<< HEAD
def normalize_reference(reference_str: Any) -> str:
    """Cleans a payment reference for comparison (case and punctuation free)."""
    if not reference_str:
        return ""
    return re.sub(r"[^a-z0-9]", "", str(reference_str).lower())


def _present(value: Any) -> bool:
    """True when OCR actually returned something for this field."""
    return value is not None and str(value).strip() != ""


def _money(value: float) -> str:
    return f"R{value:,.2f}"


def _duplicate_sentence(
    dup: dict,
    extracted: dict,
    expected: dict,
    *,
    same_seller: bool,
) -> str:
    reference = extracted.get("reference") or expected.get("reference")
    subject = f"reference {reference}" if _present(reference) else "this proof"
    if same_seller:
        return (
            f"You have already checked {subject}. Ask the buyer for a fresh "
            f"proof and confirm the money in your banking app."
        )
    source = "another seller's check" if dup.get("reason") != "duplicate_image" else "an earlier check"
    if dup.get("reason") == "duplicate_reference":
        source = "another seller's check"
    return (
        f"Khusela has already seen {subject} on {source}. Treat it as a reused "
        f"proof: do not release the goods. {BANK_REMINDER}"
    )


def _field_sentences(
    extracted: dict,
    expected: dict,
) -> tuple[list[str], list[str]]:
    """Return (matching phrases, gap phrases) for the three compared fields."""
    matches: list[str] = []
    gaps: list[str] = []

    expected_amount = normalize_amount(expected.get("amount"))
    if expected.get("amount") not in (None, "", 0, 0.0):
        if not _present(extracted.get("amount")):
            gaps.append("the amount could not be read")
        else:
            actual = normalize_amount(extracted.get("amount"))
            if abs(actual - expected_amount) < 0.005:
                matches.append(f"the amount matches ({_money(actual)})")
            else:
                gaps.append(
                    f"the amount on this proof is {_money(actual)}, "
                    f"not {_money(expected_amount)}"
                )

    if _present(expected.get("recipient")):
        want = str(expected.get("recipient")).strip()
        if not _present(extracted.get("recipient")):
            gaps.append("the name could not be read")
        elif normalize_name(extracted.get("recipient")) == normalize_name(want):
            matches.append(f"the name matches ({want})")
        else:
            gaps.append(
                f"the name on this proof is {str(extracted.get('recipient')).strip()}, "
                f"not {want}"
            )

    if _present(expected.get("reference")):
        want = str(expected.get("reference")).strip()
        if not _present(extracted.get("reference")):
            gaps.append("the reference could not be read")
        elif normalize_reference(extracted.get("reference")) == normalize_reference(want):
            matches.append(f"the reference matches ({want})")
        else:
            gaps.append(
                f"the reference on this proof is {str(extracted.get('reference')).strip()}, "
                f"not {want}"
            )

    return matches, gaps


def _reasons_for(matches: list[str], gaps: list[str], extracted: dict, expected: dict) -> list[str]:
    reasons: list[str] = []
    if expected.get("amount") not in (None, "", 0, 0.0) and (
        not _present(extracted.get("amount"))
        or abs(normalize_amount(extracted.get("amount")) - normalize_amount(expected.get("amount"))) >= 0.005
    ):
        reasons.append(
            "field_not_found" if not _present(extracted.get("amount")) else "amount_mismatch"
        )
    if _present(expected.get("recipient")):
        if not _present(extracted.get("recipient")):
            reasons.append("field_not_found")
        elif normalize_name(extracted.get("recipient")) != normalize_name(expected.get("recipient")):
            reasons.append("recipient_mismatch")
    if _present(expected.get("reference")):
        if not _present(extracted.get("reference")):
            reasons.append("field_not_found")
        elif normalize_reference(extracted.get("reference")) != normalize_reference(expected.get("reference")):
            reasons.append("reference_mismatch")
    # field_not_found is one signal however many fields were unreadable.
    return list(dict.fromkeys(reasons))


def _join(phrases: list[str]) -> str:
    if len(phrases) == 1:
        return phrases[0]
    return ", ".join(phrases[:-1]) + f" and {phrases[-1]}"


def _capitalise(sentence: str) -> str:
    return sentence[:1].upper() + sentence[1:]


def build_explanation(
    verdict: str,
    reasons: list[str],
    extracted: dict,
    expected: dict,
    ocr_confidence: float,
    dup: dict,
) -> str:
    """One deterministic sentence the seller can act on, built from the values."""
    if verdict == "STOP":
        return _duplicate_sentence(dup, extracted, expected, same_seller=False)

    if "duplicate_same_seller" in reasons:
        return _duplicate_sentence(dup, extracted, expected, same_seller=True)

    if "low_ocr_confidence" in reasons:
        return (
            f"The screenshot is too blurry to read ({ocr_confidence:.0%} confidence), so "
            f"Khusela cannot trust what it says. Ask the buyer for a clear, original "
            f"screenshot. {BANK_REMINDER}"
        )

    matches, gaps = _field_sentences(extracted, expected)

    if not gaps:
        if not matches:
            return (
                "Khusela could not read the payment details on this screenshot. "
                f"Ask the buyer for a clear, original proof. {BANK_REMINDER}"
            )
        return (
            f"The {_join(matches)[4:] if matches[0].startswith('the ') else _join(matches)} "
            f"all match your sale. Looks consistent — this is not proof of payment, "
            f"so confirm the money in your banking app before you release goods."
        )

    head = _join(matches).replace("the ", "", 1) if matches else ""
    body = _join(gaps)
    sentence = f"The {head}, but {body}." if head else f"{_capitalise(body)}."
    return f"{sentence} Do not release the goods. {BANK_REMINDER}"


def evaluate(
    extracted: dict,
    expected: dict,
    ocr_confidence: float,
    dup_result: dict,
) -> dict:
    """
    TASK-10 & TASK-11: Deterministic rule engine.

    ``dup_result`` is the duplicate lookup from ``app.db.fingerprints``:
    ``{"found": bool, "same_seller": bool, "reason": "reference"|"image"|None}``.
    """
    dup = dup_result or {}
    confidence = 0.0 if ocr_confidence is None else float(ocr_confidence)
    is_duplicate = bool(dup.get("found"))
    same_seller = bool(dup.get("same_seller"))

    def _result(verdict: str, reasons: list[str]) -> dict:
        return {
            "verdict": verdict,
            "reasons": reasons,
            "explanation": build_explanation(
                verdict, reasons, extracted, expected, confidence, dup
            ),
            "confidence": confidence,
            "is_duplicate": is_duplicate,
            "explanation_source": "template",
        }

    # 0. FORENSIC TAMPERING CHECK (PDF documents only)
    forensics = extracted.get("forensics") or (dup_result.get("forensics") if dup_result else None)
    if forensics and forensics.get("is_pdf") and forensics.get("tampering_detected"):
        forensic_reasons = forensics.get("reasons") or ["document_tampered"]
        summary = forensics.get("summary") or "Signs of image editing or copy-paste tampering detected"
        return {
            "verdict": "STOP",
            "reasons": forensic_reasons,
            "explanation": f"Forensic analysis detected document tampering ({summary}). Do not release the goods. {BANK_REMINDER}",
            "confidence": confidence,
            "is_duplicate": is_duplicate,
            "explanation_source": "template",
            "forensics": forensics,
        }

    # 1. DUPLICATE CHECK — the highest priority STOP condition.
    if is_duplicate:
        if same_seller:
            return _result("WAIT", ["duplicate_same_seller"])
        reason = dup.get("reason")
        if reason not in {"duplicate_reference", "duplicate_image"}:
            reason = "duplicate_image"
        return _result("STOP", [reason])

    # 2. OCR CONFIDENCE — if the image is too blurry we cannot trust the text.
    if confidence < 0.5:
        return _result("WAIT", ["low_ocr_confidence"])
=======
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
>>>>>>> aba3f0e96c9b960aa272c9eec4807c3b8cc2fdaf

    # 3. FIELD COMPARISON — the seller's expected order is the standard.
    matches, gaps = _field_sentences(extracted, expected)
    reasons = _reasons_for(matches, gaps, extracted, expected)

<<<<<<< HEAD
    if reasons:
        return _result("WAIT", reasons)

    return _result("MATCH", [])

=======
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
>>>>>>> aba3f0e96c9b960aa272c9eec4807c3b8cc2fdaf

# Kept for callers that only want a canned sentence (offline fallbacks).
__all__ = [
    "BANK_REMINDER",
    "build_explanation",
    "evaluate",
    "get_template",
    "normalize_amount",
    "normalize_name",
    "normalize_reference",
]
