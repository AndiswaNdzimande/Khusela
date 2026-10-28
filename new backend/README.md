# Khusela / VeriPop backend

FastAPI backend aligned with [Khusela](https://github.com/AndiswaNdzimande/Khusela): seller auth, SQLite persistence (`sellers`, `expected_sales`, `checks`, `fingerprints`), and conservative structural screening. It does **not** claim that funds have cleared.

## Local run (Windows)

```powershell
.\scripts\setup.ps1
.\scripts\run.ps1
```

macOS/Linux:

```sh
chmod +x scripts/setup.sh
./scripts/setup.sh
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

`setup` creates `.venv`, copies `.env`, generates a 32-byte secret, creates `khusela.db`, and seeds the three Khusela fixture sellers (`Thabo Sneakers`, `Naledi Beauty Hub`, `Mama Zodwa Spaza`) with `KHUSELA_SEED_PASSWORD` (default `khusela-dev-password`).

Docs: `http://127.0.0.1:8000/docs`

## API

Khusela frontend (`VITE_API_MODE=live`):

- `GET /health`
- `POST /auth/register`, `POST /auth/login` (also under `/api/auth/...`)
- `POST /check` and `POST /api/check` (Bearer token; multipart `image`, `expected_amount`, `expected_recipient`, `expected_reference`)

Screening prototype:

- `POST /api/v1/auth/register`, `/login`, `/logout`; `GET /api/v1/auth/me`
- `POST /api/v1/documents`; `GET /api/v1/documents/{id}`; `GET /api/v1/verifications/{id}`

`/check` stores a SHA-256 fingerprint and runs the Khusela rule engine. OCR is not required to start the API; until Tesseract is wired, checks return `WAIT` with `ocr_unavailable` unless a cross-seller duplicate fingerprint is found (`STOP`).

## Tests

```sh
python -m pytest -q
```

## Docker

```sh
# Set VERIPOP_AUTH_SECRET (32+ bytes) first.
docker compose up --build
```

The SQLite file and uploads live on the `veripop_documents` volume.
