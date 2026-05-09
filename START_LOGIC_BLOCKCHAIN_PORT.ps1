$Root = "C:\Users\viper\VIPER_JAVA_RISC"
$Python = "C:\Users\viper\AppData\Local\Programs\Python\Python311\python.exe"
$Server = Join-Path $Root "tools\logic_blockchain_shipper.py"
$PidFile = Join-Path $Root "logic_blockchain_shipper.pid"

$existing = Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -like "*logic_blockchain_shipper.py*" -and $_.ProcessId -ne $PID } |
    Select-Object -First 1

if ($existing) {
    $existing.ProcessId | Out-File -LiteralPath $PidFile -Force
    Write-Host "LOGIC_BLOCKCHAIN_SHIPPER_ALREADY_RUNNING PID=$($existing.ProcessId) PORT=18081"
    exit 0
}

$proc = Start-Process -FilePath $Python `
    -ArgumentList "`"$Server`"" `
    -WorkingDirectory $Root `
    -WindowStyle Hidden `
    -PassThru

$proc.Id | Out-File -LiteralPath $PidFile -Force
Write-Host "LOGIC_BLOCKCHAIN_SHIPPER_STARTED PID=$($proc.Id) PORT=18081"
