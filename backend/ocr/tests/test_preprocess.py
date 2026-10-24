import io
import os
import re

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from ocr.preprocess import (
    PreprocessConfig,
    load_image,
    otsu_threshold,
    preprocess_bytes,
    preprocess_image,
    resize_for_ocr,
    threshold_image,
    to_grayscale,
)


def _payment_screenshot() -> Image.Image:
    """A small, low-contrast JPEG screenshot similar to a compressed capture."""
    width, height = 640, 280
    image = Image.new("RGB", (width, height), (232, 232, 232))
    draw = ImageDraw.Draw(image)

    try:
        font = ImageFont.load_default(size=42)
    except TypeError:  # Pillow < 10.1
        font = ImageFont.load_default()

    draw.text((40, 30), "PAID R1,800.00", fill=(155, 155, 155), font=font)
    draw.text((40, 130), "TO THABO SNEAKERS", fill=(155, 155, 155), font=font)

    # Shrink, soften and JPEG-compress the image to simulate a screenshot that
    # was sent through WhatsApp before the seller saved it.
    degraded = (
        image.resize((220, 96), Image.Resampling.LANCZOS)
        .filter(ImageFilter.GaussianBlur(0.6))
    )
    buffer = io.BytesIO()
    degraded.save(buffer, format="JPEG", quality=32, optimize=True)
    buffer.seek(0)
    with Image.open(buffer) as compressed:
        compressed.load()
        return compressed.copy()


def test_to_grayscale_converts_colour_image():
    image = Image.new("RGB", (10, 10), (255, 0, 0))

    gray = to_grayscale(image)

    assert gray.mode == "L"
    assert gray.getpixel((0, 0)) < 128


def test_transparent_pixels_become_white_instead_of_black():
    image = Image.new("RGBA", (10, 10), (0, 0, 0, 0))

    gray = to_grayscale(image)

    assert gray.getpixel((0, 0)) == 255


def test_resize_upscales_small_screenshots():
    image = Image.new("L", (200, 100), 255)

    resized = resize_for_ocr(
        image, target_min_side=500, max_scale=10, max_side=5000
    )

    assert resized.size == (1000, 500)


def test_resize_respects_max_scale():
    image = Image.new("L", (200, 100), 255)

    resized = resize_for_ocr(image, target_min_side=500, max_scale=4, max_side=5000)

    assert resized.size == (800, 400)


def test_resize_downscales_huge_images():
    image = Image.new("L", (5000, 1000), 255)

    resized = resize_for_ocr(image, target_min_side=1000, max_side=2400, max_scale=4)

    assert max(resized.size) == 2400
    assert resized.size[0] / resized.size[1] == pytest.approx(5.0)


def test_otsu_threshold_finds_dark_text():
    image = Image.new("L", (100, 100), 255)
    ImageDraw.Draw(image).rectangle((10, 10, 40, 40), fill=0)

    cutoff = otsu_threshold(image)
    binary = threshold_image(image, "otsu")

    assert cutoff < 128
    assert binary.getpixel((20, 20)) == 0
    assert binary.getpixel((80, 80)) == 255
    assert set(np.asarray(binary).ravel()) <= {0, 255}


def test_adaptive_threshold_handles_gradient_background():
    gradient = np.tile(np.linspace(140, 255, 200, dtype=np.uint8), (100, 1))
    gradient[40:60, 50:150] = 0
    image = Image.fromarray(gradient, mode="L")

    binary = threshold_image(image, "adaptive", block_size=31, offset=10)

    assert binary.getpixel((10, 10)) == 255
    assert binary.getpixel((100, 50)) == 0


def test_auto_invert_converts_dark_mode_to_dark_text_on_white():
    image = Image.new("RGB", (200, 100), (30, 30, 30))
    ImageDraw.Draw(image).rectangle((50, 30, 150, 70), fill=(230, 230, 230))

    config = PreprocessConfig(
        target_min_side=0,
        max_side=0,
        max_scale=1,
        threshold="otsu",
        invert="auto",
    )
    processed = preprocess_image(image, config)

    assert processed.getpixel((10, 10)) == 255
    assert processed.getpixel((100, 50)) == 0


def test_auto_invert_uses_original_brightness_before_autocontrast():
    # Exactly half light, half dark: the original mean is below 127, but after
    # autocontrast it would be above 127. Auto-invert must use the original.
    image = Image.new("L", (100, 100), 70)
    ImageDraw.Draw(image).rectangle((0, 0, 49, 99), fill=180)

    processed = preprocess_image(
        image,
        PreprocessConfig(
            threshold="none",
            target_min_side=0,
            max_side=0,
            max_scale=1,
            invert="auto",
        ),
    )

    assert processed.getpixel((75, 50)) == 255  # dark background inverted
    assert processed.getpixel((25, 50)) == 0  # light panel inverted


def test_threshold_none_keeps_grayscale():
    image = Image.new("RGB", (100, 50), (200, 200, 200))

    processed = preprocess_image(
        image,
        PreprocessConfig(
            threshold="none",
            target_min_side=0,
            max_side=0,
            max_scale=1,
            autocontrast=False,
        ),
    )

    assert processed.mode == "L"
    assert processed.size == (100, 50)


def test_preprocess_bytes_returns_png():
    image = _payment_screenshot()

    data = preprocess_bytes(image)

    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    assert Image.open(io.BytesIO(data)).mode in {"L", "1"}


def test_load_image_accepts_bytes_and_file_objects(tmp_path):
    source = tmp_path / "shot.png"
    Image.new("RGB", (20, 10), (255, 255, 255)).save(source)
    payload = source.read_bytes()

    from_bytes = load_image(payload)
    from_file = load_image(io.BytesIO(payload))
    from_path = load_image(source)

    assert from_bytes.size == from_file.size == from_path.size == (20, 10)


def test_invalid_config_is_rejected():
    with pytest.raises(ValueError):
        PreprocessConfig(threshold="magic")
    with pytest.raises(ValueError):
        PreprocessConfig(grayscale=False, threshold="otsu")
    with pytest.raises(ValueError):
        PreprocessConfig(block_size=30)
    with pytest.raises(ValueError):
        PreprocessConfig(invert="sometimes")


@pytest.mark.skipif(
    os.getenv("KHUSELA_OCR_INTEGRATION") != "1",
    reason="set KHUSELA_OCR_INTEGRATION=1 to run real Tesseract/Docker OCR",
)
def test_preprocessing_makes_low_contrast_screenshot_readable():
    from ocr.tesseract_engine import run_ocr

    screenshot = _payment_screenshot()
    raw = run_ocr(screenshot, preprocess=False)
    cleaned = run_ocr(screenshot, preprocess=True)

    normalized = re.sub(r"[^A-Z0-9]", "", cleaned.text.upper())

    assert "R180000" in normalized
    assert "THABO" in normalized
    assert cleaned.confidence >= 0.5
    assert cleaned.confidence >= raw.confidence
