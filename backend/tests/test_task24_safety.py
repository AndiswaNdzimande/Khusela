"""
TASK-24: Upload safety gate.
Tests: valid JPEG/PNG pass; oversized, wrong type, truncated, empty all rejected.
Bug 2 fix verified: validate_upload uses read() loop, not async-for.
"""
import io

import pytest
from fastapi import HTTPException
from PIL import Image

from app.api.safety import validate_upload
from fastapi import UploadFile
from starlette.datastructures import UploadFile as StarletteUploadFile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_jpeg(width=10, height=10) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color="red").save(buf, format="JPEG")
    return buf.getvalue()


def _make_png(width=10, height=10) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color="blue").save(buf, format="PNG")
    return buf.getvalue()


def _upload(data: bytes, content_type: str = "application/octet-stream") -> UploadFile:
    return UploadFile(filename="test", file=io.BytesIO(data))


# ---------------------------------------------------------------------------
# Valid files
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_valid_jpeg():
    raw, mime = await validate_upload(_upload(_make_jpeg()))
    assert mime == "image/jpeg"
    assert len(raw) > 0


@pytest.mark.asyncio
async def test_valid_png():
    raw, mime = await validate_upload(_upload(_make_png()))
    assert mime == "image/png"
    assert len(raw) > 0


# ---------------------------------------------------------------------------
# Rejections
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_empty_file_rejected():
    with pytest.raises(HTTPException) as exc:
        await validate_upload(_upload(b""))
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_oversized_file_rejected():
    # Real JPEG header + enough padding to exceed 5 MB
    big = _make_jpeg() + b"A" * (5 * 1024 * 1024 + 1)
    with pytest.raises(HTTPException) as exc:
        await validate_upload(_upload(big))
    assert exc.value.status_code == 413


@pytest.mark.asyncio
async def test_exe_renamed_jpg_rejected():
    """An EXE file (DOS MZ magic bytes) must be rejected regardless of claimed type."""
    exe_bytes = b"MZ" + b"\x00" * 100
    with pytest.raises(HTTPException) as exc:
        await validate_upload(_upload(exe_bytes))
    assert exc.value.status_code == 415


@pytest.mark.asyncio
async def test_truncated_image_rejected():
    truncated = _make_jpeg()[:20]
    with pytest.raises(HTTPException) as exc:
        await validate_upload(_upload(truncated))
    assert exc.value.status_code in (415, 422)


@pytest.mark.asyncio
async def test_pdf_rejected():
    """PDF is out of contract — must be rejected with 415."""
    pdf_bytes = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF"
    with pytest.raises(HTTPException) as exc:
        await validate_upload(_upload(pdf_bytes))
    assert exc.value.status_code == 415
