# Rebuild + recreate frontend, ml-agent, and backend.
# Usage: .\scripts\restart-all.ps1
$ErrorActionPreference = "Stop"

& "$PSScriptRoot\restart-ml-agent.ps1"
& "$PSScriptRoot\restart-backend.ps1"
& "$PSScriptRoot\restart-frontend.ps1"

Write-Host "`n=== stack ===" -ForegroundColor Yellow
docker ps --filter "name=catering" --format "table {{.Names}}`t{{.Status}}`t{{.Ports}}"
