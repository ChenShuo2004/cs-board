param(
    [int]$IntervalSeconds = 600,
    [int]$BackendPort = 18765
)

$ErrorActionPreference = "Stop"
$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$python = (Resolve-Path -LiteralPath (Join-Path $workspace ".venv\Scripts\python.exe")).Path
$stateDirectory = Join-Path $workspace ".webapp"
$logPath = Join-Path $stateDirectory "restart-monitor.log"
New-Item -ItemType Directory -Path $stateDirectory -Force | Out-Null

function Write-MonitorLog([string]$message) {
    Add-Content -LiteralPath $logPath -Encoding UTF8 -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $message"
}

function Get-ActiveJobCount {
    try {
        $response = Invoke-RestMethod "http://127.0.0.1:$BackendPort/api/jobs?limit=100" -TimeoutSec 10
        return @($response.items | Where-Object { $_.status -in @("queued", "running") }).Count
    }
    catch {
        return $null
    }
}

Write-MonitorLog "Safe restart monitor started. Check interval: $IntervalSeconds seconds."
while ($true) {
    Start-Sleep -Seconds $IntervalSeconds
    $activeCount = Get-ActiveJobCount
    if ($null -ne $activeCount -and $activeCount -gt 0) {
        Write-MonitorLog "$activeCount active jobs remain. Waiting for the next check."
        continue
    }

    Start-Sleep -Seconds 5
    $confirmedCount = Get-ActiveJobCount
    if ($null -ne $confirmedCount -and $confirmedCount -gt 0) {
        Write-MonitorLog "Second check found $confirmedCount active jobs. Restart postponed."
        continue
    }

    $listenPattern = "^\s*TCP\s+127\.0\.0\.1:$BackendPort\s+0\.0\.0\.0:0\s+LISTENING"
    $listener = netstat -ano | Select-String $listenPattern | Select-Object -First 1
    if ($listener) {
        $backendPid = [int](($listener.Line -split "\s+")[-1])
        Stop-Process -Id $backendPid -Force
        Start-Sleep -Milliseconds 800
    }

    Start-Process -FilePath $python -ArgumentList "-m", "uvicorn", "webapp.server:app", "--host", "127.0.0.1", "--port", "$BackendPort" -WorkingDirectory $workspace -WindowStyle Hidden
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        Start-Sleep -Seconds 1
        try {
            $health = Invoke-RestMethod "http://127.0.0.1:$BackendPort/api/health" -TimeoutSec 5
            if ($health.status -eq "ok") {
                Write-MonitorLog "Backend restarted safely. Voice concurrency: $($health.queues.voice.concurrency). Model concurrency: $($health.queues.model.concurrency)."
                exit 0
            }
        }
        catch {}
    }
    Write-MonitorLog "Backend did not respond after restart. Manual inspection is required."
    exit 1
}
