import io
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


def _screenshot(
    lines: list[str],
    *,
    size: tuple[int, int] = (900, 480),
    background: tuple[int, int, int] = (255, 255, 255),
    foreground: tuple[int, int, int] = (20, 20, 20),
    font_size: int = 38,
) -> Image.Image:
    image = Image.new("RGB", size, background)
    draw = ImageDraw.Draw(image)
    font = _font(font_size)
    y = 35
    for line in lines:
        draw.text((45, y), line, fill=foreground, font=font)
        y += 78
    return image


def _degraded_screenshot() -> Image.Image:
    image = _screenshot(
        ["PAID 1800.00", "TO THABO SNEAKERS", "REF: SNK1800"],
        size=(640, 340),
        background=(235, 235, 235),
        foreground=(150, 150, 150),
        font_size=38,
    )
    degraded = (
        image.resize((260, 138), Image.Resampling.LANCZOS)
        .filter(ImageFilter.GaussianBlur(0.5))
    )
    buffer = io.BytesIO()
    degraded.save(buffer, format="JPEG", quality=40, optimize=True)
    buffer.seek(0)
    with Image.open(buffer) as compressed:
        compressed.load()
        return compressed.copy()


@pytest.mark.parametrize(
    "image,expected",
    [
        pytest.param(
            _screenshot(
                [
                    "PAYMENT SENT",
                    "Amount: R1,800.00",
                    "To: Thabo Sneakers",
                    "Reference: SNK1800",
                ]
            ),
            {
                "amount": 1800.0,
                "recipient": "Thabo Sneakers",
                "reference": "SNK1800",
            },
            id="light_comma_amount",
        ),
        pytest.param(
            _screenshot(
                [
                    "PAYMENT SENT",
                    "Amount: R 1 800.00",
                    "Beneficiary: Ndlovu & Sons",
                    "Reference: INV202617",
                ],
                background=(22, 22, 22),
                foreground=(245, 245, 245),
            ),
            {
                "amount": 1800.0,
                "recipient": "Ndlovu & Sons",
                "reference": "INV202617",
            },
            id="dark_mode_spaced_amount",
        ),
        pytest.param(
            _degraded_screenshot(),
            {
                "amount": 1800.0,
                "recipient": "THABO SNEAKERS",
                "reference": "SNK1800",
            },
            id="degraded_jpeg_plain_amount",
        ),
    ],
)
def test_extracts_fields_from_synthetic_screenshots(image, expected):
    from ocr.extract import extract_fields
    from ocr.tesseract_engine import run_ocr

    ocr_result = run_ocr(image)
    fields = extract_fields(ocr_result.text)

    assert ocr_result.preprocessed is True
    assert fields.amount == expected["amount"]
    assert (fields.recipient or "").casefold() == expected["recipient"].casefold()
    assert fields.reference == expected["reference"]
