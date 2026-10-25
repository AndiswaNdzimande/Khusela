---
title: "TASK-21: FastAPI skeleton with POST /check returning a stub verdict"
labels: ["enhancement", "backend"]
milestone: MVP
---
## Summary
Set up the FastAPI project skeleton with a `POST /check` endpoint that returns a hard-coded stub verdict, so every later task has a working API to plug into.

## Requirements
- [x] Project structure (`backend/app/main.py`, `backend/app/routers/`, `backend/app/schemas/`) and `requirements.txt`
- [x] `GET /health` returns `{"status": "ok"}`
- [x] `POST /check` accepts a file upload (`multipart/form-data`) and returns a stub verdict
- [x] Pydantic response schema matches `contracts/verdict.schema.json` (11 fields: `check_id`, `verdict`, `reasons`, `explanation`, `confidence`, `is_duplicate`, `extracted`, `expected`, `duplicate`, `raw_ocr_text`, `bank_reminder`)
- [x] Auto-generated docs available at `/docs`
- [x] `README.md` section: how to install and run (`uvicorn app.main:app --reload` from `backend/`)

## Acceptance criteria
- [x] `uvicorn` starts with no errors
- [x] `POST /check` returns `200` with a schema-valid verdict
- [x] `GET /health` returns `{"status": "ok"}`
- [x] A basic pytest test for `/health` and `/check` passes (`tests/test_task21_skeleton.py`)

## Implementation notes
- Entry point: `backend/app/main.py`
- Routers: `backend/app/routers/check.py`
- Schemas: `backend/app/schemas/check.py`, `backend/app/schemas/auth.py`
- Response shape follows `backend/` layout and `contracts/verdict.schema.json` — not the old `app/` stub layout
- CORS origins restricted via `ALLOWED_ORIGINS` env var (default: `http://localhost:5173`)
- Startup creates all SQLite tables; scheduler starts automatically

## Out of scope
Real OCR, real verification logic (wired via engine bridge in `routers/check.py`).

## Dependencies
None. This is the foundation for #22-#27.
