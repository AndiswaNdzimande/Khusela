"""
TASK-21 + TASK-24 + TASK-25: POST /check endpoint.
Requires a valid Bearer token (TASK-23).
Pipeline:
  1. validate_upload  – size, MIME, parse check        (TASK-24)
  2. compute fingerprint                                (TASK-25)
  3. find_duplicates from other sellers                 (TASK-25)
  4. call the existing engine.evaluate                  (existing code)
  5. persist Check + Fingerprint rows                   (TASK-22)
  6. store raw file temporarily; scheduler cleans up    (TASK-26)
"""
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.api.auth import get_current_seller
from app.api.safety import validate_upload
from app.db.database import get_db
from app.db.fingerprints import (
    compute_image_hash,
    compute_pdf_hash,
    find_duplicates,
    save_fingerprint,
)
from app.db.models import Check, Seller
from app.schemas.check import CheckResponse, HealthResponse

RAW_UPLOAD_DIR = Path(os.getenv("RAW_UPLOAD_DIR", "./uploads/raw"))

router = APIRouter(tags=["check"])


@router.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok")


@router.post("/check", response_model=CheckResponse)
async def check(
    file: UploadFile = File(...),
    expected_amount: float = Form(...),
    expected_recipient: str = Form(...),
    expected_reference: str = Form(...),
    db: Session = Depends(get_db),
    seller: Seller = Depends(get_current_seller),
):
    # ------------------------------------------------------------------ #
    # 1. Safety gate                                                       #
    # ------------------------------------------------------------------ #
    raw_bytes, mime_type = await validate_upload(file)

    # ------------------------------------------------------------------ #
    # 2. Persist raw file temporarily (deleted by scheduler after 24 h)   #
    # ------------------------------------------------------------------ #
    RAW_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ext = "pdf" if mime_type == "application/pdf" else mime_type.split("/")[1]
    raw_filename = f"{uuid.uuid4()}.{ext}"
    raw_path = RAW_UPLOAD_DIR / raw_filename
    raw_path.write_bytes(raw_bytes)
    upload_time = datetime.now(timezone.utc)

    # ------------------------------------------------------------------ #
    # 3. Compute fingerprint                                               #
    # ------------------------------------------------------------------ #
    if mime_type == "application/pdf":
        hash_hex, hash_int = compute_pdf_hash(raw_bytes)
    else:
        hash_hex, hash_int = compute_image_hash(raw_bytes)

    # ------------------------------------------------------------------ #
    # 4. Cross-seller duplicate lookup                                     #
    # ------------------------------------------------------------------ #
    dup_matches = find_duplicates(db, hash_int, seller.id)
    is_duplicate = len(dup_matches) > 0

    # ------------------------------------------------------------------ #
    # 5. Call the existing rule engine (or stub if not available)          #
    # ------------------------------------------------------------------ #
    verdict, reasons, explanation, confidence, raw_ocr_text, extracted = _run_engine(
        raw_bytes=raw_bytes,
        mime_type=mime_type,
        expected_amount=expected_amount,
        expected_recipient=expected_recipient,
        expected_reference=expected_reference,
        is_duplicate=is_duplicate,
        seller_id=seller.id,
    )

    # ------------------------------------------------------------------ #
    # 6. Persist Check row                                                 #
    # ------------------------------------------------------------------ #
    check_row = Check(
        seller_id=seller.id,
        verdict=verdict,
        reasons=reasons,
        raw_file_path=str(raw_path),
        raw_file_uploaded_at=upload_time,
    )
    db.add(check_row)
    db.flush()  # get check_row.id without committing yet

    # ------------------------------------------------------------------ #
    # 7. Persist Fingerprint row                                           #
    # ------------------------------------------------------------------ #
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
        duplicate={"found": is_duplicate, "matches": len(dup_matches)},
        raw_ocr_text=raw_ocr_text,
        explanation_source="engine",
    )


# --------------------------------------------------------------------------- #
# Engine bridge – calls the existing backend engine if available,             #
# falls back to a labelled stub so the API stays runnable without it.         #
# --------------------------------------------------------------------------- #
def _run_engine(
    raw_bytes: bytes,
    mime_type: str,
    expected_amount: float,
    expected_recipient: str,
    expected_reference: str,
    is_duplicate: bool,
    seller_id: str,
) -> tuple:
    try:
        from engine import evaluate  # existing module in backend/
        from ocr import run_ocr, extract_fields

        ocr_result = run_ocr(raw_bytes)
        fields = extract_fields(ocr_result.get("text", ""))
        result = evaluate(
            extracted=fields,
            expected={
                "amount": expected_amount,
                "recipient": expected_recipient,
                "reference": expected_reference,
            },
            duplicate={"found": is_duplicate, "same_seller": False},
            ocr_confidence=ocr_result.get("confidence", 0.0),
        )
        return (
            result["verdict"],
            result["reasons"],
            result.get("explanation", ""),
            result.get("confidence"),
            ocr_result.get("text"),
            fields,
        )
    except ImportError:
        # Engine not on sys.path yet – return an honest stub
        return (
            "WAIT",
            ["engine_unavailable"],
            "Engine modules not connected yet. Results are a stub.",
            None,
            None,
            {},
        )
