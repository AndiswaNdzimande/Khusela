---
title: "TASK-23: Simple seller auth (register with business name, token login)"
labels: ["enhancement", "backend", "security"]
milestone: MVP
---
## Summary
Sellers register with a business name and password, then log in to receive a JWT bearer token for all API calls.

## Requirements
- [x] `POST /auth/register`: `business_name` + `password`; returns `201` or `409` if name taken
- [x] `POST /auth/login`: returns JWT access token (200) or `401`
- [x] Passwords hashed with bcrypt via `passlib[bcrypt]==1.7.4` + `bcrypt==4.0.1`
- [x] `get_current_seller` dependency reads `Authorization: Bearer <token>`, returns `Seller` row or `401`
- [x] `POST /check` requires authentication
- [x] `JWT_SECRET_KEY` and `JWT_EXPIRE_MINUTES` from env vars only
- [x] Minimum 8-character password, non-empty business name (Pydantic validation)

## Bug fixes (v4 report)
- [x] **Bug 8 (MEDIUM):** `SECRET_KEY = os.environ["JWT_SECRET_KEY"]` raised `KeyError` at import if unset. Fixed: `os.getenv()` with `sys.exit(1)` in `main.py` startup if missing.
- [x] **Bug 9 (LOW):** `passlib 1.7.4` is incompatible with `bcrypt >= 4.1`. Fixed: `bcrypt==4.0.1` pinned in `requirements.txt`.
- [x] **Routes:** `POST /auth/register` and `POST /auth/login` (prefix `/auth`). Frontend calls `/api/auth/*` — Andiswa/Ntoampi to confirm prefix alignment with `backend/main.py`.

## Acceptance criteria
- [x] Register → login → `/check` succeeds with token
- [x] `/check` with no token → `401`
- [x] `/check` with bad token → `401`
- [x] Tests: register, duplicate, short password, wrong password, protected route (`tests/test_task23_auth.py`)

## Implementation notes
- Router: `backend/app/api/auth.py`
- Schemas: `backend/app/schemas/auth.py`
- Algorithm: HS256 JWT via `python-jose`
- `seller_id` always taken from token — never from a client field

## Out of scope
Password reset, email verification, roles.

## Dependencies
Depends on #21 and #22.
