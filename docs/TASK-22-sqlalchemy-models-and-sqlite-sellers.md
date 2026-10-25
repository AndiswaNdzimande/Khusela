---
title: "TASK-22: SQLAlchemy models and SQLite: sellers, expected_sales, checks, fingerprints"
labels: ["enhancement", "backend", "database"]
milestone: MVP
---
## Summary
Add the persistence layer using SQLAlchemy and SQLite, with the four core tables.

## Requirements
- [ ] `app/db.py` with engine, `SessionLocal`, `Base`, and a `get_db` FastAPI dependency
- [ ] `Seller`: `id`, `business_name` (unique), `password_hash`, `created_at`
- [ ] `ExpectedSale`: `id`, `seller_id` (FK), `amount`, `reference`, `expected_at`, `created_at`
- [ ] `Check`: `id`, `seller_id` (FK), `verdict`, `reasons` (JSON), `created_at`
- [ ] `Fingerprint`: `id`, `seller_id` (FK), `check_id` (FK), `hash`, `created_at`, indexed on `hash`
- [ ] Tables created on startup (or via Alembic migration)
- [ ] Foreign keys enabled for SQLite (`PRAGMA foreign_keys=ON`)

## Acceptance criteria
- [ ] Running the app creates the SQLite file with all four tables
- [ ] A test inserts and reads one row per model
- [ ] Deleting a seller does not leave orphaned rows (cascade or documented behaviour)

## Notes
Do not store raw uploaded files in the database. Only fingerprints and verdict metadata (see #26).

## Dependencies
Depends on #21.
