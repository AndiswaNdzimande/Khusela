"""
TASK-21 + TASK-24 + TASK-25: POST /check and GET /health endpoints.
Requires a valid Bearer token (TASK-23).

Pipeline:
  1. validate_upload   – size cap, magic-byte MIME, Pillow parse   (TASK-24)
  2. compute fingerprint (1024-bit or 64-bit fallback)              (TASK-25)
  3. find_duplicates   – all sellers, with same_seller flag          (TASK-25)
  4. call integration.check_payment (the real pipeline)              (TASK-05)
  5. NEW: enhance explanation with Khuzeka (generate_ai_explanation) (TASK-12+)
  6. persist Check + Fingerprint rows                                (TASK-22)
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
    compute_reference_hash,
    dup_result,
    find_duplicates,
    save_fingerprint,
)
from app.db.models import Check, Seller
from app.schemas.check import CheckResponse, HealthResponse
from engine.ai_explainer import generate_ai_explanation  # NEW: Khuzeka

logger = logging.getLogger(__name__)

router = APIRouter(tags=["check"])


@router.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok")


@router.post("/check", response_model=CheckResponse)
async def check_endpoint(
    image: UploadFile = File(...),
    expected_amount: float = Form(...),
    expected_recipient: str = Form(...),
    expected_reference: str = Form(...),
    db: Session = Depends(get_db),
    seller: Seller = Depends(get_current_seller),
):
    # 1. Safety gate
    raw_bytes, mime_type = await validate_upload(image)

    # 2. Compute fingerprint (Returns 3 values now)
    hash_hex, hash_int, hash_algo = compute_image_hash(raw_bytes)

<<<<<<< HEAD
    # ------------------------------------------------------------------ #
    # 3. Duplicate lookup – reference hash (primary) + pHash (secondary)  #
    # ------------------------------------------------------------------ #
    ref_hash = compute_reference_hash(expected_reference, expected_amount)
    matches = find_duplicates(db, hash_int, seller.id, reference_hash=ref_hash)
    dup = dup_result(matches)          # {"found": bool, "same_seller": bool, "reason": ...}
=======
    # 3. Duplicate lookup (Takes 4 arguments now)
    matches = find_duplicates(db, hash_hex, hash_algo, seller.id)
    dup = dup_result(matches)
>>>>>>> aba3f0e96c9b960aa272c9eec4807c3b8cc2fdaf
    is_duplicate = dup["found"]

    # 4. Run the real pipeline
    (
        verdict,
        reasons,
        engine_explanation,
        confidence,
        raw_ocr_text,
        extracted,
        suggested_reply, # NEW
    ) = _run_pipeline(
        raw_bytes=raw_bytes,
        expected_amount=expected_amount,
        expected_recipient=expected_recipient,
        expected_reference=expected_reference,
        dup=dup,
        seller_id=seller.id,
    )

    # 5. Enhance explanation with Khuzeka
    is_stub = raw_ocr_text is None
    final_explanation, explanation_source = _enhance_explanation(
        verdict=verdict,
        reasons=reasons,
        engine_explanation=engine_explanation,
        is_stub=is_stub,
    )

    # 6. Persist Check row
    check_row = Check(
        seller_id=seller.id,
        verdict=verdict,
        reasons=reasons,
        raw_file_path=None,
        raw_file_uploaded_at=None,
    )
    db.add(check_row)
    db.flush()

<<<<<<< HEAD
    saved_ref = extracted.get("reference") or expected_reference
    saved_ref_hash = compute_reference_hash(saved_ref, extracted.get("amount") or expected_amount)
    save_fingerprint(db, seller.id, check_row.id, hash_hex, hash_int, reference_hash=saved_ref_hash)
=======
    # Save fingerprint (Takes 6 arguments now)
    save_fingerprint(db, seller.id, check_row.id, hash_hex, hash_int, hash_algo)
>>>>>>> aba3f0e96c9b960aa272c9eec4807c3b8cc2fdaf
    db.commit()
    db.refresh(check_row)

    return CheckResponse(
        check_id=check_row.id,
        verdict=verdict,
        reasons=reasons,
        explanation=final_explanation,
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
        explanation_source=explanation_source,
        suggested_reply=suggested_reply, # NEW
    )


# ---------------------------------------------------------------------------
# Pipeline bridge
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
            result.get("suggested_reply", ""), # NEW
        )
    except Exception as exc:
        logger.warning("Pipeline unavailable (%s: %s) — returning stub.", type(exc).__name__, exc)
        return (
            "WAIT",
            ["engine_unavailable"],
            "Pipeline not connected yet. This is a stub verdict.",
            None,
            None,
            {},
            "", # Fallback for suggested_reply
        )


# ---------------------------------------------------------------------------
# Khuzeka enhancement
# ---------------------------------------------------------------------------
def _enhance_explanation(
    verdict: str,
    reasons: list,
    engine_explanation: str,
    is_stub: bool,
) -> tuple:
    if is_stub:
        return engine_explanation, "stub"
    try:
        ai_text = generate_ai_explanation({
            "verdict": verdict,
            "reasons": reasons,
            "explanation": engine_explanation,
        })
        if ai_text and ai_text.strip() != engine_explanation.strip():
            return ai_text, "ai"
    except Exception as exc:
        logger.warning("AI explainer failed (%s: %s) — using engine text.", type(exc).__name__, exc)
    return engine_explanation, "engine"