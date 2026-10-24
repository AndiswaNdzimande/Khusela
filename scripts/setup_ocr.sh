#!/usr/bin/env bash
# Set up OCR for a Khusela laptop.
#
# Usage: ./scripts/setup_ocr.sh
#
# Prefers a local Tesseract install (fastest) and builds the Docker fallback
# image when Docker is available. Safe to re-run.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

IMAGE="${KHUSELA_OCR_DOCKER_IMAGE:-khusela-ocr:latest}"
PYTHON="${PYTHON:-python3}"

echo "Khusela OCR setup"
echo "  repo:   $ROOT"
echo "  python: $("$PYTHON" --version 2>&1)"
echo

print_install_help() {
  cat <<'EOF'
Install Tesseract locally:
  macOS:          brew install tesseract
  Ubuntu/Debian:  sudo apt-get install tesseract-ocr
  Windows:        winget install UB-Mannheim.TesseractOCR
                  (then reopen your terminal so PATH is refreshed)

Or install Docker Desktop and re-run this script to build the fallback:
  https://www.docker.com/products/docker-desktop/
EOF
}

if ! "$PYTHON" -c "import pytesseract" >/dev/null 2>&1; then
  echo "pytesseract is not installed for $PYTHON."
  echo "Create/activate your virtualenv, then run:"
  echo "  $PYTHON -m pip install -r backend/requirements-dev.txt"
  echo
fi

if command -v tesseract >/dev/null 2>&1; then
  echo "Local Tesseract found: $(tesseract --version 2>&1 | head -n 1)"
else
  echo "Local Tesseract not found on PATH."
fi

if command -v docker >/dev/null 2>&1; then
  if docker info >/dev/null 2>&1; then
    if docker image inspect "$IMAGE" >/dev/null 2>&1; then
      echo "Docker fallback image already built: $IMAGE"
    else
      echo "Building Docker fallback image: $IMAGE"
      docker build -t "$IMAGE" -f backend/ocr/Dockerfile backend/ocr
    fi
  else
    echo "Docker is installed but the daemon is not running. Start Docker Desktop and re-run."
  fi
else
  echo "Docker not found (fallback unavailable)."
fi

echo
if "$PYTHON" -c "import pytesseract" >/dev/null 2>&1; then
  if ! "$PYTHON" backend/ocr/tesseract_engine.py --check; then
    print_install_help
    exit 1
  fi
else
  echo "Skipping OCR check until the Python dependencies are installed:"
  echo "  $PYTHON -m pip install -r backend/requirements-dev.txt"
  print_install_help
  exit 1
fi
