---
title: "TASK-27: Sandboxed PDF parsing in Docker"
labels: ["enhancement", "security", "infrastructure"]
milestone: MVP
---
## Summary
Parse uploaded PDFs inside an isolated Docker container so a malicious PDF cannot compromise the main API.

## Requirements
- [ ] `Dockerfile` for a minimal parser image (slim Python base, one PDF library)
- [ ] Container runs as a non-root user
- [ ] No network access (`--network none`)
- [ ] Read-only root filesystem (`--read-only`) with a small tmpfs for scratch space
- [ ] Resource limits: memory, CPU, and a hard timeout (e.g. 10 seconds)
- [ ] All Linux capabilities dropped (`--cap-drop ALL`) and `no-new-privileges`
- [ ] API passes the file in and receives extracted text or a structured error out
- [ ] Timeout, crash, or non-zero exit is treated as "unparseable" (fails closed)
- [ ] `README.md` section on building and running the sandbox

## Acceptance criteria
- [ ] A valid PDF returns extracted text
- [ ] A corrupt PDF returns a clean error
- [ ] A PDF that hangs the parser is killed at the timeout
- [ ] Container has no network and cannot write outside scratch space (verified by test or documented check)

## Out of scope
Image parsing (handled by Pillow in #24).

## Dependencies
Related to #24.
