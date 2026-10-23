# Start medical QA stack: pgvector + backend + frontend
# Usage: right-click -> Run with PowerShell, or: powershell -ExecutionPolicy Bypass -File .\启动.ps1
$ErrorActionPreference = "SilentlyContinue"
$root = $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$logs = Join-Path $root "logs"
if (-not (Test-Path $logs)) { New-Item -ItemType Directory -Path $logs | Out-Null }

# 1. Docker Desktop
docker info --format "{{.ServerVersion}}" | Out-Null
if ($LASTEXITCODE -ne 0) {
    $dockerExe = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if (Test-Path $dockerExe) {
        Start-Process $dockerExe
        for ($i = 0; $i -lt 40; $i++) {
            Start-Sleep -Seconds 4
            docker info --format "{{.ServerVersion}}" | Out-Null
            if ($LASTEXITCODE -eq 0) { break }
        }
    }
}

# 2. PostgreSQL + pgvector
$exists = docker ps -a --filter "name=^medical-pg-local$" --format "{{.Names}}"
if (-not $exists) {
    docker run -d --name medical-pg-local -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=medicalqa -e POSTGRES_DB=medical_qa -p 5433:5432 pgvector/pgvector:pg16 | Out-Null
} else {
    $running = docker ps --filter "name=^medical-pg-local$" --format "{{.Names}}"
    if (-not $running) { docker start medical-pg-local | Out-Null }
}
for ($i = 0; $i -lt 30; $i++) {
    docker exec medical-pg-local pg_isready -U postgres 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { break }
    Start-Sleep -Seconds 2
}

# 3. Backend (uvicorn, port 8000)
$p8000 = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if (-not $p8000) {
    Start-Process -FilePath "E:\Programs\anaconda\python.exe" `
        -ArgumentList "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000" `
        -WorkingDirectory $backend `
        -RedirectStandardOutput (Join-Path $logs "backend.out.log") `
        -RedirectStandardError (Join-Path $logs "backend.err.log") | Out-Null
}

# 4. Frontend (Vite, port 5173)
$p5173 = Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue
if (-not $p5173) {
    $npm = (Get-Command npm.cmd).Source
    Start-Process -FilePath $npm `
        -ArgumentList "run", "dev", "--", "--host", "0.0.0.0" `
        -WorkingDirectory $frontend `
        -RedirectStandardOutput (Join-Path $logs "frontend.out.log") `
        -RedirectStandardError (Join-Path $logs "frontend.err.log") | Out-Null
}

# 5. Wait for health
for ($i = 0; $i -lt 30; $i++) {
    $c = curl.exe -s -o NUL -w "%{http_code}" http://localhost:8000/api/health 2>$null
    if ($c -eq "200") { break }
    Start-Sleep -Seconds 2
}
for ($i = 0; $i -lt 30; $i++) {
    $c = curl.exe -s -o NUL -w "%{http_code}" http://localhost:5173/ 2>$null
    if ($c -eq "200") { break }
    Start-Sleep -Seconds 2
}

Write-Host ""
Write-Host "Frontend: http://localhost:5173"
Write-Host "Backend:  http://localhost:8000/docs"
Write-Host "Health:   http://localhost:8000/api/health"
Write-Host "Logs:     $logs"
