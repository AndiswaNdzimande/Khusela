from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import require_seller
from app.db.database import get_db
from app.db.fingerprints import compute_file_hash, dup_result, find_duplicates, save_fingerprint
from app.db.models import Check, Seller
from engine.evaluate import evaluate
from engine.templates import get_template

logger = logging.getLogger(__name__)

router = APIRouter(tags=["khusela-check"])


class CheckResponse(BaseModel):
    check_id: str
    verdict: str
    reasons: list[str]
    explanation: str
    confidence: float | None = None
    is_duplicate: bool
    extracted: dict[str, Any] = {}
    expected: dict[str, Any] = {}
    duplicate: dict[str, Any] = {}
    raw_ocr_text: str | None = None
    explanation_source: str = "template"
    suggested_reply: str | None = None
    bank_reminder: str = (
        "Always confirm with your bank before releasing goods. "
        "Khusela checks the slip only — it cannot guarantee that funds have cleared."
    )


def _attempt_ocr(raw_bytes: bytes) -> tuple[dict[str, Any], float, str | None]:
    """Try to run OCR and field extraction on the image bytes.

    Returns (extracted_fields_dict, ocr_confidence, raw_ocr_text).
    Falls back gracefully to empty fields and confidence=0.0 when OCR is
    unavailable (Tesseract not installed and no Docker image built).
    """
    try:
        from ocr.tesseract_engine import OcrUnavailableError, run_ocr
        from ocr.extract import extract_fields
    except ImportError:
        # OCR package not importable — this should not happen in normal installs.
        return {}, 0.0, None

    try:
        ocr_result = run_ocr(raw_bytes)
        fields = extract_fields(ocr_result.text)
        extracted: dict[str, Any] = {
            "amount": fields.amount,
            "recipient": fields.recipient,
            "reference": fields.reference,
        }
        return extracted, ocr_result.confidence, ocr_result.text or None
    except OcrUnavailableError as exc:
        logger.info("OCR unavailable (%s); proceeding with empty extracted fields.", exc)
        return {}, 0.0, None
    except Exception as exc:
        logger.warning("OCR run failed: %s", exc)
        return {}, 0.0, None


def _run_check(
    raw_bytes: bytes,
    expected_amount: float,
    expected_recipient: str,
    expected_reference: str,
    db: Session,
    seller: Seller,
) -> CheckResponse:
    # --- Fingerprinting (SHA-256 exact duplicate detection) ---
    hash_hex, hash_int, hash_algo = compute_file_hash(raw_bytes)
    matches = find_duplicates(db, hash_hex, hash_algo, seller.id)
    dup = dup_result(matches)

    # --- OCR (best-effort; degrades gracefully when Tesseract is absent) ---
    extracted, ocr_confidence, raw_ocr_text = _attempt_ocr(raw_bytes)

    expected = {
        "amount": expected_amount,
        "recipient": expected_recipient,
        "reference": expected_reference,
    }

    # --- Rule engine ---
    decision = evaluate(extracted, expected, ocr_confidence=ocr_confidence, dup_result=dup)

    # Normalise the low_ocr_confidence reason to ocr_unavailable when nothing
    # was extracted — gives the seller a clearer message.
    if decision["reasons"] == ["low_ocr_confidence"] and not extracted:
        decision["explanation"] = get_template("OCR_UNAVAILABLE")
        decision["reasons"] = ["ocr_unavailable", "low_ocr_confidence"]

    # --- Persist ---
    check_row = Check(
        seller_id=seller.id,
        verdict=decision["verdict"],
        reasons=decision["reasons"],
        explanation=decision["explanation"],
        confidence=decision.get("confidence"),
        extracted=extracted,
        expected=expected,
        duplicate=dup,
        raw_file_path=None,
        raw_file_uploaded_at=None,
    )
    db.add(check_row)
    db.flush()
    save_fingerprint(db, seller.id, check_row.id, hash_hex, hash_int, hash_algo)
    db.commit()
    db.refresh(check_row)

    return CheckResponse(
        check_id=check_row.id,
        verdict=decision["verdict"],
        reasons=decision["reasons"],
        explanation=decision["explanation"],
        confidence=decision.get("confidence"),
        is_duplicate=bool(dup["found"]),
        extracted=extracted,
        expected=expected,
        duplicate={**dup, "matches": len(matches)},
        raw_ocr_text=raw_ocr_text,
        explanation_source="template",
        suggested_reply=None,
    )


@router.post("/check", response_model=CheckResponse)
async def check_endpoint(
    image: Annotated[UploadFile, File(...)],
    expected_amount: Annotated[float, Form(...)],
    expected_recipient: Annotated[str, Form(...)],
    expected_reference: Annotated[str, Form(...)],
    db: Annotated[Session, Depends(get_db)],
    seller: Annotated[Seller, Depends(require_seller)],
) -> CheckResponse:
    raw = await image.read()
    if not raw:
        raise HTTPException(status_code=422, detail="Empty file")
    return _run_check(raw, expected_amount, expected_recipient, expected_reference, db, seller)


@router.post("/api/check", response_model=CheckResponse)
async def check_api(
    image: Annotated[UploadFile, File(...)],
    expected_amount: Annotated[float, Form(...)],
    expected_recipient: Annotated[str, Form(...)],
    expected_reference: Annotated[str, Form(...)],
    db: Annotated[Session, Depends(get_db)],
    seller: Annotated[Seller, Depends(require_seller)],
) -> CheckResponse:
    raw = await image.read()
    if not raw:
        raise HTTPException(status_code=422, detail="Empty file")
    return _run_check(raw, expected_amount, expected_recipient, expected_reference, db, seller)
