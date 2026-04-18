# Rebuild + recreate the ml-agent container. Reads env from .\ml-agent.env.
# Usage: .\scripts\restart-ml-agent.ps1
$ErrorActionPreference = "Stop"

if (-not (Test-Path ".\ml-agent.env")) {
  Write-Host "[ERROR] .\ml-agent.env not found. Create it with DATABASE_URL, OPENAI_API_KEY, CORS_ORIGIN." -ForegroundColor Red
  exit 1
}

Write-Host "[1/3] building ml-agent image..." -ForegroundColor Cyan
docker compose build ml-agent
if ($LASTEXITCODE -ne 0) { Write-Host "[ERROR] build failed - aborting." -ForegroundColor Red; exit 1 }

Write-Host "[2/3] recreating container..." -ForegroundColor Cyan
docker rm -f catering-ml-agent-local 2>$null | Out-Null
docker run -d --name catering-ml-agent-local `
  -p 8000:8000 `
  --network thecateringcompany_catering-network `
  --env-file .\ml-agent.env `
  thecateringcompany-ml-agent:latest | Out-Null

Start-Sleep -Seconds 3
Write-Host "[3/3] logs:" -ForegroundColor Cyan
docker logs catering-ml-agent-local --tail 15
Write-Host "`n[OK] ml-agent up at http://localhost:8000" -ForegroundColor Green
