# Architecture and current implementation

## Current flow

```text
Caller --Bearer token--> FastAPI upload
                         | size + magic-byte checks
                         | generated file id + SHA-256
                         v
                   local data directory
                         |
                         v
           INSUFFICIENT_EVIDENCE response
```

`app/main.py` serves the API. Persistence uses the Khusela SQLite schema in `app/db/` (`sellers`, `expected_sales`, `checks`, `fingerprints`, plus `auth_sessions` and `documents`). The rule engine lives in `engine/evaluate.py`. This still makes no authenticity, settlement, identity or fraud determination. Risk score remains null because there is no calibrated detector. OCR is optional; `/check` stores fingerprints and returns `WAIT` until OCR is wired.

## Intended boundaries for expansion

Separate authentication and tenant authorization, upload/storage, document validation, OCR and classification adapters, POP/identity rules, risk aggregation, review cases, provider adapters and background jobs. Persist each processing stage and its model/rule version. Use private encrypted object storage and short-lived access grants; isolate parsers in restricted workers. Keep payment status distinct from document appearance and identity validation.

## Known gaps

SQLite + SQLAlchemy is in place; there is still no PostgreSQL/Alembic production store, Redis, worker, OCR runtime, PDF rendering, image forensics, bank feed, identity authority, messaging webhook, billing, retention scheduler, monitoring or CI configuration. These must not be represented as operational features until implemented and verified.
