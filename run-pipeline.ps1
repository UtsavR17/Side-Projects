# Runs the background pipeline stages, or imports human-supplied files.
#   .\run-pipeline.ps1                           # full cycle
#   .\run-pipeline.ps1 train predict             # selected stages
#   .\run-pipeline.ps1 import .\incoming\*.csv   # import CSVs/pages, then refresh
# `scrape`/`weather` need internet access; failures are non-fatal.
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$CliArgs)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location "$root\backend"

if (-not $env:DATABASE_URL) { $env:DATABASE_URL = 'sqlite:///./dev.db' }
if (-not $env:WEATHER_ENABLED) { $env:WEATHER_ENABLED = 'false' }
if (-not $env:ML_ARTIFACT_DIR) { $env:ML_ARTIFACT_DIR = '.\ml_artifacts' }

# `import <files...>` — human-in-the-loop ingestion (CSV or saved HTML pages),
# followed by the stages that make the new data usable.
if ($CliArgs -and $CliArgs[0] -eq 'import') {
    $files = @($CliArgs | Select-Object -Skip 1)
    if ($files.Count -eq 0) {
        Write-Host 'Usage: .\run-pipeline.ps1 import <file.csv|card.html> [more files...]' -ForegroundColor Yellow
        Write-Host 'See docs/data-import.md for the CSV schema.' -ForegroundColor Yellow
        exit 1
    }
    Write-Host "=== import: $($files -join ', ') ===" -ForegroundColor Cyan
    & .\.venv\Scripts\python.exe -m pipeline.import_files @files
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    foreach ($stage in @('features', 'predict', 'explain', 'evaluate', 'warm')) {
        Write-Host "=== $stage ===" -ForegroundColor Cyan
        & .\.venv\Scripts\python.exe -m pipeline.run --stage $stage
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
    exit 0
}

if (-not $CliArgs -or $CliArgs.Count -eq 0) {
    & .\.venv\Scripts\python.exe -m pipeline.run --stage all
} else {
    foreach ($stage in $CliArgs) {
        Write-Host "=== $stage ===" -ForegroundColor Cyan
        & .\.venv\Scripts\python.exe -m pipeline.run --stage $stage
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
}
