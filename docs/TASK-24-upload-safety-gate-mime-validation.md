---
title: "TASK-24: Upload safety gate: MIME validation, 5 MB cap, parse check"
labels: ["enhancement", "backend", "security"]
milestone: MVP
---
## Summary
Validate every upload before it is processed. Reject anything that is too large, not an allowed type, or cannot be parsed.

## Requirements
- [x] Maximum size 5 MB enforced while reading the stream; over the limit returns `413`
- [x] Allowed types: JPEG, PNG (PDF accepted at gate; full parse deferred to #27 sandbox)
- [x] Detect the real type from file content (magic bytes via `python-magic`), not the `Content-Type` header or filename; disallowed type returns `415`
- [x] Parse check: images opened and verified with `Pillow`; corrupt or truncated files return `422`
- [x] PDF header check (`%PDF` magic bytes) before passing to the sandbox
- [x] Client filename ignored; file stored under a generated UUID
- [x] Gate runs before fingerprinting or storage — nothing downstream sees an invalid file

## Acceptance criteria
- [x] Tests: valid JPEG, PNG, PDF pass (`tests/test_task24_safety.py`)
- [x] Tests: 5 MB + 1 byte returns `413`
- [x] Tests: `.exe` renamed to `.jpg` returns `415` (magic bytes reveal real type)
- [x] Tests: truncated image returns `415` or `422`
- [x] Tests: empty file returns `422`

## Implementation notes
- Module: `backend/app/api/safety.py`
- `validate_upload(file: UploadFile)` returns `(raw_bytes, mime_type)` or raises `HTTPException`
- `python-magic` requires `libmagic` system library:
  - Linux/macOS: `sudo apt install libmagic1` / `brew install libmagic`
  - Windows: `pip install python-magic-bin`
- `safe_filename()` helper returns a UUID-based name, discarding whatever the client sent

## Security notes
Treat all uploads as untrusted input. Magic-byte detection prevents disguised executables.

## Dependencies
Depends on #21 and #23. PDF full parse uses #27.
