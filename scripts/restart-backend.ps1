# Rebuild + recreate the backend container. Reads env from .\backend.env.
# Usage: .\scripts\restart-backend.ps1
$ErrorActionPreference = "Stop"

if (-not (Test-Path ".\backend.env")) {
  Write-Host "[ERROR] .\backend.env not found. See scripts/restart-backend.ps1 header for required keys." -ForegroundColor Red
  exit 1
}

Write-Host "[1/3] building backend image..." -ForegroundColor Cyan
docker compose build backend
if ($LASTEXITCODE -ne 0) { Write-Host "[ERROR] build failed - aborting." -ForegroundColor Red; exit 1 }

Write-Host "[2/3] recreating container..." -ForegroundColor Cyan
docker rm -f catering-backend-local 2>$null | Out-Null
docker run -d --name catering-backend-local `
  -p 3001:3001 `
  --network thecateringcompany_catering-network `
  --env-file .\backend.env `
  thecateringcompany-backend:latest | Out-Null

Start-Sleep -Seconds 6
Write-Host "[3/3] logs:" -ForegroundColor Cyan
docker logs catering-backend-local --tail 30
Write-Host "`n[OK] backend up at http://localhost:3001" -ForegroundColor Green
