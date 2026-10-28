# Start the API after setup. Usage: .\scripts\run.ps1
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    throw "Run .\scripts\setup.ps1 first."
}
& $VenvPython -m uvicorn app.main:app --reload --port 8000
