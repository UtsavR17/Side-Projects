# Seeds SYNTHETIC demo data (clearly-labelled, not real MTC form) so the
# dashboard, predictions and leaderboard have content offline.
#   .\seed-demo.ps1
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location "$root\backend"

if (-not $env:DATABASE_URL) { $env:DATABASE_URL = 'sqlite:///./dev.db' }
if (-not $env:ML_ARTIFACT_DIR) { $env:ML_ARTIFACT_DIR = '.\ml_artifacts' }

& .\.venv\Scripts\python.exe seed_demo.py
