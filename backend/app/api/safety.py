"""
TASK-24: Upload safety gate.
Checks (in order):
  1. Size cap: 5 MB enforced while reading in chunks     → 413
  2. MIME type from magic bytes (not Content-Type)       → 415
  3. Parse check: Pillow verify for images, PDF check    → 422
Returns (raw_bytes, mime_type) ready for processing.
"""
import io
import uuid
from typing import Tuple

import magic
from fastapi import HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError

MAX_BYTES = 5 * 1024 * 1024   # 5 MB
CHUNK_SIZE = 65_536            # 64 KB per read

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
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="File exceeds the 5 MB limit",
            )
        chunks.append(chunk)

    raw = b"".join(chunks)

    if len(raw) == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Empty file",
        )

    # Magic-byte MIME detection (ignores client Content-Type/filename)
    detected_mime = magic.from_buffer(raw[:2048], mime=True)
    if detected_mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"File type '{detected_mime}' is not allowed. "
                "Accepted: JPEG, PNG, PDF"
            ),
        )

    # Parse check: Pillow for images, header check for PDFs
    if detected_mime == "application/pdf":
        _verify_pdf(raw)
    else:
        _verify_image(raw)

    return raw, detected_mime


def _verify_image(raw: bytes) -> None:
    """Open and fully verify the image with Pillow. Catches truncated/corrupt files."""
    try:
        img = Image.open(io.BytesIO(raw))
        img.verify()
    except (UnidentifiedImageError, Exception) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Image could not be parsed: {exc}",
        )


def _verify_pdf(raw: bytes) -> None:
    """Verify that the PDF has a valid %PDF header."""
    if not raw.startswith(b"%PDF"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="PDF file is corrupted or missing a valid '%PDF' header.",
        )


def safe_filename(mime_type: str = "image/jpeg") -> str:
    """Return a UUID-based filename. Client-supplied name is never used."""
    if mime_type == "application/pdf":
        ext = "pdf"
    elif mime_type == "image/png":
        ext = "png"
    else:
        ext = "jpg"
    return f"{uuid.uuid4()}.{ext}"
