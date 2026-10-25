---
title: "TASK-26: 24-hour raw-image deletion scheduled job"
labels: ["enhancement", "backend", "privacy"]
milestone: MVP
---
## Summary
A scheduled job deletes raw files older than 24 hours, leaving only fingerprints and verdict metadata.

## Requirements
- [x] `Check.raw_file_uploaded_at` records upload time; `raw_file_path` cleared after deletion
- [x] APScheduler `BackgroundScheduler` runs on a configurable interval (default 15 min)
- [x] Deletes raw files older than `RAW_IMAGE_RETENTION_HOURS` (default 24)
- [x] Fingerprint and Check rows kept after deletion
- [x] Logs count of deleted files only — never file contents or seller data
- [x] Idempotent: already-missing files silently skipped; exceptions caught without crashing API

## Bug fixes (v4 report)
- [x] **Bug 7 (MEDIUM):** `/check` was writing every upload to disk for 24h, contradicting the "nothing stored" privacy story. Fixed: `/check` no longer stores raw files. The scheduler remains available but is **off by default** (`START_SCHEDULER=0`). Set `START_SCHEDULER=1` to enable it only if raw storage is intentionally used.

## Acceptance criteria
- [x] Test: file older than 24h → deleted
- [x] Test: file younger than 24h → kept
- [x] Test: Fingerprint rows survive deletion
- [x] Scheduler starts when `START_SCHEDULER=1` and does not crash the API on failure
(`tests/test_task26_scheduler.py`)

## Implementation notes
- Module: `backend/app/scheduler.py`
- Scheduler is started in `main.py` only when `START_SCHEDULER=1`
- `RAW_IMAGE_RETENTION_HOURS` and `DELETION_JOB_INTERVAL_MINUTES` configurable via `.env`

## Notes
Supports data-minimisation under POPIA.

## Dependencies
Depends on #22 and #24.
