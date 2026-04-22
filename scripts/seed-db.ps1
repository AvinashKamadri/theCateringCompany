# Seed roles, permissions, users, and menu into the local DB.
# Assumes postgres (catering-db-local) is running and backend has applied migrations.
# Safe to re-run: role seed uses ON CONFLICT, menu uses upsert. seed:users will ADD another 100.
# Usage: .\scripts\seed-db.ps1
$ErrorActionPreference = "Stop"

Write-Host "[1/3] seeding roles + permissions..." -ForegroundColor Cyan
Get-Content "$PSScriptRoot\..\sql\seed_roles_permissions.sql" -Raw | docker exec -i catering-db-local psql -U cateringco -d cateringco_dev | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Host "[ERROR] roles seed failed." -ForegroundColor Red; exit 1 }

Push-Location "$PSScriptRoot\..\backend"
try {
  Write-Host "[2/3] seeding users (20 staff + 80 hosts, pw=TestPass123)..." -ForegroundColor Cyan
  npm run seed:users
  if ($LASTEXITCODE -ne 0) { Write-Host "[ERROR] seed:users failed." -ForegroundColor Red; exit 1 }

  Write-Host "[3/3] seeding menu..." -ForegroundColor Cyan
  npm run seed:menu
  if ($LASTEXITCODE -ne 0) { Write-Host "[ERROR] seed:menu failed." -ForegroundColor Red; exit 1 }
} finally {
  Pop-Location
}

Write-Host "`n[OK] DB seeded." -ForegroundColor Green
