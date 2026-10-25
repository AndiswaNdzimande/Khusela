#!/usr/bin/env bash
# Creates the Khusela TASK-21..27 GitHub issues.
# Prerequisites: GitHub CLI authenticated (gh auth login) and run from inside the repo.
set -euo pipefail

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
REPO="AndiswaNdzimande/Khusela"
MILESTONE="MVP"
TMPDIR_PREFIX="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_PREFIX"' EXIT

# ---------------------------------------------------------------------------
# Guard: require gh
# ---------------------------------------------------------------------------
if ! command -v gh &>/dev/null; then
  echo "Error: GitHub CLI (gh) is not installed. See https://cli.github.com/" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------
echo "Creating labels..."
gh label create "enhancement"   --color "a2eeef" --description "New feature or request"         --repo "$REPO" --force
gh label create "backend"       --color "1d76db" --description "API and server-side work"        --repo "$REPO" --force
gh label create "database"      --color "5319e7" --description "Schema, models, queries"         --repo "$REPO" --force
gh label create "security"      --color "d93f0b" --description "Security-related"                --repo "$REPO" --force
gh label create "privacy"       --color "fbca04" --description "Data protection and retention"   --repo "$REPO" --force
gh label create "infrastructure" --color "bfd4f2" --description "Docker, deployment, tooling"   --repo "$REPO" --force

# ---------------------------------------------------------------------------
# Milestone (ignore error if it already exists)
# ---------------------------------------------------------------------------
echo "Creating milestone..."
gh api "repos/$REPO/milestones" \
  -f title="$MILESTONE" \
  -f description="First working version of Khusela" \
  >/dev/null 2>&1 \
  || echo "Milestone '$MILESTONE' already exists, continuing."

# ---------------------------------------------------------------------------
# Helper: write body to a temp file and create the issue
# Usage: create_issue <title> <labels_csv> <body_file>
# ---------------------------------------------------------------------------
create_issue() {
  local title="$1"
  local labels="$2"
  local body_file="$3"

  gh issue create \
    --repo "$REPO" \
    --title "$title" \
    --label "$labels" \
    --milestone "$MILESTONE" \
    --body-file "$body_file"
}

# ---------------------------------------------------------------------------
# TASK-21
# ---------------------------------------------------------------------------
echo "Creating TASK-21..."
BODY_21="$TMPDIR_PREFIX/body-21.md"
cat >"$BODY_21" <<'EOF'
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
EOF
create_issue \
  "TASK-21: FastAPI skeleton with POST /check returning a stub verdict" \
  "enhancement,backend" \
  "$BODY_21"

# ---------------------------------------------------------------------------
# TASK-22
# ---------------------------------------------------------------------------
echo "Creating TASK-22..."
BODY_22="$TMPDIR_PREFIX/body-22.md"
cat >"$BODY_22" <<'EOF'
## Summary
Add the persistence layer using SQLAlchemy and SQLite, with the four core tables.

## Requirements
- [ ] `app/db.py` with engine, `SessionLocal`, `Base`, and a `get_db` FastAPI dependency
- [ ] `Seller`: `id`, `business_name` (unique), `password_hash`, `created_at`
- [ ] `ExpectedSale`: `id`, `seller_id` (FK), `amount`, `reference`, `expected_at`, `created_at`
- [ ] `Check`: `id`, `seller_id` (FK), `verdict`, `reasons` (JSON), `created_at`
- [ ] `Fingerprint`: `id`, `seller_id` (FK), `check_id` (FK), `hash`, `created_at`, indexed on `hash`
- [ ] Tables created on startup (or via Alembic migration)
- [ ] Foreign keys enabled for SQLite (`PRAGMA foreign_keys=ON`)

## Acceptance criteria
- [ ] Running the app creates the SQLite file with all four tables
- [ ] A test inserts and reads one row per model
- [ ] Deleting a seller does not leave orphaned rows (cascade or documented behaviour)

## Notes
Do not store raw uploaded files in the database. Only fingerprints and verdict metadata (see #26).

## Dependencies
Depends on #21.
EOF
create_issue \
  "TASK-22: SQLAlchemy models and SQLite: sellers, expected_sales, checks, fingerprints" \
  "enhancement,backend,database" \
  "$BODY_22"

# ---------------------------------------------------------------------------
# TASK-23
# ---------------------------------------------------------------------------
echo "Creating TASK-23..."
BODY_23="$TMPDIR_PREFIX/body-23.md"
cat >"$BODY_23" <<'EOF'
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
EOF
create_issue \
  "TASK-23: Simple seller auth (register with business name, token login)" \
  "enhancement,backend,security" \
  "$BODY_23"

# ---------------------------------------------------------------------------
# TASK-24
# ---------------------------------------------------------------------------
echo "Creating TASK-24..."
BODY_24="$TMPDIR_PREFIX/body-24.md"
cat >"$BODY_24" <<'EOF'
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
EOF
create_issue \
  "TASK-24: Upload safety gate: MIME validation, 5 MB cap, parse check" \
  "enhancement,backend,security" \
  "$BODY_24"

# ---------------------------------------------------------------------------
# TASK-25
# ---------------------------------------------------------------------------
echo "Creating TASK-25..."
BODY_25="$TMPDIR_PREFIX/body-25.md"
cat >"$BODY_25" <<'EOF'
## Summary
Compute a fingerprint for each uploaded proof of payment, store it, and flag near-duplicates that were previously submitted by a **different** seller (a slip reused across sellers is a strong fraud signal).

## Requirements
- [ ] Fingerprint function: perceptual hash for images; normalised text hash for PDFs
- [ ] Store the fingerprint in the `fingerprints` table linked to the seller and check
- [ ] Query near-duplicates using Hamming distance below a configurable threshold
- [ ] Exclude the current seller's own fingerprints (re-uploading your own slip is not a cross-seller match)
- [ ] Return matches in the verdict reasons without exposing the other seller's identity or business name
- [ ] Threshold configurable via environment variable, with a documented default

## Acceptance criteria
- [ ] Same image from seller A then seller B is flagged for B
- [ ] Same image uploaded twice by seller A is not flagged
- [ ] A slightly resized or recompressed copy is still detected
- [ ] An unrelated image is not flagged
- [ ] Tests cover all four cases

## Privacy
Only the hash is stored, never the raw file (see #26).

## Dependencies
Depends on #22 and #24.
EOF
create_issue \
  "TASK-25: Store fingerprints and query near-duplicates from OTHER sellers" \
  "enhancement,backend,database" \
  "$BODY_25"

# ---------------------------------------------------------------------------
# TASK-26
# ---------------------------------------------------------------------------
echo "Creating TASK-26..."
BODY_26="$TMPDIR_PREFIX/body-26.md"
cat >"$BODY_26" <<'EOF'
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
EOF
create_issue \
  "TASK-26: 24-hour raw-image deletion scheduled job" \
  "enhancement,backend,privacy" \
  "$BODY_26"

# ---------------------------------------------------------------------------
# TASK-27
# ---------------------------------------------------------------------------
echo "Creating TASK-27..."
BODY_27="$TMPDIR_PREFIX/body-27.md"
cat >"$BODY_27" <<'EOF'
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
EOF
create_issue \
  "TASK-27: Sandboxed PDF parsing in Docker" \
  "enhancement,security,infrastructure" \
  "$BODY_27"

echo ""
echo "Done. Issues TASK-21 through TASK-27 created on $REPO."
