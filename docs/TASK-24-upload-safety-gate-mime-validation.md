---
title: "TASK-24: Upload safety gate: MIME validation, 5 MB cap, parse check"
labels: ["enhancement", "backend", "security"]
milestone: MVP
---
## Summary
Validate every upload before it is processed. Reject anything that is too large, not an allowed type, or cannot be parsed.

## Requirements
- [ ] Maximum size 5 MB, enforced while reading the stream; over the limit returns `413`
- [ ] Allowed types: JPEG, PNG, PDF
- [ ] Detect the real type from file content (magic bytes), not just the `Content-Type` header or file extension; disallowed type returns `415`
- [ ] Parse check: images must open and verify with Pillow; PDFs must parse (via the sandbox from #27)
- [ ] Corrupt or unparseable files return `422` with a clear message
- [ ] Sanitise or ignore the client filename; store under a generated UUID
- [ ] Gate runs before any fingerprinting or storage

## Acceptance criteria
- [ ] Tests: valid JPEG, PNG, PDF pass
- [ ] Tests: 5 MB + 1 byte file, `.exe` renamed to `.jpg`, truncated image, and empty file are all rejected with the right status code

## Security notes
Treat all uploads as untrusted input.

## Dependencies
Depends on #21 and #23. PDF parse check uses #27.
