# Set up OCR for a Khusela laptop (Windows PowerShell).
#
# Usage: .\scripts\setup_ocr.ps1
#
# Prefers a local Tesseract install (fastest) and builds the Docker fallback
# image when Docker is available. Safe to re-run.

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Image = if ($env:KHUSELA_OCR_DOCKER_IMAGE) { $env:KHUSELA_OCR_DOCKER_IMAGE } else { "khusela-ocr:latest" }
$Python = if ($env:PYTHON) { $env:PYTHON } else { "python" }

Write-Host "Khusela OCR setup"
Write-Host "  repo:   $Root"
Write-Host "  python: $(& $Python --version 2>&1)"
Write-Host ""

function Show-InstallHelp {
    Write-Host @"
Install Tesseract locally:
  winget install UB-Mannheim.TesseractOCR
  (then reopen your terminal so PATH is refreshed)

Or install Docker Desktop and re-run this script to build the fallback:
  https://www.docker.com/products/docker-desktop/
"@
}

$pytesseractOk = $false
& $Python -c "import pytesseract" 2>$null
if ($LASTEXITCODE -eq 0) { $pytesseractOk = $true } else {
    Write-Host "pytesseract is not installed for $Python."
    Write-Host "Create/activate your virtualenv, then run:"
    Write-Host "  $Python -m pip install -r backend/requirements-dev.txt"
    Write-Host ""
}

if (Get-Command tesseract -ErrorAction SilentlyContinue) {
    $version = (& tesseract --version 2>&1 | Select-Object -First 1)
    Write-Host "Local Tesseract found: $version"
} else {
    Write-Host "Local Tesseract not found on PATH."
}

if (Get-Command docker -ErrorAction SilentlyContinue) {
    docker info *> $null
    if ($LASTEXITCODE -eq 0) {
        docker image inspect $Image *> $null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Docker fallback image already built: $Image"
        } else {
            Write-Host "Building Docker fallback image: $Image"
            docker build -t $Image -f backend/ocr/Dockerfile backend/ocr
            if ($LASTEXITCODE -ne 0) { throw "Docker image build failed." }
        }
    } else {
        Write-Host "Docker is installed but the daemon is not running. Start Docker Desktop and re-run."
    }
} else {
    Write-Host "Docker not found (fallback unavailable)."
}

Write-Host ""
if ($pytesseractOk) {
    & $Python backend/ocr/tesseract_engine.py --check
    if ($LASTEXITCODE -ne 0) {
        Show-InstallHelp
        exit 1
    }
} else {
    Write-Host "Skipping OCR check until the Python dependencies are installed:"
    Write-Host "  $Python -m pip install -r backend/requirements-dev.txt"
    Show-InstallHelp
    exit 1
}
