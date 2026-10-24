import os

import pytest
from PIL import Image, ImageDraw, ImageFilter, ImageFont

pytestmark = pytest.mark.skipif(
    os.getenv("KHUSELA_OCR_INTEGRATION") != "1",
    reason="set KHUSELA_OCR_INTEGRATION=1 to run real Tesseract/Docker OCR",
)


def _font(size: int) -> ImageFont.ImageFont:
    for name in ("DejaVuSans.ttf", "Arial.ttf", "Helvetica.ttc"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


def _screenshot() -> Image.Image:
    image = Image.new("RGB", (900, 480), "white")
    draw = ImageDraw.Draw(image)
    font = _font(38)
    y = 35
    for line in (
        "PAYMENT SENT",
        "Amount: R1,800.00",
        "To: Thabo Sneakers",
        "Reference: SNK1800",
    ):
        draw.text((45, y), line, fill=(20, 20, 20), font=font)
        y += 78
    return image


def test_blurry_screenshot_gets_low_confidence_and_returns_raw_text():
    from ocr.tesseract_engine import run_ocr

    sharp = _screenshot()
    blurred = sharp.filter(ImageFilter.GaussianBlur(4))

    sharp_result = run_ocr(sharp)
    blurred_result = run_ocr(blurred)

    assert "R1,800.00" in sharp_result.raw_text
    assert sharp_result.confidence >= 0.75
    assert sharp_result.confidence_label == "high"

    assert blurred_result.confidence < 0.5
    assert blurred_result.confidence < sharp_result.confidence
    assert blurred_result.confidence_label == "low"
    assert blurred_result.is_reliable is False
    assert isinstance(blurred_result.raw_text, str)

    output = blurred_result.as_dict()
    assert output["raw_ocr_text"] == blurred_result.raw_text
    assert output["ocr_confidence"] == blurred_result.confidence
    assert output["confidence_label"] == "low"
