<#
.SYNOPSIS
    Starts the full dev stack: Docker infra (Postgres + Redis), frontend, backend, and ml-agent.
    Kills any existing processes on their ports before starting.

.DESCRIPTION
    Infrastructure (Docker):
      - PostgreSQL  → 5432
      - Redis       → 6379

    Services (local):
      - Frontend  (Next.js)   → 3000
      - Backend   (NestJS)    → 3001
      - ML Agent  (FastAPI)   → 8000

    Run from the repo root:  .\start-dev.ps1
    Stop everything:         .\start-dev.ps1 -Stop
    Skip Docker:             .\start-dev.ps1 -NoDocker
#>

param(
    [switch]$Stop,      # Only kill running services — don't start new ones
    [switch]$NoDocker   # Skip Docker infra (Postgres/Redis) startup
)

$ROOT = $PSScriptRoot

# ── Service definitions ──────────────────────────────────────────────────────
$services = @(
    @{
        Name    = "Frontend"
        Port    = 3000
        Dir     = "$ROOT\frontend"
        Cmd     = "npm run dev"
        Process = "node"
    },
    @{
        Name    = "Backend"
        Port    = 3001
        Dir     = "$ROOT\backend"
        Cmd     = "npm run start:dev"
        Process = "node"
    },
    @{
        Name    = "ML Agent"
        Port    = 8000
        Dir     = "$ROOT\ml-agent"
        Cmd     = "& '.\venv\Scripts\Activate.ps1'; uvicorn api:app --host 0.0.0.0 --port 8000 --reload"
        Process = "python"
    }
)

# ── Helper: kill processes on a given port ───────────────────────────────────
function Stop-ServiceOnPort {
    param(
        [string]$ServiceName,
        [int]$Port,
        [string]$ProcessName
    )

    Write-Host "`n[$ServiceName] Checking port $Port..." -ForegroundColor Cyan

    # 1) Kill by port — works regardless of process name
    $pids = netstat -ano |
        Select-String "LISTENING" |
        Select-String ":$Port\s" |
        ForEach-Object {
            if ($_ -match '\s+(\d+)\s*$') { $Matches[1] }
        } |
        Sort-Object -Unique

    if ($pids) {
        foreach ($pid in $pids) {
            try {
                $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
                if ($proc) {
                    Write-Host "  Killing PID $pid ($($proc.ProcessName)) on port $Port" -ForegroundColor Yellow
                    Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
                }
            } catch {
                Write-Host "  PID $pid already exited" -ForegroundColor DarkGray
            }
        }
    } else {
        Write-Host "  No process found on port $Port" -ForegroundColor Green
    }

    # 2) Also kill any stray child processes by name + command pattern
    #    (handles orphaned watchers that released the port but are still running)
    if ($ProcessName -eq "node") {
        Get-Process -Name "node" -ErrorAction SilentlyContinue |
            Where-Object {
                try {
                    $cmdline = (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)" -ErrorAction SilentlyContinue).CommandLine
                    $cmdline -and $cmdline -match [regex]::Escape($ServiceName.ToLower().Replace(" ", "-"))
                } catch { $false }
            } |
            ForEach-Object {
                Write-Host "  Killing stray node PID $($_.Id)" -ForegroundColor Yellow
                Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
            }
    }
}

# ── Kill existing services ───────────────────────────────────────────────────
Write-Host "========================================" -ForegroundColor Magenta
Write-Host "  Stopping existing dev services...     " -ForegroundColor Magenta
Write-Host "========================================" -ForegroundColor Magenta

foreach ($svc in $services) {
    Stop-ServiceOnPort -ServiceName $svc.Name -Port $svc.Port -ProcessName $svc.Process
}

if ($Stop) {
    if (-not $NoDocker) {
        Write-Host "`n[Docker] Stopping Postgres & Redis..." -ForegroundColor Cyan
        docker compose -f "$ROOT\docker-compose.yml" down 2>$null
    }
    Write-Host "`nAll services stopped." -ForegroundColor Green
    exit 0
}

# ── Start Docker infrastructure ──────────────────────────────────────────────
if (-not $NoDocker) {
    Write-Host "`n========================================" -ForegroundColor Magenta
    Write-Host "  Starting Docker infra (Postgres+Redis)" -ForegroundColor Magenta
    Write-Host "========================================" -ForegroundColor Magenta

    # Check Docker is running
    $dockerOk = docker info 2>$null
    if (-not $dockerOk) {
        Write-Host "`n  Docker is not running!" -ForegroundColor Red
        Write-Host "  Please start Docker Desktop and re-run this script." -ForegroundColor Red
        Write-Host "  Or use: .\start-dev.ps1 -NoDocker  (if DB is already running elsewhere)" -ForegroundColor DarkGray
        exit 1
    }

    # Start only postgres and redis (not the app containers)
    docker compose -f "$ROOT\docker-compose.yml" up -d postgres redis
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  Failed to start Docker services!" -ForegroundColor Red
        exit 1
    }

    # Wait for Postgres to be healthy
    Write-Host "`n[Docker] Waiting for Postgres to be ready..." -ForegroundColor Cyan
    $attempts = 0
    $maxAttempts = 30
    while ($attempts -lt $maxAttempts) {
        $health = docker inspect --format='{{.State.Health.Status}}' (docker compose -f "$ROOT\docker-compose.yml" ps -q postgres) 2>$null
        if ($health -eq "healthy") {
            Write-Host "  Postgres is ready!" -ForegroundColor Green
            break
        }
        $attempts++
        Start-Sleep -Seconds 2
    }
    if ($attempts -ge $maxAttempts) {
        Write-Host "  Postgres did not become healthy in time." -ForegroundColor Red
        exit 1
    }

    Write-Host "  Redis & Postgres are up." -ForegroundColor Green
}

Start-Sleep -Seconds 2   # let ports release from killed processes

# ── Start services in new terminal windows ───────────────────────────────────
Write-Host "`n========================================" -ForegroundColor Magenta
Write-Host "  Starting dev services...              " -ForegroundColor Magenta
Write-Host "========================================" -ForegroundColor Magenta

foreach ($svc in $services) {
    $dir  = $svc.Dir
    $cmd  = $svc.Cmd
    $name = $svc.Name

    if (-not (Test-Path $dir)) {
        Write-Host "`n[$name] Directory not found: $dir — skipping" -ForegroundColor Red
        continue
    }

    Write-Host "`n[$name] Starting on port $($svc.Port)..." -ForegroundColor Cyan
    Start-Process powershell -ArgumentList @(
        "-NoExit",
        "-Command",
        "Set-Location '$dir'; Write-Host '=== $name (port $($svc.Port)) ===' -ForegroundColor Green; $cmd"
    )
}

# ── Summary ──────────────────────────────────────────────────────────────────
Start-Sleep -Seconds 1
Write-Host "`n========================================" -ForegroundColor Green
Write-Host "  All services launched!                " -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Postgres   -> localhost:5432" -ForegroundColor DarkGray
Write-Host "  Redis      -> localhost:6379" -ForegroundColor DarkGray
Write-Host "  Frontend   -> http://localhost:3000" -ForegroundColor White
Write-Host "  Backend    -> http://localhost:3001" -ForegroundColor White
Write-Host "  ML Agent   -> http://localhost:8000" -ForegroundColor White
Write-Host ""
Write-Host "  Stop all:    .\start-dev.ps1 -Stop" -ForegroundColor DarkGray
Write-Host "  No Docker:   .\start-dev.ps1 -NoDocker" -ForegroundColor DarkGray
Write-Host ""
