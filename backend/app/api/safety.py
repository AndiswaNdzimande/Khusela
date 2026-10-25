"""
TASK-24: Upload safety gate.
Checks (in order):
  1. Size cap: 5 MB enforced while reading the stream        → 413
  2. MIME type from magic bytes (not Content-Type header)    → 415
  3. Parse check: Pillow for images                          → 422
Returns a tuple (bytes, mime_type) ready for fingerprinting.
"""
import io
import uuid
from typing import Tuple

import magic
from fastapi import HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError

MAX_BYTES = 5 * 1024 * 1024  # 5 MB

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "application/pdf",
}


async def validate_upload(file: UploadFile) -> Tuple[bytes, str]:
    """
    Read the upload, enforce size + type + parse checks.
    Returns (raw_bytes, mime_type).
    Raises HTTPException on any violation.
    """
    # --- 1. Read with size cap ---
    chunks = []
    total = 0
    async for chunk in file:
        total += len(chunk)
        if total > MAX_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds the 5 MB limit ({total} bytes received so far)",
            )
        chunks.append(chunk)
    raw = b"".join(chunks)

    if len(raw) == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Empty file",
        )

    # --- 2. Magic-byte MIME detection ---
    detected_mime = magic.from_buffer(raw[:2048], mime=True)
    if detected_mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File type '{detected_mime}' is not allowed. Accepted: JPEG, PNG, PDF",
        )

    # --- 3. Parse check ---
    if detected_mime in ("image/jpeg", "image/png"):
        _verify_image(raw)
    # PDF parse is handled by the Docker sandbox (TASK-27); a basic header check suffices here.
    elif detected_mime == "application/pdf":
        _verify_pdf_header(raw)

    return raw, detected_mime


def _verify_image(raw: bytes) -> None:
    """Open and fully verify the image with Pillow."""
    try:
        img = Image.open(io.BytesIO(raw))
        img.verify()          # catches truncated / corrupt files
    except (UnidentifiedImageError, Exception) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Image could not be parsed: {exc}",
        )


def _verify_pdf_header(raw: bytes) -> None:
    """Minimal PDF header check before the sandbox parses the full file."""
    if not raw.startswith(b"%PDF"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="File does not appear to be a valid PDF",
        )


def safe_filename() -> str:
    """Return a UUID-based filename, ignoring whatever the client sent."""
    return str(uuid.uuid4())
