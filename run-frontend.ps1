# Starts the FormEdge web dashboard (Next.js dev server).
#   .\run-frontend.ps1
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location "$root\frontend"

if (-not (Test-Path .\node_modules)) {
    Write-Host 'Installing frontend dependencies...' -ForegroundColor Yellow
    npm install --no-audit --no-fund
}

Write-Host ''
Write-Host '  Dashboard : http://localhost:3000' -ForegroundColor Cyan
Write-Host '  API base  : ' -NoNewline -ForegroundColor DarkGray
Write-Host ((Get-Content .\.env.local -ErrorAction SilentlyContinue | Select-String 'NEXT_PUBLIC_API_URL').Line)
Write-Host ''

npm run dev
