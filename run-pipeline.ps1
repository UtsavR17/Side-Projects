# Runs the background pipeline stages (scrape -> features -> train -> predict ->
# explain -> evaluate -> cache warm).
#   .\run-pipeline.ps1                # full cycle
#   .\run-pipeline.ps1 train predict  # only selected stages
# Real scraping needs internet access to mtcjockeyclub.com; the `scrape` and
# `weather` stages are skipped automatically when they fail — nothing crashes.
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Stages)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location "$root\backend"

if (-not $env:DATABASE_URL) { $env:DATABASE_URL = 'sqlite:///./dev.db' }
if (-not $env:WEATHER_ENABLED) { $env:WEATHER_ENABLED = 'false' }
if (-not $env:ML_ARTIFACT_DIR) { $env:ML_ARTIFACT_DIR = '.\ml_artifacts' }

if (-not $Stages -or $Stages.Count -eq 0) {
    & .\.venv\Scripts\python.exe -m pipeline.run --stage all
} else {
    foreach ($stage in $Stages) {
        Write-Host "=== $stage ===" -ForegroundColor Cyan
        & .\.venv\Scripts\python.exe -m pipeline.run --stage $stage
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
}
