# Bring up the whole local stack in dependency order:
#   db -> backend + ml-agent -> frontend
# Usage: .\scripts\restart-all.ps1

& "$PSScriptRoot\restart-db.ps1"
& "$PSScriptRoot\restart-backend.ps1"
& "$PSScriptRoot\restart-ml-agent.ps1"
& "$PSScriptRoot\restart-frontend.ps1"

Write-Host "`n=== stack ===" -ForegroundColor Yellow
docker ps --filter "name=catering" --format "table {{.Names}}`t{{.Status}}`t{{.Ports}}"

Write-Host "`nApp: http://localhost:3000   |   Backend: http://localhost:3001   |   ML: http://localhost:8000   |   DB: localhost:5433" -ForegroundColor Cyan
Write-Host "Tip: run .\scripts\seed-db.ps1 once to populate roles/users/menu." -ForegroundColor DarkGray
