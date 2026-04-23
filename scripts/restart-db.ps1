# Ensure the local Postgres container is running and healthy.
# Uses docker-compose.yml service `postgres` (container catering-db-local) on host port 5433.
# Safe to re-run; data persists in the `postgres_data` volume.
# Usage: .\scripts\restart-db.ps1
Write-Host "[1/2] starting postgres..." -ForegroundColor Cyan
docker compose up -d postgres
if ($LASTEXITCODE -ne 0) { Write-Host "[ERROR] compose up failed." -ForegroundColor Red; exit 1 }

Write-Host "[2/2] waiting for healthcheck..." -ForegroundColor Cyan
$healthy = $false
for ($i = 1; $i -le 30; $i++) {
  $status = docker inspect --format='{{.State.Health.Status}}' catering-db-local 2>$null
  if ($status -eq "healthy") { $healthy = $true; break }
  Start-Sleep -Seconds 1
}
if (-not $healthy) {
  Write-Host "[ERROR] postgres did not become healthy within 30s." -ForegroundColor Red
  docker logs catering-db-local --tail 20
  exit 1
}

Write-Host "`n[OK] postgres up at localhost:5433 (db=cateringco_dev, user=cateringco)" -ForegroundColor Green
