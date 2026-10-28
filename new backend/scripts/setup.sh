#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python3}"

echo "Khusela / VeriPop backend setup"
echo "  repo:   $ROOT"
echo "  python: $($PYTHON --version)"
echo

if [ ! -d .venv ]; then
  echo "Creating virtual environment..."
  "$PYTHON" -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
  secret="$(python -c 'import secrets; print(secrets.token_hex(32))')"
  python - "$secret" <<'PY'
import sys
from pathlib import Path
secret = sys.argv[1]
text = Path(".env").read_text(encoding="utf-8")
text = text.replace("replace-with-a-long-random-secret-of-32-bytes-minimum", secret)
text = text.replace("replace_with_a_long_random_secret", secret)
Path(".env").write_text(text, encoding="utf-8")
PY
  echo "Wrote .env and generated AUTH/JWT secret."
else
  echo ".env already exists; leaving it unchanged."
fi

mkdir -p data
python scripts/init_db.py
python scripts/seed_sellers.py

echo
echo "Setup complete. Start the API with:"
echo "  source .venv/bin/activate"
echo "  uvicorn app.main:app --reload --port 8000"
echo "Docs: http://127.0.0.1:8000/docs"
