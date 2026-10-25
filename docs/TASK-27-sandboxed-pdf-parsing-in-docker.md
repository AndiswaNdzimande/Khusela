---
title: "TASK-27: Sandboxed PDF parsing in Docker"
labels: ["enhancement", "security", "infrastructure"]
milestone: MVP
---
## Summary
Parse uploaded PDFs inside an isolated Docker container so a malicious PDF cannot compromise the main API.

## Requirements
- [x] `Dockerfile` for a minimal parser image (`python:3.12-slim`, `pdfminer.six` only)
- [x] Container runs as a non-root user (`parser`)
- [x] No network access (`--network none`)
- [x] Read-only root filesystem (`--read-only`) with a small tmpfs (`/tmp:size=32m`) for scratch space
- [x] Resource limits: `--memory 256m`, `--cpus 0.5`, hard timeout (`PDF_SANDBOX_TIMEOUT_SECONDS`, default 10s)
- [x] All Linux capabilities dropped (`--cap-drop ALL`) and `--security-opt no-new-privileges`
- [x] API passes PDF bytes via stdin; receives JSON (`{"text": "..."}` or `{"error": "..."}`) via stdout
- [x] Timeout, crash, or non-zero exit treated as "unparseable" — fails closed, never raises
- [x] `backend/README.md` section on building and running the sandbox

## Acceptance criteria
- [x] A valid PDF returns `{"text": "..."}` (exit 0)
- [x] A corrupt PDF returns `{"error": "..."}` (exit 1, clean error)
- [x] A PDF that hangs the parser is killed at the timeout (`subprocess.TimeoutExpired` caught)
- [x] Container has no network and cannot write outside `/tmp` scratch space

## Implementation notes
- Dockerfile: `backend/pdf_sandbox/Dockerfile`
- Parser script: `backend/pdf_sandbox/parse_pdf.py` (reads stdin, writes JSON to stdout)
- API bridge: `backend/app/api/pdf_parser.py` — `parse_pdf_sandboxed(raw_bytes)` → dict
- Build the image once: `docker build -t khusela-pdf-sandbox ./pdf_sandbox`
- Image name configurable via `PDF_SANDBOX_IMAGE` env var

## Build and run

```bash
# Build
docker build -t khusela-pdf-sandbox backend/pdf_sandbox

# Test manually
docker run --rm --network none --read-only \
  --tmpfs /tmp:size=32m \
  --memory 256m --cpus 0.5 \
  --cap-drop ALL --security-opt no-new-privileges \
  -i khusela-pdf-sandbox < /path/to/test.pdf
```

## Out of scope
Image parsing (handled by Pillow in #24).

## Dependencies
Related to #24.
