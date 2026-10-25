---
title: "TASK-22: SQLAlchemy models and SQLite: sellers, expected_sales, checks, fingerprints"
labels: ["enhancement", "backend", "database"]
milestone: MVP
---
## Summary
Add the persistence layer using SQLAlchemy and SQLite, with the four core tables.

## Requirements
- [x] `backend/app/db/database.py` — engine, `SessionLocal`, `Base`, and a `get_db` FastAPI dependency
- [x] `Seller`: `id` (UUID), `business_name` (unique), `password_hash`, `created_at`
- [x] `ExpectedSale`: `id`, `seller_id` (FK → sellers), `amount`, `reference`, `expected_at`, `created_at`
- [x] `Check`: `id`, `seller_id` (FK → sellers), `verdict`, `reasons` (JSON), `raw_file_path`, `raw_file_uploaded_at`, `created_at`
- [x] `Fingerprint`: `id`, `seller_id` (FK → sellers), `check_id` (FK → checks), `hash`, `hash_int`, `created_at`, indexed on `hash`
- [x] Tables created on startup via `Base.metadata.create_all()`
- [x] Foreign keys enabled for SQLite (`PRAGMA foreign_keys=ON`) via SQLAlchemy connect event
- [x] Cascade deletes: deleting a seller removes all child rows

## Acceptance criteria
- [x] Running the app creates the SQLite file (`khusela.db`) with all four tables
- [x] Tests insert and read one row per model (`tests/test_task22_models.py`)
- [x] Deleting a seller removes all orphaned rows (cascade `all, delete-orphan`)

## Implementation notes
- Models: `backend/app/db/models.py`
- Database session: `backend/app/db/database.py`
- `DATABASE_URL` defaults to `sqlite:///./khusela.db`, overridable via env var
- `hash_int` column stores integer representation of the pHash for Hamming distance queries (TASK-25)

## Notes
Raw uploaded files are never stored in the database. Only fingerprints and verdict metadata (see #26).

## Dependencies
Depends on #21.
