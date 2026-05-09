param(
    [int]$Port = 11435,
    [int]$WaitSeconds = 45
)

$ErrorActionPreference = "Stop"
$Root = "C:\Users\viper\VIPER_JAVA_RISC"
$Engine = "C:\Users\viper\house_inference_engine.py"
$Stdout = Join-Path $Root "house_inference_stdout.log"
$Stderr = Join-Path $Root "house_inference_stderr.log"

function Test-House {
    try {
        $res = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 3
        return ($res.StatusCode -eq 200)
    } catch {
        return $false
    }
}

if (Test-House) {
    [pscustomobject]@{ status = "already_healthy"; port = $Port } | ConvertTo-Json -Compress
    exit 0
}

$python = (Get-Command py -ErrorAction SilentlyContinue)
if ($null -eq $python) {
    throw "Python launcher 'py' was not found."
}
if (-not (Test-Path -LiteralPath $Engine)) {
    throw "House engine file not found: $Engine"
}

Start-Process -FilePath $python.Source `
    -ArgumentList @("-3", $Engine) `
    -WorkingDirectory $Root `
    -RedirectStandardOutput $Stdout `
    -RedirectStandardError $Stderr `
    -WindowStyle Hidden

$deadline = (Get-Date).AddSeconds($WaitSeconds)
do {
    Start-Sleep -Seconds 2
    if (Test-House) {
        [pscustomobject]@{ status = "started"; port = $Port; engine = $Engine } | ConvertTo-Json -Compress
        exit 0
    }
} while ((Get-Date) -lt $deadline)

[pscustomobject]@{ status = "start_timeout"; port = $Port; engine = $Engine } | ConvertTo-Json -Compress
exit 1
