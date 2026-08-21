$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root ".venv\Scripts\python.exe"
$lanAddress = Get-NetIPConfiguration |
    Where-Object { $_.IPv4DefaultGateway -and $_.IPv4Address } |
    Select-Object -ExpandProperty IPv4Address |
    Where-Object { $_.IPAddress -match '^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)' } |
    Select-Object -First 1 -ExpandProperty IPAddress

Write-Host "启动白板声画工坊..." -ForegroundColor Cyan
Write-Host "本机访问：http://127.0.0.1:13000"
if ($lanAddress) {
    Write-Host "局域网访问：http://${lanAddress}:13000" -ForegroundColor Green
}

Start-Process -FilePath $python -ArgumentList "-m", "uvicorn", "webapp.server:app", "--host", "127.0.0.1", "--port", "18765" -WorkingDirectory $root -WindowStyle Hidden
Start-Process -FilePath "npm.cmd" -ArgumentList "run", "dev" -WorkingDirectory (Join-Path $root "web") -WindowStyle Hidden

Start-Sleep -Seconds 3
Start-Process "http://127.0.0.1:13000"
