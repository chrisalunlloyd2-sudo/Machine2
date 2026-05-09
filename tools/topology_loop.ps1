$ErrorActionPreference = "Continue"

$Root = "C:\Users\viper\VIPER_JAVA_RISC"
$Python = "C:\Users\viper\AppData\Local\Programs\Python\Python311\python.exe"
$Sidecar = Join-Path $Root "tools\topology_sidecar.py"
$Log = Join-Path $Root "topology_sidecar_loop.log"

Set-Location $Root

while ($true) {
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -LiteralPath $Log -Value "[$stamp] TOPOLOGY_LOOP_BEGIN"

    try {
        & $Python $Sidecar suggest-cycle --label "KAROO_20MIN" 2>&1 | Add-Content -LiteralPath $Log
        & $Python $Sidecar karoo-approval-cycle --label "KAROO_20MIN_APPROVAL" 2>&1 | Add-Content -LiteralPath $Log
        & $Python $Sidecar monitor-dislikes 2>&1 | Add-Content -LiteralPath $Log
        & $Python $Sidecar queue-logic-block --limit 32 2>&1 | Add-Content -LiteralPath $Log
        & $Python $Sidecar prune --keep 18 2>&1 | Add-Content -LiteralPath $Log
        $status = (Invoke-WebRequest -Uri "http://127.0.0.1:8080/" -UseBasicParsing -TimeoutSec 5).StatusCode
        Add-Content -LiteralPath $Log -Value "[$stamp] LIVE_WEB_STATUS=$status"
    } catch {
        Add-Content -LiteralPath $Log -Value "[$stamp] TOPOLOGY_LOOP_ERROR=$($_.Exception.Message)"
    }

    Add-Content -LiteralPath $Log -Value "[$stamp] TOPOLOGY_LOOP_SLEEP_1200"
    Start-Sleep -Seconds 1200
}
