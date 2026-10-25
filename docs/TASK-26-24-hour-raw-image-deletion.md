---
title: "TASK-26: 24-hour raw-image deletion scheduled job"
labels: ["enhancement", "backend", "privacy"]
milestone: MVP
---
## Summary
Raw uploaded images must not be kept longer than 24 hours. A scheduled job deletes them, leaving only fingerprints and verdict metadata.

## Requirements
- [x] `Check.raw_file_uploaded_at` records the upload time for every stored raw file
- [x] `Check.raw_file_path` stores the path; cleared to `NULL` after deletion
- [x] Scheduled job (APScheduler `BackgroundScheduler`) runs on a fixed interval (default every 15 minutes)
- [x] Deletes raw files older than 24 hours from disk
- [x] Fingerprint and Check rows are kept after deletion
- [x] Retention period (`RAW_IMAGE_RETENTION_HOURS`) and job interval (`DELETION_JOB_INTERVAL_MINUTES`) configurable via environment variables
- [x] Logs the count of deleted files — never file contents or seller data
- [x] Idempotent: already-missing files are silently skipped; exceptions are caught and logged without crashing the API

## Acceptance criteria
- [x] Test: file older than 24h → deleted (`tests/test_task26_scheduler.py`)
- [x] Test: file younger than 24h → kept
- [x] Test: Fingerprint rows remain after deletion
- [x] Job starts with the app (`app/main.py` startup event) and a failure does not crash the API

## Implementation notes
- Module: `backend/app/scheduler.py`
- `delete_expired_raw_files()` — core deletion function, called by APScheduler
- `start_scheduler()` — creates and starts the scheduler; returns it so `main.py` can shut it down cleanly
- Raw files are stored in `RAW_UPLOAD_DIR` (default `./uploads/raw`)
- Scheduler uses UTC timezone

## Notes
Supports data-minimisation under POPIA.

## Dependencies
Depends on #22 and #24.
