---
title: "TASK-21: FastAPI skeleton with POST /check returning a stub verdict"
labels: ["enhancement", "backend"]
milestone: MVP
---
## Summary
Set up the FastAPI project skeleton with a `POST /check` endpoint that returns a hard-coded stub verdict, so every later task has a working API to plug into.

## Requirements
- [ ] Project structure (`app/main.py`, `app/routers/`, `app/schemas/`) and `requirements.txt`
- [ ] `GET /health` returns `{"status": "ok"}`
- [ ] `POST /check` accepts a file upload (`multipart/form-data`) and returns a stub verdict
- [ ] Pydantic response schema, e.g. `{"verdict": "needs_review", "reasons": ["stub"], "check_id": "<uuid>"}`
- [ ] Auto-generated docs available at `/docs`
- [ ] `README.md` section: how to install and run (`uvicorn app.main:app --reload`)

## Acceptance criteria
- [ ] `uvicorn` starts with no errors
- [ ] `POST /check` returns `200` with a schema-valid stub verdict
- [ ] A basic pytest test for `/health` and `/check` passes

## Out of scope
Auth, database, real verification logic (see #22, #23, #25).

## Dependencies
None. This is the foundation for #22-#27.
