#!/usr/bin/env bash
# Creates the Khusela TASK-21..27 GitHub issues.
# Prerequisites: GitHub CLI authenticated (gh auth login) and run from the repo root.
# Issue bodies are read from docs/TASK-*.md so they stay in sync with the docs.
set -euo pipefail

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
REPO="AndiswaNdzimande/Khusela"
MILESTONE="MVP"
# Resolve the docs directory relative to this script, not the caller's cwd
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCS_DIR="$SCRIPT_DIR/files"

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
gh label create "enhancement"    --color "a2eeef" --description "New feature or request"        --repo "$REPO" --force
gh label create "backend"        --color "1d76db" --description "API and server-side work"       --repo "$REPO" --force
gh label create "database"       --color "5319e7" --description "Schema, models, queries"        --repo "$REPO" --force
gh label create "security"       --color "d93f0b" --description "Security-related"               --repo "$REPO" --force
gh label create "privacy"        --color "fbca04" --description "Data protection and retention"  --repo "$REPO" --force
gh label create "infrastructure" --color "bfd4f2" --description "Docker, deployment, tooling"    --repo "$REPO" --force

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
# Helper: strip YAML front-matter from a markdown file and create the issue.
# Usage: create_issue_from_doc <title> <labels_csv> <doc_file>
# ---------------------------------------------------------------------------
create_issue_from_doc() {
  local title="$1"
  local labels="$2"
  local doc_file="$3"

  # Strip lines between the first and second '---' (YAML front-matter)
  local body
  body="$(awk '/^---/{found++; next} found>=2' "$doc_file")"

  local tmpfile
  tmpfile="$(mktemp)"
  printf '%s' "$body" > "$tmpfile"

  gh issue create \
    --repo "$REPO" \
    --title "$title" \
    --label "$labels" \
    --milestone "$MILESTONE" \
    --body-file "$tmpfile"

  rm -f "$tmpfile"
}

# ---------------------------------------------------------------------------
# TASK-21
# ---------------------------------------------------------------------------
echo "Creating TASK-21..."
create_issue_from_doc \
  "TASK-21: FastAPI skeleton with POST /check returning a stub verdict" \
  "enhancement,backend" \
  "$DOCS_DIR/TASK-21-fastapi-skeleton-with-post-check.md"

# ---------------------------------------------------------------------------
# TASK-22
# ---------------------------------------------------------------------------
echo "Creating TASK-22..."
create_issue_from_doc \
  "TASK-22: SQLAlchemy models and SQLite: sellers, expected_sales, checks, fingerprints" \
  "enhancement,backend,database" \
  "$DOCS_DIR/TASK-22-sqlalchemy-models-and-sqlite-sellers.md"

# ---------------------------------------------------------------------------
# TASK-23
# ---------------------------------------------------------------------------
echo "Creating TASK-23..."
create_issue_from_doc \
  "TASK-23: Simple seller auth (register with business name, token login)" \
  "enhancement,backend,security" \
  "$DOCS_DIR/TASK-23-simple-seller-auth-register-with.md"

# ---------------------------------------------------------------------------
# TASK-24
# ---------------------------------------------------------------------------
echo "Creating TASK-24..."
create_issue_from_doc \
  "TASK-24: Upload safety gate: MIME validation, 5 MB cap, parse check" \
  "enhancement,backend,security" \
  "$DOCS_DIR/TASK-24-upload-safety-gate-mime-validation.md"

# ---------------------------------------------------------------------------
# TASK-25
# ---------------------------------------------------------------------------
echo "Creating TASK-25..."
create_issue_from_doc \
  "TASK-25: Store fingerprints and query near-duplicates from OTHER sellers" \
  "enhancement,backend,database" \
  "$DOCS_DIR/TASK-25-store-fingerprints-and-query-near.md"

# ---------------------------------------------------------------------------
# TASK-26
# ---------------------------------------------------------------------------
echo "Creating TASK-26..."
create_issue_from_doc \
  "TASK-26: 24-hour raw-image deletion scheduled job" \
  "enhancement,backend,privacy" \
  "$DOCS_DIR/TASK-26-24-hour-raw-image-deletion.md"

# ---------------------------------------------------------------------------
# TASK-27
# ---------------------------------------------------------------------------
echo "Creating TASK-27..."
create_issue_from_doc \
  "TASK-27: Sandboxed PDF parsing in Docker" \
  "enhancement,security,infrastructure" \
  "$DOCS_DIR/TASK-27-sandboxed-pdf-parsing-in-docker.md"

echo ""
echo "Done. Issues TASK-21 through TASK-27 created on $REPO."
