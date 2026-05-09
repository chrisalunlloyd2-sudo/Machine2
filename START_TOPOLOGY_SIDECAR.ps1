$Root = "C:\Users\viper\VIPER_JAVA_RISC"
$Loop = Join-Path $Root "tools\topology_loop.ps1"
$PidFile = Join-Path $Root "topology_sidecar.pid"

$existing = Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -like "*topology_loop.ps1*" -and $_.ProcessId -ne $PID } |
    Select-Object -First 1

if ($existing) {
    $existing.ProcessId | Out-File -LiteralPath $PidFile -Force
    Write-Host "TOPOLOGY_SIDECAR_ALREADY_RUNNING PID=$($existing.ProcessId)"
    exit 0
}

$proc = Start-Process -FilePath "powershell.exe" `
    -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$Loop`"" `
    -WorkingDirectory $Root `
    -WindowStyle Hidden `
    -PassThru

$proc.Id | Out-File -LiteralPath $PidFile -Force
Write-Host "TOPOLOGY_SIDECAR_STARTED PID=$($proc.Id)"
