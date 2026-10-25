"""
TASK-24: Upload safety gate.
Tests: valid JPEG/PNG/PDF pass; oversized, wrong type, truncated, empty all rejected.
"""
import io
import struct

import pytest
from fastapi import UploadFile
from PIL import Image

from app.api.safety import validate_upload

# ---------------------------------------------------------------------------
# Helpers to generate minimal valid/invalid files
# ---------------------------------------------------------------------------

def _make_jpeg_bytes(width=10, height=10) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color="red").save(buf, format="JPEG")
    return buf.getvalue()


def _make_png_bytes(width=10, height=10) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color="blue").save(buf, format="PNG")
    return buf.getvalue()


def _make_pdf_bytes() -> bytes:
    return b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"


def _make_upload(data: bytes, content_type: str = "application/octet-stream") -> UploadFile:
    return UploadFile(filename="test", file=io.BytesIO(data), headers={"content-type": content_type})


# ---------------------------------------------------------------------------
# Valid files
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_valid_jpeg():
    raw, mime = await validate_upload(_make_upload(_make_jpeg_bytes(), "image/jpeg"))
    assert mime == "image/jpeg"


@pytest.mark.asyncio
async def test_valid_png():
    raw, mime = await validate_upload(_make_upload(_make_png_bytes(), "image/png"))
    assert mime == "image/png"


@pytest.mark.asyncio
async def test_valid_pdf():
    raw, mime = await validate_upload(_make_upload(_make_pdf_bytes(), "application/pdf"))
    assert mime == "application/pdf"


# ---------------------------------------------------------------------------
# Rejections
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_empty_file_rejected():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        await validate_upload(_make_upload(b""))
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_oversized_file_rejected():
    from fastapi import HTTPException
    big = b"\xff\xd8\xff" + b"A" * (5 * 1024 * 1024 + 1)  # fake JPEG header + oversized body
    with pytest.raises(HTTPException) as exc:
        await validate_upload(_make_upload(big))
    assert exc.value.status_code == 413


@pytest.mark.asyncio
async def test_exe_renamed_jpg_rejected():
    """An .exe file disguised as a .jpg must be rejected by magic bytes."""
    from fastapi import HTTPException
    exe_bytes = b"MZ" + b"\x00" * 100   # DOS/PE magic bytes
    with pytest.raises(HTTPException) as exc:
        await validate_upload(_make_upload(exe_bytes, "image/jpeg"))
    assert exc.value.status_code == 415


@pytest.mark.asyncio
async def test_truncated_image_rejected():
    """A JPEG with the first 20 bytes is structurally corrupt."""
    from fastapi import HTTPException
    truncated = _make_jpeg_bytes()[:20]
    with pytest.raises(HTTPException) as exc:
        await validate_upload(_make_upload(truncated, "image/jpeg"))
    # May be 415 (magic doesn't confirm JPEG) or 422 (parse fails)
    assert exc.value.status_code in (415, 422)
