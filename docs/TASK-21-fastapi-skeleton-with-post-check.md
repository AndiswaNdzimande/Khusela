---
title: "TASK-21: FastAPI skeleton with POST /check returning a stub verdict"
labels: ["enhancement", "backend"]
milestone: MVP
---
## Summary
FastAPI project skeleton with `GET /health` and `POST /check`, Pydantic response schema matching the verdict contract, JWT auth gate, and auto-docs.

## Requirements
- [x] Project structure: `backend/app/main.py`, `backend/app/routers/`, `backend/app/schemas/`, `requirements.txt`
- [x] `GET /health` returns `{"status": "ok"}`
- [x] `POST /check` accepts `image` (multipart), `expected_amount`, `expected_recipient`, `expected_reference`
- [x] Pydantic response schema matches `contracts/verdict.schema.json` (11 fields)
- [x] Auto-generated docs at `/docs`
- [x] `README.md`: install and run with `uvicorn app.main:app --reload` from `backend/`

## Bug fixes (v4 report)
- [x] **Bug 3 (CRITICAL):** `_run_engine` imported the engine module (not the function), passed wrong kwarg (`duplicate=` vs `dup_result=`), read OCR result as dict (it is an object), only caught `ImportError` so `TypeError` → 500. Fixed: `routers/check.py` now calls `integration.check_payment`, catches all exceptions.
- [x] **Bug 4 (HIGH):** Field name was `file`; frontend sends `image`. Fixed in `routers/check.py`.
- [x] **Bug 7 (MEDIUM):** `/check` wrote raw uploads to `./uploads/raw`, contradicting the "nothing stored" privacy story. Fixed: raw bytes never written to disk.
- [x] **Bug 8 (MEDIUM):** `JWT_SECRET_KEY = os.environ["JWT_SECRET_KEY"]` crashed at import before the app could start. Fixed: `os.getenv()` with a startup validation in `main.py` that logs a clear error and exits with `sys.exit(1)`.
- [x] **Bug 9 (LOW):** `pytest` from repo root failed — two packages both named `tests`. Fixed: `pytest.ini` with `--import-mode=importlib`.

## Acceptance criteria
- [x] `uvicorn` starts with no errors (with `JWT_SECRET_KEY` set)
- [x] `GET /health` returns `{"status": "ok"}`
- [x] `POST /check` returns `200` with schema-valid verdict
- [x] `POST /check` without token returns `401`
- [x] Tests pass: `tests/test_task21_skeleton.py`
- [x] Startup log names each pipeline piece as `REAL` or `STAND-IN`

## Implementation notes
- Entry point: `backend/app/main.py`
- Routers: `backend/app/routers/check.py`
- Schemas: `backend/app/schemas/check.py`, `backend/app/schemas/auth.py`
- `START_SCHEDULER=1` env var required to enable deletion scheduler (off by default)
- CORS restricted via `ALLOWED_ORIGINS` env var

## Dependencies
None. Foundation for #22–#27.
