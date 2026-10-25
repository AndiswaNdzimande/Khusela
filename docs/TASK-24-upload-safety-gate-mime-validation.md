---
title: "TASK-24: Upload safety gate: MIME validation, 5 MB cap, parse check"
labels: ["enhancement", "backend", "security"]
milestone: MVP
---
## Summary
Validate every upload before it is processed. Reject anything too large, not an allowed type, or unparseable.

## Requirements
- [x] Maximum size 5 MB enforced while reading the stream; over the limit returns `413`
- [x] Allowed types: JPEG, PNG (PDF removed — out of contract per `docs/interfaces.md`)
- [x] Detect real type from magic bytes (not `Content-Type` header or filename); disallowed type returns `415`
- [x] Parse check: images opened and verified with Pillow; corrupt/truncated files return `422`
- [x] Client filename ignored; UUID used internally
- [x] Gate runs before fingerprinting or storage

## Bug fixes (v4 report)
- [x] **Bug 2 (CRITICAL):** `async for chunk in file` raised `TypeError` — `UploadFile` has no `__aiter__` on starlette 0.x. Fixed: replaced with `await file.read(65536)` loop.
- [x] **Bug 4 (HIGH):** Field name was `file`; frontend sends `image`. Fixed: parameter renamed to `image` in `routers/check.py`.

## Acceptance criteria
- [x] Tests: valid JPEG, PNG pass
- [x] Tests: 5 MB + 1 byte → `413`
- [x] Tests: `.exe` renamed to `.jpg` → `415`
- [x] Tests: truncated image → `415` or `422`
- [x] Tests: empty file → `422`
- [x] Tests: PDF → `415` (out of contract)
(`tests/test_task24_safety.py`)

## Implementation notes
- Module: `backend/app/api/safety.py`
- `validate_upload(file: UploadFile)` returns `(raw_bytes, mime_type)` or raises `HTTPException`
- Requires `libmagic` system library (see `backend/docs/ocr-setup.md`)
  - Windows: `pip install python-magic-bin`

## Security notes
Treat all uploads as untrusted input. Magic-byte detection prevents disguised executables.

## Dependencies
Depends on #21 and #23.
