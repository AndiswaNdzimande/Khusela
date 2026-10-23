"""Image preprocessing that makes payment screenshots easier for Tesseract.

The pipeline is deliberately simple and deterministic:

1. Flatten transparency and convert to grayscale.
2. Resize small screenshots up (and huge ones down) to a Tesseract-friendly size.
3. Improve contrast.
4. Optional light denoising.
5. Auto-detect dark mode and invert it to dark-text-on-white.
6. Binarise with Otsu or an adaptive local threshold.

Everything is implemented with Pillow + NumPy so it works on every laptop
without OpenCV/compiler setup. See ``docs/ocr-preprocessing.md``.

Command line usage::

    python backend/ocr/preprocess.py --image screenshot.png --out clean.png
    python backend/ocr/preprocess.py --image screenshot.png --ocr
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, BinaryIO, Union

import numpy as np
from PIL import Image, ImageFilter, ImageOps

ImageSource = Union[str, Path, bytes, bytearray, BinaryIO, Image.Image]

THRESHOLD_METHODS = ("none", "otsu", "adaptive")


@dataclass(frozen=True)
class PreprocessConfig:
    """Tunable knobs for :func:`preprocess_image`."""

    grayscale: bool = True
    autocontrast: bool = True
    target_min_side: int = 1000
    max_side: int = 2400
    max_scale: float = 4.0
    threshold: str = "otsu"
    block_size: int = 31
    offset: int = 10
    denoise: bool = False
    # True, False, or "auto" (invert when the image is mostly dark).
    invert: bool | str = "auto"
    output_format: str = "PNG"

    def __post_init__(self) -> None:
        if self.threshold not in THRESHOLD_METHODS:
            raise ValueError(
                f"threshold must be one of {THRESHOLD_METHODS}, got {self.threshold!r}"
            )
        if not self.grayscale and self.threshold != "none":
            raise ValueError("threshold requires grayscale=True")
        if self.target_min_side < 0 or self.max_side < 0:
            raise ValueError("target_min_side and max_side must be >= 0")
        if self.max_scale < 1:
            raise ValueError("max_scale must be >= 1")
        if self.block_size < 3 or self.block_size % 2 == 0:
            raise ValueError("block_size must be an odd number >= 3")
        if self.offset < 0:
            raise ValueError("offset must be >= 0")
        if self.invert not in (True, False, "auto"):
            raise ValueError("invert must be True, False or 'auto'")


def load_image(image: ImageSource) -> Image.Image:
    """Load paths, bytes, binary file objects or PIL images into a PIL image.

    EXIF orientation is applied so phone screenshots are not sideways.
    """
    if isinstance(image, Image.Image):
        loaded = image.copy()
    elif isinstance(image, (str, Path)):
        with Image.open(image) as opened:
            opened.load()
            loaded = opened.copy()
    elif isinstance(image, (bytes, bytearray)):
        with Image.open(BytesIO(bytes(image))) as opened:
            opened.load()
            loaded = opened.copy()
    else:
        read = getattr(image, "read", None)
        if not callable(read):
            raise TypeError(
                "image must be a path, bytes, a binary file object or a PIL.Image.Image"
            )
        data = read()
        if isinstance(data, str):
            data = data.encode()
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("File object did not return bytes.")
        with Image.open(BytesIO(bytes(data))) as opened:
            opened.load()
            loaded = opened.copy()

    return ImageOps.exif_transpose(loaded)


def _flatten_transparency(image: Image.Image) -> Image.Image:
    if image.mode in ("RGBA", "LA") or "transparency" in image.info:
        rgba = image.convert("RGBA")
        background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        return Image.alpha_composite(background, rgba).convert("RGB")
    if image.mode not in ("L", "RGB"):
        return image.convert("RGB")
    return image


def to_grayscale(image: Image.Image) -> Image.Image:
    """Flatten transparency and return an 8-bit grayscale image."""
    return ImageOps.grayscale(_flatten_transparency(image))


def resize_for_ocr(
    image: Image.Image,
    *,
    target_min_side: int = 1000,
    max_side: int = 2400,
    max_scale: float = 4.0,
) -> Image.Image:
    """Resize an image so the short side is near ``target_min_side``.

    Small screenshots are upscaled (up to ``max_scale``); very large images are
    downscaled so the longest side is at most ``max_side``. Aspect ratio is
    preserved and LANCZOS resampling keeps text edges clean.
    """
    width, height = image.size
    if width <= 0 or height <= 0:
        return image

    scale = 1.0
    if target_min_side > 0:
        scale = target_min_side / min(width, height)
    scale = min(scale, max_scale)
    if max_side > 0:
        scale = min(scale, max_side / max(width, height))

    if abs(scale - 1.0) < 0.01:
        return image

    new_size = (max(1, round(width * scale)), max(1, round(height * scale)))
    return image.resize(new_size, Image.Resampling.LANCZOS)


def otsu_threshold(image: Image.Image) -> int:
    """Return the Otsu threshold (0-255) for a grayscale image."""
    gray = np.asarray(image.convert("L"), dtype=np.uint8)
    histogram = np.bincount(gray.ravel(), minlength=256).astype(np.float64)
    total = histogram.sum()
    if total == 0:
        return 127

    probabilities = histogram / total
    omega = np.cumsum(probabilities)
    levels = np.arange(256, dtype=np.float64)
    mu = np.cumsum(probabilities * levels)
    mu_total = mu[-1]

    denominator = omega * (1.0 - omega)
    variance = np.zeros(256, dtype=np.float64)
    valid = denominator > 0
    variance[valid] = (mu_total * omega[valid] - mu[valid]) ** 2 / denominator[valid]

    return int(np.argmax(variance))


def _adaptive_threshold_array(
    gray: np.ndarray,
    block_size: int,
    offset: int,
) -> np.ndarray:
    """Adaptive mean threshold using an integral image (no OpenCV needed)."""
    array = gray.astype(np.float64)
    height, width = array.shape

    integral = np.zeros((height + 1, width + 1), dtype=np.float64)
    integral[1:, 1:] = array.cumsum(axis=0).cumsum(axis=1)

    radius = block_size // 2
    rows = np.arange(height)
    columns = np.arange(width)
    y0 = np.clip(rows - radius, 0, height)
    y1 = np.clip(rows + radius + 1, 0, height)
    x0 = np.clip(columns - radius, 0, width)
    x1 = np.clip(columns + radius + 1, 0, width)

    sums = (
        integral[np.ix_(y1, x1)]
        - integral[np.ix_(y0, x1)]
        - integral[np.ix_(y1, x0)]
        + integral[np.ix_(y0, x0)]
    )
    counts = (y1 - y0)[:, None] * (x1 - x0)[None, :]
    local_mean = sums / np.maximum(counts, 1)

    return np.where(array > local_mean - offset, 255, 0).astype(np.uint8)


def threshold_image(
    image: Image.Image,
    method: str = "otsu",
    *,
    block_size: int = 31,
    offset: int = 10,
) -> Image.Image:
    """Binarise a grayscale image. Returns an image with only 0 and 255."""
    if method not in THRESHOLD_METHODS:
        raise ValueError(f"method must be one of {THRESHOLD_METHODS}, got {method!r}")

    gray = image.convert("L")
    if method == "none":
        return gray

    if method == "otsu":
        cutoff = otsu_threshold(gray)
        lookup = [0 if value <= cutoff else 255 for value in range(256)]
        return gray.point(lookup, mode="L")

    array = _adaptive_threshold_array(np.asarray(gray), block_size, offset)
    return Image.fromarray(array, mode="L")


def _is_dark(image: Image.Image) -> bool:
    gray = np.asarray(image.convert("L"), dtype=np.uint8)
    return float(gray.mean()) < 127.0


def preprocess_image(
    image: ImageSource,
    config: PreprocessConfig | None = None,
) -> Image.Image:
    """Run the full preprocessing pipeline and return a PIL image."""
    settings = config or PreprocessConfig()
    processed = load_image(image)

    if settings.grayscale:
        processed = to_grayscale(processed)
    else:
        processed = _flatten_transparency(processed)

    processed = resize_for_ocr(
        processed,
        target_min_side=settings.target_min_side,
        max_side=settings.max_side,
        max_scale=settings.max_scale,
    )

    should_invert: bool | str = False
    if settings.grayscale:
        should_invert = settings.invert
        if should_invert == "auto":
            # Decide before autocontrast: stretching the histogram can make a
            # dark-mode screenshot look bright even though it is not.
            should_invert = _is_dark(processed)

    if settings.autocontrast:
        processed = ImageOps.autocontrast(processed, cutoff=1)

    if settings.denoise:
        processed = processed.filter(ImageFilter.MedianFilter(3))

    if settings.grayscale:
        if should_invert:
            processed = ImageOps.invert(processed.convert("L"))

        if settings.threshold != "none":
            processed = threshold_image(
                processed,
                settings.threshold,
                block_size=settings.block_size,
                offset=settings.offset,
            )

    return processed


def preprocess_bytes(
    image: ImageSource,
    config: PreprocessConfig | None = None,
) -> bytes:
    """Preprocess and encode an image, ready to hand to Tesseract/Docker."""
    settings = config or PreprocessConfig()
    processed = preprocess_image(image, settings)
    buffer = BytesIO()
    save_kwargs: dict[str, Any] = {}
    if settings.output_format.upper() == "JPEG":
        save_kwargs = {"quality": 95}
        if processed.mode not in ("L", "RGB"):
            processed = processed.convert("RGB")
    elif settings.output_format.upper() == "PNG":
        save_kwargs = {"optimize": True}

    processed.save(buffer, format=settings.output_format, **save_kwargs)
    return buffer.getvalue()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Preprocess a payment screenshot for Tesseract OCR"
    )
    parser.add_argument("--image", required=True, help="input image path")
    parser.add_argument("--out", help="where to save the preprocessed image")
    parser.add_argument(
        "--threshold",
        choices=THRESHOLD_METHODS,
        default="otsu",
        help="binarisation method (default: otsu)",
    )
    parser.add_argument("--no-grayscale", action="store_true")
    parser.add_argument("--no-autocontrast", action="store_true")
    parser.add_argument("--denoise", action="store_true")
    parser.add_argument(
        "--invert",
        choices=["auto", "true", "false"],
        default="auto",
        help="invert dark-mode images (default: auto)",
    )
    parser.add_argument("--target-min-side", type=int, default=1000)
    parser.add_argument("--max-side", type=int, default=2400)
    parser.add_argument("--max-scale", type=float, default=4.0)
    parser.add_argument("--ocr", action="store_true", help="run OCR on the result")
    parser.add_argument("--json", action="store_true", help="print a JSON summary")
    args = parser.parse_args(argv)

    invert: bool | str
    if args.invert == "auto":
        invert = "auto"
    else:
        invert = args.invert == "true"

    config = PreprocessConfig(
        grayscale=not args.no_grayscale,
        autocontrast=not args.no_autocontrast,
        target_min_side=args.target_min_side,
        max_side=args.max_side,
        max_scale=args.max_scale,
        threshold=args.threshold,
        denoise=args.denoise,
        invert=invert,
    )

    try:
        processed = preprocess_image(args.image, config)
        output_path = args.out
        if output_path is None and not args.ocr:
            source = Path(args.image)
            output_path = str(source.with_name(f"{source.stem}_preprocessed.png"))

        if output_path:
            processed.save(output_path)

        summary: dict[str, Any] = {
            "input": str(args.image),
            "output": output_path,
            "size": list(processed.size),
            "mode": processed.mode,
            "config": asdict(config),
        }

        if args.ocr:
            try:
                from .tesseract_engine import run_ocr
            except ImportError:  # running as a plain script
                from tesseract_engine import run_ocr  # type: ignore[no-redef]

            result = run_ocr(processed, preprocess=False)
            summary["ocr"] = result.as_dict()

        if args.json:
            print(json.dumps(summary, indent=2, ensure_ascii=False))
        else:
            if output_path:
                print(f"Preprocessed image saved to {output_path}")
            print(f"Size: {processed.size[0]}x{processed.size[1]} ({processed.mode})")
            if "ocr" in summary:
                ocr = summary["ocr"]
                print(f"OCR backend: {ocr['backend']} (confidence {ocr['confidence']:.2f})")
                print("--- text ---")
                print(ocr["text"])
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
