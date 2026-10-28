"""TASK-05: glue that runs one screenshot through the whole Khusela pipeline.

    validate_upload -> analyse_image -> find_duplicates -> evaluate
                    -> explanation -> save fingerprint -> verdict JSON

The verdict is decided by engine.evaluate() only. This module never adds or
changes rules; it only moves data between the pieces and shapes the result to
contracts/verdict.schema.json.

Some pieces are owned by other people and may not exist yet. Each one below has
a stand-in that is used ONLY when the real module cannot be imported:

    analyse_image      real one: backend/ocr/pipeline.py   (Nyakallo)
    find_duplicates    real one: backend/db/fingerprints.py (Sphiwe, TASK-25)
    validate_upload    real one: safety gate                (Sphiwe, TASK-24)

When a real module lands with the same function name, this file picks it up
automatically and the stand-in goes unused. See docs/interfaces.md.
"""
from __future__ import annotations

import io
import itertools
import threading

from engine.evaluate import evaluate, normalize_amount

BANK_REMINDER = "Confirm the money in your banking app before you release goods."
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
ALLOWED_FORMATS = {"PNG", "JPEG"}


class UploadRejected(Exception):
    """Upload refused before OCR. `code` is one of the codes in docs/interfaces.md."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# --------------------------------------------------------------------------
# Stand-in: upload safety gate (real one: Sphiwe, TASK-24)
# --------------------------------------------------------------------------
def _standin_validate_upload(image_bytes: bytes) -> None:
    from PIL import Image, UnidentifiedImageError

    if len(image_bytes) > MAX_UPLOAD_BYTES:
        raise UploadRejected("file_too_large", "Images must be 5 MB or smaller.")
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            fmt = img.format
            img.verify()
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError):
        # Anything that is not a readable image (text file, corrupt data, ...)
        raise UploadRejected("unsupported_type", "Please upload a PNG or JPEG screenshot.")
    if fmt not in ALLOWED_FORMATS:
        raise UploadRejected("unsupported_type", "Please upload a PNG or JPEG screenshot.")


# --------------------------------------------------------------------------
# Stand-in: image analysis (real one: Nyakallo, backend/ocr/pipeline.py)
# --------------------------------------------------------------------------
def _standin_analyse_image(image_bytes: bytes) -> dict:
    from ocr import extract_fields, phash, run_ocr

    ocr = run_ocr(image_bytes)
    fields = extract_fields(ocr.text)
    return {
        "amount": fields.amount,
        "recipient": fields.recipient,
        "reference": fields.reference,
        "ocr_confidence": float(ocr.confidence),
        "raw_text": ocr.text,
        "phash": phash(image_bytes),
    }


# --------------------------------------------------------------------------
# Stand-in: fingerprint store (real one: Sphiwe, TASK-25). Memory only, so it
# resets when the server restarts. Fine for the demo; never use it in prod.
# --------------------------------------------------------------------------
_fingerprints: list[tuple[str, str]] = []  # (phash hex, seller_id)
_lock = threading.Lock()


def _standin_find_duplicates(phash_hex: str, seller_id: str) -> dict:
    from ocr import is_near_duplicate

    with _lock:
        stored = list(_fingerprints)
    matches = [owner for h, owner in stored if is_near_duplicate(phash_hex, h)]
    found = bool(matches)
    # A copy from ANOTHER seller is the dangerous case, so it wins over a
    # copy from the same seller (decision rule 1 in docs/interfaces.md).
    same_seller = found and all(owner == seller_id for owner in matches)
    return {"found": found, "same_seller": same_seller}


def _standin_save_fingerprint(phash_hex: str, seller_id: str) -> None:
    with _lock:
        _fingerprints.append((phash_hex, seller_id))


def reset_fingerprints() -> None:
    """Empty the stand-in store (used by tests and by the demo reset)."""
    with _lock:
        _fingerprints.clear()


# --------------------------------------------------------------------------
# Pick the real piece when it exists, otherwise the stand-in.
# --------------------------------------------------------------------------
try:
    from ocr.pipeline import analyse_image  # type: ignore  # noqa: F401
except ImportError:
    analyse_image = _standin_analyse_image

try:
    from db.fingerprints import find_duplicates, save_fingerprint  # type: ignore  # noqa: F401
except ImportError:
    find_duplicates = _standin_find_duplicates
    save_fingerprint = _standin_save_fingerprint

try:
    from api.safety import validate_upload  # type: ignore  # noqa: F401
except ImportError:
    validate_upload = _standin_validate_upload

_check_ids = itertools.count(1)


def _explanation(verdict: dict, use_ai: bool) -> tuple[str, str]:
    """Return (text, source). The AI only sees the finished verdict."""
    template_text = verdict["explanation"]
    if not use_ai:
        return template_text, "template"
    from engine.ai_explainer import generate_ai_explanation

    text = generate_ai_explanation(verdict)
    return text, ("template" if text == template_text else "gemini")


def check_payment(
    image_bytes: bytes,
    *,
    expected_amount,
    expected_recipient: str,
    expected_reference: str = "",
    seller_id: str = "demo_seller",
    use_ai: bool = True,
) -> dict:
    """Run one screenshot through the pipeline and return the verdict JSON.

    Raises UploadRejected for bad uploads and ocr.OcrUnavailableError when no
    OCR backend can be used. Both are handled by the HTTP layer.
    """
    validate_upload(image_bytes)

    found = analyse_image(image_bytes)
    extracted = {
        "amount": found["amount"],
        "recipient": found["recipient"],
        "reference": found["reference"],
    }
    expected = {
        "amount": normalize_amount(expected_amount),
        "recipient": expected_recipient,
        "reference": expected_reference,
    }
    dup = find_duplicates(found["phash"], seller_id)

    # Rules only. Anything the engine does not know yet is simply ignored.
    verdict = evaluate(
        extracted=extracted,
        expected=expected,
        ocr_confidence=found["ocr_confidence"],
        dup_result=dup,
    )
    text, source = _explanation(verdict, use_ai)

    # Remember this screenshot so a later copy is caught.
    save_fingerprint(found["phash"], seller_id)

    return {
        "check_id": f"chk_{next(_check_ids):06d}",
        "verdict": verdict["verdict"],
        "reasons": verdict["reasons"],
        "explanation": text,
        "explanation_source": source,
        "extracted": extracted,
        "expected": expected,
        "ocr_confidence": found["ocr_confidence"],
        "duplicate": {"found": bool(dup["found"]), "same_seller": bool(dup["same_seller"])},
        "raw_ocr_text": found["raw_text"],
        "bank_reminder": BANK_REMINDER,
    }
