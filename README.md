# Khusela

Khusela helps small business owners check payment screenshots before releasing
goods.

## Backend quick start

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements-dev.txt
```

OCR uses Tesseract with a Docker fallback. Run the setup check once per laptop:

```bash
# macOS / Linux
./scripts/setup_ocr.sh

# Windows PowerShell
.\scripts\setup_ocr.ps1
```

See [docs/ocr-setup.md](docs/ocr-setup.md) for per-OS install steps,
configuration and troubleshooting, and
[docs/ocr-preprocessing.md](docs/ocr-preprocessing.md) for the
grayscale/resize/threshold pipeline.

## Tests

```bash
python -m pytest
```

The OCR tests that call Tesseract are opt-in:

```bash
KHUSELA_OCR_INTEGRATION=1 python -m pytest backend/ocr/tests
```
