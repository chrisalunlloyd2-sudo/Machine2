$ErrorActionPreference = "Stop"
$cloudflared = Join-Path $env:USERPROFILE "cloudflared.exe"
if (-not (Test-Path $cloudflared)) {
    Write-Host "NOTES_TUNNEL_DEFERRED: cloudflared.exe not found at $cloudflared"
    exit 2
}

$log = Join-Path $PSScriptRoot "notes_cloudflared.log"
$urlFile = Join-Path $PSScriptRoot "NOTES_CLOUDFLARE_URL.txt"
Start-Process -FilePath $cloudflared -ArgumentList "tunnel --url http://127.0.0.1:8091" -RedirectStandardOutput $log -RedirectStandardError $log -WindowStyle Hidden
Start-Sleep -Seconds 6
$content = Get-Content -Path $log -ErrorAction SilentlyContinue | Out-String
$match = [regex]::Match($content, "https://[-a-zA-Z0-9]+\.trycloudflare\.com")
if ($match.Success) {
    Set-Content -Path $urlFile -Value $match.Value
    Write-Host "NOTES_TUNNEL_URL=$($match.Value)"
} else {
    Write-Host "NOTES_TUNNEL_STARTED_BUT_URL_NOT_FOUND_YET. Check $log"
}
