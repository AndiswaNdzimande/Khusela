---
title: "TASK-26: 24-hour raw-image deletion scheduled job"
labels: ["enhancement", "backend", "privacy"]
milestone: MVP
---
## Summary
Raw uploaded images must not be kept longer than 24 hours. A scheduled job deletes them, leaving only fingerprints and verdict metadata.

## Requirements
- [ ] Record the upload time for every stored raw file
- [ ] Scheduled job (APScheduler or equivalent) runs on a fixed interval, e.g. every 15 minutes
- [ ] Deletes raw files older than 24 hours from disk
- [ ] Fingerprints and check records are kept
- [ ] Retention period (24h) and job interval configurable via environment variables
- [ ] Logs the count of deleted files, never file contents or seller data
- [ ] Safe to run repeatedly (idempotent) and tolerant of already-missing files

## Acceptance criteria
- [ ] Test with a file older than 24h: deleted
- [ ] Test with a file younger than 24h: kept
- [ ] Fingerprint rows remain after deletion
- [ ] Job starts with the app and a failure does not crash the API

## Notes
Supports data-minimisation (POPIA).

## Dependencies
Depends on #22 and #24.
