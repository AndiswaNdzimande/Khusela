---
title: "TASK-23: Simple seller auth (register with business name, token login)"
labels: ["enhancement", "backend", "security"]
milestone: MVP
---
## Summary
Let sellers register with a business name and password, then log in to receive a JWT bearer token used to authenticate API calls.

## Requirements
- [x] `POST /auth/register`: `business_name` + `password`; returns `201`, or `409` if the name is taken
- [x] `POST /auth/login`: returns a JWT access token on valid credentials, `401` otherwise
- [x] Passwords hashed with bcrypt via `passlib[bcrypt]` — never stored or logged in plain text
- [x] `get_current_seller` dependency reads `Authorization: Bearer <token>` and resolves the `Seller` row
- [x] `POST /check` requires authentication — returns `401` with no token or a bad/expired token
- [x] `JWT_SECRET_KEY` and `JWT_EXPIRE_MINUTES` read from environment variables, never hard-coded
- [x] Basic validation: minimum 8-character password, non-empty business name (Pydantic `RegisterRequest`)

## Acceptance criteria
- [x] Register → login → `POST /check` succeeds with the token
- [x] `POST /check` without a token returns `401`
- [x] `POST /check` with a bad token returns `401`
- [x] Tests cover register, duplicate register, short password, wrong password, protected route (`tests/test_task23_auth.py`)

## Implementation notes
- Router: `backend/app/api/auth.py`
- Schemas: `backend/app/schemas/auth.py`
- Algorithm: `HS256` JWT via `python-jose`
- `seller_id` is always taken from the validated token — never from a client-supplied field
- `JWT_SECRET_KEY` must be set in `.env`; the app crashes loudly on startup if missing (no silent fallback)

## Out of scope
Password reset, email verification, roles.

## Dependencies
Depends on #21 and #22.
