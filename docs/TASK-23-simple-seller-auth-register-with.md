---
title: "TASK-23: Simple seller auth (register with business name, token login)"
labels: ["enhancement", "backend", "security"]
milestone: MVP
---
## Summary
Let sellers register with a business name and password, then log in to receive a token used to authenticate API calls.

## Requirements
- [ ] `POST /auth/register`: `business_name` + `password`; returns `201`, or `409` if the name is taken
- [ ] `POST /auth/login`: returns an access token (JWT or opaque bearer token) on valid credentials, `401` otherwise
- [ ] Passwords hashed with bcrypt or argon2 (never stored or logged in plain text)
- [ ] `get_current_seller` dependency reading `Authorization: Bearer <token>`
- [ ] `POST /check` requires authentication
- [ ] Secret key and token expiry read from environment variables, not hard-coded
- [ ] Basic validation: minimum password length, non-empty business name

## Acceptance criteria
- [ ] Register, login, then `POST /check` succeeds with the token
- [ ] `POST /check` without a token or with a bad token returns `401`
- [ ] Tests cover register, duplicate register, wrong password, and protected route

## Out of scope
Password reset, email verification, roles.

## Dependencies
Depends on #21 and #22.
