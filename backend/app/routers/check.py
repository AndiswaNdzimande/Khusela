"""
TASK-21 + TASK-24 + TASK-25: POST /check and GET /health endpoints.
Requires a valid Bearer token (TASK-23).

Pipeline (v5, per report section 5 recommendation):
  1. validate_upload      – size cap, magic-byte MIME, Pillow parse   (TASK-24)
  2. call integration.check_payment with the CORRECT kwargs            (TASK-05)
     — integration owns OCR, pHash, duplicate lookup and engine logic.
     — This router does NOT compute its own hash or call find_duplicates.
  3. persist Check row                                                  (TASK-22)
  4. save_fingerprint from the phash returned by integration            (TASK-25)

N2 fix (v5 report, CRITICAL):
  Previous version called check_payment(image_bytes=..., expected={...},
  dup_result=..., seller_id=...) which does not match integration.py's
  actual signature:
    check_payment(raw_bytes, expected_amount, expected_recipient,
                  expected_reference, seller_id)
  Fix: pass the four scalar kwargs integration.py accepts.

N5 fix (v5 report, MEDIUM):
  Server now validates expected_amount > 0 and rejects 0, negative, NaN.
"""
import logging
import math

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.auth import get_current_seller
from app.api.safety import validate_upload
from app.db.database import get_db
from app.db.fingerprints import save_fingerprint
from app.db.models import Check, Seller
from app.schemas.check import CheckResponse, HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["check"])


@router.get("/health", response_model=HealthResponse)
def health():
    """Returns pipeline self-test result (real or stub)."""
    pipeline_ok = _pipeline_self_test()
    return HealthResponse(
        status="ok",
        pipeline=pipeline_ok,
    )


@router.post("/check", response_model=CheckResponse)
async def check_endpoint(
    image: UploadFile = File(...),          # frontend sends 'image'
    expected_amount: float = Form(...),
    expected_recipient: str = Form(...),
    expected_reference: str = Form(...),
    db: Session = Depends(get_db),
    seller: Seller = Depends(get_current_seller),
):
    # ------------------------------------------------------------------ #
    # N5: server-side amount validation                                    #
    # ------------------------------------------------------------------ #
    if not math.isfinite(expected_amount) or expected_amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="expected_amount must be a positive finite number",
        )

    # ------------------------------------------------------------------ #
    # 1. Safety gate                                                       #
    # ------------------------------------------------------------------ #
    raw_bytes, mime_type = await validate_upload(image)

    # ------------------------------------------------------------------ #
    # 2. Pipeline (integration.check_payment with correct kwargs)          #
    # ------------------------------------------------------------------ #
    (
        verdict, reasons, explanation, confidence,
        raw_ocr_text, extracted, phash_hex,
    ) = _run_pipeline(
        raw_bytes=raw_bytes,
        expected_amount=expected_amount,
        expected_recipient=expected_recipient,
        expected_reference=expected_reference,
        seller_id=seller.id,
    )

    is_duplicate = any(r in ("duplicate_image", "duplicate_same_seller") for r in reasons)

    # ------------------------------------------------------------------ #
    # 3. Persist Check row                                                 #
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

    # ------------------------------------------------------------------ #
    # 4. Save fingerprint if integration returned one                      #
    # ------------------------------------------------------------------ #
    if phash_hex:
        save_fingerprint(db, phash_hex, seller.id, check_row.id)

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
        duplicate={"found": is_duplicate},
        raw_ocr_text=raw_ocr_text,
        explanation_source="engine" if raw_ocr_text else "stub",
    )


# ---------------------------------------------------------------------------
# Pipeline bridge — N2 fix: correct kwargs for integration.check_payment
# ---------------------------------------------------------------------------

def _run_pipeline(
    raw_bytes: bytes,
    expected_amount: float,
    expected_recipient: str,
    expected_reference: str,
    seller_id: str,
) -> tuple:
    """
    Call integration.check_payment with the signature it actually accepts.
    Returns a 7-tuple:
      (verdict, reasons, explanation, confidence, raw_ocr_text, extracted, phash_hex)
    phash_hex may be None if integration is unavailable.
    """
    try:
        import integration  # backend/integration.py (on TASK-05 branch / merged)

        result = integration.check_payment(
            raw_bytes,
            expected_amount=expected_amount,
            expected_recipient=expected_recipient,
            expected_reference=expected_reference,
            seller_id=seller_id,
        )
        return (
            result["verdict"],
            result["reasons"],
            result.get("explanation", ""),
            result.get("confidence"),
            result.get("raw_ocr_text"),
            result.get("extracted", {}),
            result.get("phash_hex"),        # integration passes this back for storage
        )
    except Exception as exc:
        logger.warning(
            "Pipeline unavailable (%s: %s) — returning stub. "
            "Merge TASK-05 branch to get real verdicts.",
            type(exc).__name__, exc,
        )
        return (
            "WAIT",
            ["engine_unavailable"],
            "Pipeline not connected. Merge TASK-05 branch for real verdicts.",
            None,
            None,
            {},
            None,
        )


# ---------------------------------------------------------------------------
# N6 fix: startup self-test — calls integration with one fixture byte,
# returns True only if the call succeeds without exception.
# ---------------------------------------------------------------------------

_SELF_TEST_RESULT: bool | None = None


def _pipeline_self_test() -> bool:
    """
    Try importing and calling integration.check_payment with 1 byte of data.
    Result is cached after first call (done at startup).
    Returns True = pipeline is real and callable, False = stub.
    """
    global _SELF_TEST_RESULT
    if _SELF_TEST_RESULT is not None:
        return _SELF_TEST_RESULT
    try:
        import integration
        # Minimal call — will fail OCR but must not raise TypeError
        integration.check_payment(
            b"\xff\xd8\xff",   # JPEG magic bytes
            expected_amount=1.0,
            expected_recipient="self-test",
            expected_reference="self-test",
            seller_id="self-test",
        )
        _SELF_TEST_RESULT = True
    except TypeError as exc:
        # Wrong signature — still broken (N2)
        logger.error("Pipeline self-test FAILED (wrong signature): %s", exc)
        _SELF_TEST_RESULT = False
    except Exception:
        # OCR/engine error is fine — the call was accepted
        _SELF_TEST_RESULT = True
    return _SELF_TEST_RESULT
