# Starts the FormEdge API (FastAPI + Uvicorn).
#   .\run-backend.ps1
# Defaults to a local SQLite database and the in-process cache fallback so it
# runs with zero infrastructure; set DATABASE_URL / REDIS_URL to use Postgres+Redis.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location "$root\backend"

if (-not (Test-Path .\.venv\Scripts\python.exe)) {
    Write-Host 'No virtualenv found. Creating one and installing dependencies...' -ForegroundColor Yellow
    python -m venv .venv
    & .\.venv\Scripts\python.exe -m ensurepip --default-pip
    & .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
    if (Test-Path .\requirements-ml.txt) { & .\.venv\Scripts\python.exe -m pip install -r requirements-ml.txt }
}

if (-not $env:DATABASE_URL) { $env:DATABASE_URL = 'sqlite:///./dev.db' }
if (-not $env:WEATHER_ENABLED) { $env:WEATHER_ENABLED = 'false' }
if (-not $env:ML_ARTIFACT_DIR) { $env:ML_ARTIFACT_DIR = '.\ml_artifacts' }

Write-Host ''
Write-Host "  API docs : http://127.0.0.1:8000/api/docs" -ForegroundColor Cyan
Write-Host "  Database : $env:DATABASE_URL" -ForegroundColor DarkGray
Write-Host "  Cache    : $env:REDIS_URL" -ForegroundColor DarkGray
Write-Host ''

& .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
