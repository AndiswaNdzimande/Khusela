# Prepare this backend so it can run locally on Windows.
# Usage: .\scripts\setup.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = if ($env:PYTHON) { $env:PYTHON } else { "python" }

Write-Host "Khusela backend setup"
Write-Host "  repo:   $Root"
Write-Host "  python: $(& $Python --version)"
Write-Host ""

# ── Virtual environment ──────────────────────────────────────────────────────
if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..."
    & $Python -m venv .venv
}

$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    throw "Virtual environment is missing .venv\Scripts\python.exe"
}

# ── Dependencies ─────────────────────────────────────────────────────────────
Write-Host "Installing Python dependencies..."
& $VenvPython -m pip install --upgrade pip --quiet
& $VenvPython -m pip install -r requirements.txt

# ── .env file ────────────────────────────────────────────────────────────────
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    $secret = & $VenvPython -c "import secrets; print(secrets.token_hex(32))"
    $envContent = Get-Content ".env" -Raw
    $envContent = $envContent -replace "replace-with-a-long-random-secret-of-32-bytes-minimum", $secret
    $envContent = $envContent -replace "replace_with_a_long_random_secret", $secret
    Set-Content -Path ".env" -Value $envContent -NoNewline
    Write-Host "Wrote .env and generated AUTH/JWT secret."
} else {
    Write-Host ".env already exists; leaving it unchanged."
}

# ── Data directory ───────────────────────────────────────────────────────────
New-Item -ItemType Directory -Force -Path "data" | Out-Null

# ── Database ─────────────────────────────────────────────────────────────────
Write-Host "Creating SQLite tables..."
& $VenvPython scripts\init_db.py

Write-Host "Seeding development sellers..."
& $VenvPython scripts\seed_sellers.py

# ── OCR backend check ────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Checking OCR backend availability..."
& $VenvPython -m ocr.tesseract_engine --check
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "  NOTE: No OCR backend found. The /check endpoint will still work"
    Write-Host "  but will always return WAIT (ocr_unavailable) until Tesseract is"
    Write-Host "  installed or the Docker fallback image is built."
    Write-Host ""
    Write-Host "  To install Tesseract on Windows:"
    Write-Host "    winget install UB-Mannheim.TesseractOCR"
    Write-Host "  Then reopen your terminal and run setup.ps1 again."
    Write-Host ""
    Write-Host "  Or build the Docker fallback (requires Docker Desktop):"
    Write-Host "    docker build -t khusela-ocr:latest ocr/"
}

# ── Done ─────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Setup complete. Start the API with:"
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host "  uvicorn app.main:app --reload --port 8000"
Write-Host ""
Write-Host "  or:  .\scripts\run.ps1"
Write-Host ""
Write-Host "Docs: http://127.0.0.1:8000/docs"
