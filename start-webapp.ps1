$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root ".venv\Scripts\python.exe"
$webRoot = Join-Path $root "web"
$stateDir = Join-Path $root ".webapp"
$launcherErrorLog = Join-Path $stateDir "launcher-error.log"
$backendOutputLog = Join-Path $stateDir "backend-output.log"
$backendErrorLog = Join-Path $stateDir "backend-error.log"
$frontendOutputLog = Join-Path $stateDir "frontend-output.log"
$frontendErrorLog = Join-Path $stateDir "frontend-error.log"

New-Item -ItemType Directory -Force -Path $stateDir | Out-Null
Remove-Item -LiteralPath $launcherErrorLog -Force -ErrorAction SilentlyContinue

function Test-BackendReady {
    try {
        Invoke-RestMethod "http://127.0.0.1:18765/api/health" -TimeoutSec 2 | Out-Null
        return $true
    } catch {
        return $false
    }
}

function Test-FrontendReady {
    try {
        Invoke-WebRequest "http://127.0.0.1:13000" -UseBasicParsing -TimeoutSec 2 | Out-Null
        return $true
    } catch {
        return $false
    }
}

try {
    $lanAddress = Get-NetIPConfiguration -ErrorAction SilentlyContinue |
        Where-Object { $_.IPv4DefaultGateway -and $_.IPv4Address } |
        Select-Object -ExpandProperty IPv4Address |
        Where-Object { $_.IPAddress -match '^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)' } |
        Select-Object -First 1 -ExpandProperty IPAddress

    Write-Host "Starting the whiteboard video workshop..." -ForegroundColor Cyan
    Write-Host "Local URL: http://127.0.0.1:13000"
    if ($lanAddress) {
        Write-Host "LAN URL: http://${lanAddress}:13000" -ForegroundColor Green
    }

    if (Test-BackendReady) {
        Write-Host "Backend is already running." -ForegroundColor DarkGray
    } else {
        Remove-Item -LiteralPath $backendOutputLog, $backendErrorLog -Force -ErrorAction SilentlyContinue
        Start-Process -FilePath $python -ArgumentList "-m", "uvicorn", "webapp.server:app", "--host", "127.0.0.1", "--port", "18765" -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput $backendOutputLog -RedirectStandardError $backendErrorLog
    }

    if (Test-FrontendReady) {
        Write-Host "Frontend is already running." -ForegroundColor DarkGray
    } else {
        Remove-Item -LiteralPath $frontendOutputLog, $frontendErrorLog -Force -ErrorAction SilentlyContinue
        Start-Process -FilePath "npm.cmd" -ArgumentList "run", "dev" -WorkingDirectory $webRoot -WindowStyle Hidden -RedirectStandardOutput $frontendOutputLog -RedirectStandardError $frontendErrorLog
    }

    $backendReady = $false
    $frontendReady = $false
    for ($attempt = 0; $attempt -lt 90; $attempt++) {
        $backendReady = Test-BackendReady
        $frontendReady = Test-FrontendReady
        if ($backendReady -and $frontendReady) {
            break
        }
        Start-Sleep -Seconds 1
    }

    if (-not $backendReady) {
        throw "Backend failed to start. See .webapp\backend-error.log."
    }
    if (-not $frontendReady) {
        throw "Frontend failed to start. See .webapp\frontend-error.log."
    }

    Write-Host "Ready. Opening the browser..." -ForegroundColor Green
    Start-Process "http://127.0.0.1:13000"
} catch {
    $message = "{0}`r`n{1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $_.Exception.Message
    Set-Content -LiteralPath $launcherErrorLog -Value $message -Encoding UTF8
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
