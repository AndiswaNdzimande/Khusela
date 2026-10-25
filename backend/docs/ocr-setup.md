# OCR Setup Guide

Khusela uses Tesseract 5 for OCR. It must be installed **and on your PATH** before running the API or the test suite, otherwise the engine returns `ocr_unavailable`.

---

## Linux (Ubuntu / Debian)

```bash
sudo apt update
sudo apt install tesseract-ocr tesseract-ocr-eng
tesseract --version   # should print 5.x
```

---

## macOS

```bash
brew install tesseract
tesseract --version
```

---

## Windows

1. Download the installer from the [UB-Mannheim releases page](https://github.com/UB-Mannheim/tesseract/wiki).
2. Run the installer and tick **"Add Tesseract to PATH"** during setup.
3. Open a **new** PowerShell window and verify:

```powershell
tesseract --version
```

If you forgot to tick the PATH option, add it manually:

```powershell
# Default install path — adjust if yours differs
$env:PATH += ";C:\Program Files\Tesseract-OCR"
# To make it permanent, add the same line to your PowerShell profile:
# notepad $PROFILE
```

---

## Docker fallback

If Tesseract cannot be installed on a machine, the existing Docker fallback script handles it:

```bash
bash backend/scripts/setup_ocr.sh
```

> **Note:** `setup_ocr.ps1` / `setup_ocr.sh` do **not** add Tesseract to PATH automatically.  
> You must do that manually using the steps above, or the API will return `ocr_unavailable` even after the script runs.

---

## Verify OCR works end to end

```bash
cd backend
python - <<'EOF'
import pytesseract
from PIL import Image
import io, urllib.request

# Download a simple test image
url = "https://tesseract.projectnaptha.com/img/eng_bw.png"
data = urllib.request.urlopen(url).read()
img = Image.open(io.BytesIO(data))
print(pytesseract.image_to_string(img))
EOF
```

You should see readable text. If you see an empty string or an error, Tesseract is not on PATH.

---

## Demo laptop checklist (run before the hackathon demo)

- [ ] `tesseract --version` prints 5.x in a fresh terminal
- [ ] `python -c "import pytesseract; print(pytesseract.get_tesseract_version())"` succeeds
- [ ] Docker Desktop is running (required for TASK-27 PDF sandbox)
- [ ] `docker run --rm hello-world` succeeds
- [ ] The `khusela-pdf-sandbox` image is built: `docker build -t khusela-pdf-sandbox backend/pdf_sandbox`
- [ ] Wi-Fi off test: start the API and upload a receipt — OCR must still work (Tesseract is local, no internet needed)
