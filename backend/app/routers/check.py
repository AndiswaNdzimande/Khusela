"""
TASK-21 + TASK-24 + TASK-25: POST /check and GET /health endpoints.
Requires a valid Bearer token (TASK-23).

Pipeline:
  1. validate_upload   – size cap, magic-byte MIME, Pillow parse   (TASK-24)
  2. compute pHash fingerprint                                       (TASK-25)
  3. find_duplicates   – all sellers, with same_seller flag          (TASK-25)
  4. call integration.check_payment (the real pipeline)              (TASK-05)
     Falls back to a labelled stub if integration is not on sys.path.
  5. persist Check + Fingerprint rows                                (TASK-22)

Bug fixes (v4 report):
  Bug 3: _run_engine called `from engine import evaluate` (gets the module,
         not the function), passed wrong kwarg name (duplicate= vs dup_result=),
         read OCR result as dict (it is an object), hard-coded same_seller=False,
         only caught ImportError so TypeError → 500.
         Fix: call integration.check_payment which already handles the engine
         correctly. Catch all exceptions, not just ImportError.
  Bug 7: /check previously wrote every upload to ./uploads/raw, contradicting
         the privacy story ("nothing stored").
         Fix: raw bytes are never written to disk. The scheduler is still
         available for teams that choose to store files, but /check does not use it.
  Field rename: frontend sends field name 'image', not 'file' (report bug 4).
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.auth import get_current_seller
from app.api.safety import validate_upload
from app.db.database import get_db
from app.db.fingerprints import (
    compute_image_hash,
    dup_result,
    find_duplicates,
    save_fingerprint,
)
from app.db.models import Check, Seller
from app.schemas.check import CheckResponse, HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["check"])


@router.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok")


@router.post("/check", response_model=CheckResponse)
async def check_endpoint(
    # Frontend sends field name 'image' (bug 4 fix)
    image: UploadFile = File(...),
    expected_amount: float = Form(...),
    expected_recipient: str = Form(...),
    expected_reference: str = Form(...),
    db: Session = Depends(get_db),
    seller: Seller = Depends(get_current_seller),
):
    # ------------------------------------------------------------------ #
    # 1. Safety gate – size, MIME, Pillow parse                           #
    # ------------------------------------------------------------------ #
    raw_bytes, mime_type = await validate_upload(image)

    # ------------------------------------------------------------------ #
    # 2. Compute fingerprint (overflow-safe signed int)                   #
    # ------------------------------------------------------------------ #
    hash_hex, hash_int = compute_image_hash(raw_bytes)

    # ------------------------------------------------------------------ #
    # 3. Duplicate lookup – returns all matches with same_seller flag     #
    # ------------------------------------------------------------------ #
    matches = find_duplicates(db, hash_int, seller.id)
    dup = dup_result(matches)          # {"found": bool, "same_seller": bool}
    is_duplicate = dup["found"]

    # ------------------------------------------------------------------ #
    # 4. Run the real pipeline via integration.check_payment              #
    # ------------------------------------------------------------------ #
    verdict, reasons, explanation, confidence, raw_ocr_text, extracted = _run_pipeline(
        raw_bytes=raw_bytes,
        expected_amount=expected_amount,
        expected_recipient=expected_recipient,
        expected_reference=expected_reference,
        dup=dup,
        seller_id=seller.id,
    )

    # ------------------------------------------------------------------ #
    # 5. Persist Check row (no raw file stored – privacy compliant)       #
    # ------------------------------------------------------------------ #
    check_row = Check(
        seller_id=seller.id,
        verdict=verdict,
        reasons=reasons,
        raw_file_path=None,
        raw_file_uploaded_at=None,
    )
    db.add(check_row)
    db.flush()

    save_fingerprint(db, seller.id, check_row.id, hash_hex, hash_int)
    db.commit()
    db.refresh(check_row)

    return CheckResponse(
        check_id=check_row.id,
        verdict=verdict,
        reasons=reasons,
        explanation=explanation,
        confidence=confidence,
        is_duplicate=is_duplicate,
        extracted=extracted,
        expected={
            "amount": expected_amount,
            "recipient": expected_recipient,
            "reference": expected_reference,
        },
        duplicate={
            "found": dup["found"],
            "same_seller": dup["same_seller"],
            "matches": len(matches),
        },
        raw_ocr_text=raw_ocr_text,
        explanation_source="engine" if raw_ocr_text else "stub",
    )


# ---------------------------------------------------------------------------
# Pipeline bridge
# Bug 3 fix: call integration.check_payment, not engine.evaluate directly.
# Catches ALL exceptions (not just ImportError) so TypeError never → 500.
# ---------------------------------------------------------------------------
def _run_pipeline(
    raw_bytes: bytes,
    expected_amount: float,
    expected_recipient: str,
    expected_reference: str,
    dup: dict,
    seller_id: str,
) -> tuple:
    try:
        import integration  # backend/integration.py

        result = integration.check_payment(
            image_bytes=raw_bytes,
            expected={
                "amount": expected_amount,
                "recipient": expected_recipient,
                "reference": expected_reference,
            },
            dup_result=dup,
            seller_id=seller_id,
        )
        return (
            result["verdict"],
            result["reasons"],
            result.get("explanation", ""),
            result.get("confidence"),
            result.get("raw_ocr_text"),
            result.get("extracted", {}),
        )
    except Exception as exc:
        # Log the real error so it is visible in the server log
        logger.warning("Pipeline unavailable (%s: %s) — returning stub.", type(exc).__name__, exc)
        return (
            "WAIT",
            ["engine_unavailable"],
            "Pipeline not connected yet. This is a stub verdict.",
            None,
            None,
            {},
        )
