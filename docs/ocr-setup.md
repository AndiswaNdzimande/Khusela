# OCR setup (Tesseract + Docker fallback)

Khusela reads payment screenshots with [Tesseract](https://tesseract-ocr.github.io/)
through `pytesseract`. Every team laptop needs at least one working backend:

| Backend | When it is used | Requirements |
| --- | --- | --- |
| `local` | First choice, fastest | Tesseract binary + `pytesseract` |
| `docker` | Fallback when local Tesseract is missing or broken | Docker Desktop + the `khusela-ocr` image |

The Python wrapper picks a backend automatically, so the rest of the app always
calls the same functions:

```python
from ocr import run_ocr

result = run_ocr("screenshot.png")   # or bytes / file object / PIL.Image
print(result.text)
print(result.confidence)             # 0.0 - 1.0, ready for the rule engine
print(result.backend)                # "local" or "docker"
```

## Quick start

From the repository root:

```bash
# macOS / Linux
./scripts/setup_ocr.sh

# Windows PowerShell
.\scripts\setup_ocr.ps1

# check what will be used
python backend/ocr/tesseract_engine.py --check
```

Expected output when ready:

```text
Khusela OCR check
  Python:            3.12.3
  pytesseract:       installed
  Local Tesseract:   5.3.0
  Docker:            available
  Docker image:      khusela-ocr:latest (built)
  Selected backend:  local

OK: OCR is ready.
```

Then run a real OCR test:

```bash
python backend/ocr/tesseract_engine.py --image tests/fixtures/your-screenshot.png
```

## Option 1: local Tesseract (recommended)

Install the Tesseract binary for your OS, then install the Python packages.

| OS | Command |
| --- | --- |
| macOS (Homebrew) | `brew install tesseract` |
| Ubuntu / Debian / WSL | `sudo apt-get update && sudo apt-get install tesseract-ocr` |
| Windows (winget) | `winget install UB-Mannheim.TesseractOCR` |
| Windows (Chocolatey) | `choco install tesseract` |

After installing on Windows, **close and reopen your terminal** so the updated
`PATH` is loaded.

Install the Python dependencies (inside your virtualenv):

```bash
python -m pip install -r backend/requirements-dev.txt
```

Verify:

```bash
tesseract --version
python -c "import pytesseract; print(pytesseract.get_tesseract_version())"
```

If Tesseract is installed somewhere unusual, point to the binary explicitly:

```bash
# macOS example
export TESSERACT_CMD="/opt/homebrew/bin/tesseract"
```

## Option 2: Docker fallback

Use this when you cannot install Tesseract locally (for example a locked-down
laptop). Docker Desktop must be installed and running.

```bash
docker build -t khusela-ocr:latest -f backend/ocr/Dockerfile backend/ocr
```

The setup scripts build this image for you. The engine builds it lazily the
first time it needs the fallback, unless auto-build is disabled.

Test the image directly:

```bash
cat screenshot.png | docker run --rm -i khusela-ocr:latest stdin stdout -l eng --psm 6
```

The engine pipes images through stdin instead of mounting folders, so the same
command works on macOS, Linux and Windows. The image ships with English
(`eng`) and orientation data only; add `tesseract-ocr-<lang>` packages to
`backend/ocr/Dockerfile` if you need another language.

Force the Docker backend for a run:

```bash
python backend/ocr/tesseract_engine.py --image screenshot.png --backend docker
```

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `KHUSELA_OCR_BACKEND` | `auto` | `auto`, `local` or `docker` |
| `KHUSELA_OCR_DOCKER_IMAGE` | `khusela-ocr:latest` | Docker image name |
| `KHUSELA_OCR_AUTOBUILD` | `1` | Set to `0` to forbid automatic image builds |
| `KHUSELA_OCR_LANG` | `eng` | Tesseract language code |
| `KHUSELA_OCR_PSM` | `6` | Tesseract page segmentation mode |
| `KHUSELA_OCR_TIMEOUT` | `120` | Docker OCR timeout in seconds |
| `TESSERACT_CMD` | unset | Explicit path to the local Tesseract binary |

`auto` tries local first and falls back to Docker if the local install is
missing or fails. Setting `local` or `docker` forces that backend and fails
loudly if it is unavailable.

## Tests

The unit tests do not need Tesseract or Docker:

```bash
python -m pytest backend/ocr/tests
```

To exercise a real backend (local or Docker):

```bash
KHUSELA_OCR_INTEGRATION=1 python -m pytest backend/ocr/tests
```

## Troubleshooting

**`tesseract: command not found`**
The binary is not on `PATH`. Reinstall with the command for your OS, reopen the
terminal, or set `TESSERACT_CMD`.

**Windows: pytesseract cannot find Tesseract**
The UB Mannheim installer usually adds `C:\Program Files\Tesseract-OCR` to
`PATH`. If not, set it for the session:

```powershell
$env:TESSERACT_CMD = "C:\Program Files\Tesseract-OCR\tesseract.exe"
```

**`Cannot connect to the Docker daemon`**
Start Docker Desktop (or `sudo systemctl start docker`) and re-run the check.

**Docker build fails behind a company proxy**
Configure the proxy in Docker Desktop, or install Tesseract locally instead.
Once a teammate has built the image, `docker save` / `docker load` can move it
to another laptop without a rebuild.

**OCR returns empty text or low confidence**
Make sure the screenshot is sharp and contains the payment details. The rule
engine treats confidence below `0.5` as unreadable; image preprocessing is
handled separately. Try `--psm 6` (default) for screenshots and `--psm 3` for
full-page documents.
