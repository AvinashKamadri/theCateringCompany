# Rebuild + recreate the frontend container with the correct build args.
# Usage: .\scripts\restart-frontend.ps1
Write-Host "[1/3] building frontend image..." -ForegroundColor Cyan
docker compose -f docker-compose.yml build `
  --build-arg NEXT_PUBLIC_API_URL=http://localhost:3001 `
  --build-arg NEXT_PUBLIC_ML_API_URL=http://localhost:8000 `
  --build-arg NEXT_PUBLIC_WS_URL=ws://localhost:3001 `
  frontend
if ($LASTEXITCODE -ne 0) { Write-Host "[ERROR] build failed - aborting." -ForegroundColor Red; exit 1 }

Write-Host "[2/3] recreating container..." -ForegroundColor Cyan
docker rm -f catering-frontend-local 2>$null | Out-Null
docker run -d --name catering-frontend-local `
  -p 3000:3000 `
  --network thecateringcompany_catering-network `
  thecateringcompany-frontend:latest | Out-Null

Start-Sleep -Seconds 2
Write-Host "[3/3] logs:" -ForegroundColor Cyan
docker logs catering-frontend-local --tail 10
Write-Host "`n[OK] frontend up at http://localhost:3000" -ForegroundColor Green
