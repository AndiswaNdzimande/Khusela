# Khusela – Backend

FastAPI backend for proof-of-payment verification.  
Covers TASK-21 through TASK-27.

---

## Requirements

- Python 3.11+
- [libmagic](https://github.com/ahupp/python-magic#installation) (system library for MIME detection)
  - **Linux/macOS:** `sudo apt install libmagic1` or `brew install libmagic`
  - **Windows:** install the DLL via `pip install python-magic-bin`
- Docker Desktop (optional, required only for TASK-27 PDF sandbox)

---

## Install and run

```bash
cd backend

# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set environment variables
cp .env.example .env
# Edit .env – at minimum set JWT_SECRET_KEY

# 4. Start the API (from the backend/ directory)
uvicorn app.main:app --reload
```

Docs are available at http://localhost:8000/docs

---

## Run tests

```bash
cd backend
pytest -v
```

---

## TASK-27: PDF sandbox

Build the Docker image once:

```bash
docker build -t khusela-pdf-sandbox ./pdf_sandbox
```

The API will use it automatically when a PDF is uploaded.  
Set `PDF_SANDBOX_IMAGE` in `.env` if you tag the image differently.

Manual test:

```bash
docker run --rm --network none --read-only \
  --tmpfs /tmp:size=32m \
  --memory 256m --cpus 0.5 \
  --cap-drop ALL --security-opt no-new-privileges \
  -i khusela-pdf-sandbox < /path/to/test.pdf
```

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `JWT_SECRET_KEY` | **required** | Secret for signing JWTs |
| `JWT_EXPIRE_MINUTES` | `60` | Token lifetime |
| `DATABASE_URL` | `sqlite:///./khusela.db` | SQLAlchemy DB URL |
| `RAW_IMAGE_RETENTION_HOURS` | `24` | Hours before raw files are deleted |
| `DELETION_JOB_INTERVAL_MINUTES` | `15` | How often the deletion job runs |
| `RAW_UPLOAD_DIR` | `./uploads/raw` | Where raw files are stored temporarily |
| `PHASH_HAMMING_THRESHOLD` | `10` | Max Hamming distance for near-duplicate match |
| `ALLOWED_ORIGINS` | `http://localhost:5173` | Comma-separated CORS origins |
| `PDF_SANDBOX_IMAGE` | `khusela-pdf-sandbox` | Docker image name for PDF sandbox |
| `PDF_SANDBOX_TIMEOUT_SECONDS` | `10` | Hard timeout for PDF container |
