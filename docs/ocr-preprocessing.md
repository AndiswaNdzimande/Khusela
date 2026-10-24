# Image preprocessing for OCR

Payment screenshots are often small, compressed, low-contrast or dark mode.
Tesseract reads best when text is dark on a light background, has clean edges,
and is roughly 300 DPI. `backend/ocr/preprocess.py` normalises screenshots
before they reach Tesseract.

The pipeline uses Pillow + NumPy only, so there is no OpenCV or compiler setup
on team laptops.

## Pipeline

| Step | Default | What it does |
| --- | --- | --- |
| Transparency flatten | always | Composites transparent pixels onto white instead of black |
| Grayscale | on | Converts RGB/alpha images to 8-bit luminance |
| Resize | short side ~1000 px, long side ≤ 2400 px | Upscales small screenshots up to 4×; downscales huge captures |
| Autocontrast | on | Stretches faint text away from the background |
| Denoise | off | Optional 3×3 median filter |
| Auto-invert | on (`auto`) | Turns dark-mode screenshots into dark-text-on-white |
| Threshold | `otsu` | Binarises the image (or use `adaptive` / `none`) |

## Usage

`run_ocr()` preprocesses by default:

```python
from ocr import run_ocr

result = run_ocr("screenshot.png")
print(result.text)
print(result.confidence)
print(result.preprocessed)   # True
```

Disable it when the image is already clean:

```python
result = run_ocr("clean.png", preprocess=False)
```

Tune the pipeline with `PreprocessConfig`:

```python
from ocr import PreprocessConfig, run_ocr

config = PreprocessConfig(
    target_min_side=1200,
    max_side=3000,
    threshold="adaptive",   # uneven lighting / photos
    block_size=31,
    offset=10,
    denoise=True,
)

result = run_ocr("photo-of-receipt.jpg", preprocess_config=config)
```

Preprocess without OCR and get PNG bytes:

```python
from ocr import preprocess_bytes, preprocess_image

png_bytes = preprocess_bytes("screenshot.png")
image = preprocess_image("screenshot.png")
image.save("clean.png")
```

## Command line

```bash
# Save a preprocessed copy
python backend/ocr/preprocess.py --image screenshot.png --out clean.png

# Preprocess and immediately run OCR
python backend/ocr/preprocess.py --image screenshot.png --ocr

# Inspect the settings and output size as JSON
python backend/ocr/preprocess.py --image screenshot.png --out clean.png --json

# Off for a clean, already-binary image
python backend/ocr/tesseract_engine.py --image clean.png --no-preprocess
```

## Tuning guide

| Setting | Options | When to change it |
| --- | --- | --- |
| `threshold` | `otsu` (default), `adaptive`, `none` | Use `adaptive` for uneven lighting or photos; use `none` if Tesseract loses thin strokes |
| `target_min_side` | default `1000` | Increase to `1400–1800` for very small screenshots |
| `max_side` | default `2400` | Lower to speed up OCR on huge 4K screenshots |
| `max_scale` | default `4.0` | Caps upscaling so a tiny thumbnail does not become enormous |
| `invert` | `auto` (default), `true`, `false` | Force `true`/`false` if auto-detection guesses wrong |
| `denoise` | default `false` | Enable for noisy photos, leave off for crisp screenshots |
| `block_size` | odd number, default `31` | Larger blocks for bigger text; smaller blocks for dense text |
| `offset` | default `10` | Higher values keep more grey background as white in adaptive mode |

## Example result

The integration test builds a 220×96 low-contrast JPEG (quality 32 with slight
blur) containing `PAID R1,800.00` and `TO THABO SNEAKERS`.

Without preprocessing, Tesseract misreads the amount:

```text
PAID #17,800.00
TO THABO SNEAKERS.
```

With the default pipeline it reads correctly at ~0.92 confidence:

```text
PAID R1,800.00
TO THABO SNEAKERS
```

## Tests

The unit tests cover grayscale conversion, transparency, resizing, Otsu,
adaptive thresholding, dark-mode inversion, PNG bytes and configuration
validation:

```bash
python -m pytest backend/ocr/tests/test_preprocess.py
```

The end-to-end readability test needs a real backend (local Tesseract or the
Docker fallback):

```bash
KHUSELA_OCR_INTEGRATION=1 python -m pytest backend/ocr/tests/test_preprocess.py
```
