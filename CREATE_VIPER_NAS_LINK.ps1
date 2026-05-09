param(
    [string]$NasRoot = $env:VIPER_NAS_ROOT
)

$ErrorActionPreference = "Stop"
$Desktop = [Environment]::GetFolderPath("Desktop")
$LocalStaging = Join-Path $Desktop "VIPER_NAS_SYNC_STAGING"
$ShortcutPath = Join-Path $Desktop "VIPER_NAS_SYNC.url"

if ([string]::IsNullOrWhiteSpace($NasRoot)) {
    New-Item -ItemType Directory -Force -Path $LocalStaging | Out-Null
    $Readme = Join-Path $LocalStaging "README_VIPER_NAS_SYNC.txt"
    Set-Content -LiteralPath $Readme -Encoding UTF8 -Value @"
VIPER NAS sync staging folder.

Set VIPER_NAS_ROOT to the real NAS/share path on each machine, then rerun:
powershell -ExecutionPolicy Bypass -File C:\Users\viper\VIPER_JAVA_RISC\CREATE_VIPER_NAS_LINK.ps1

Until VIPER_NAS_ROOT is set, agents should use this local staging folder only.
"@
    [pscustomobject]@{
        status = "local_staging_created"
        path = $LocalStaging
        reason = "VIPER_NAS_ROOT not set"
    } | ConvertTo-Json -Compress
    exit 0
}

if (-not (Test-Path -LiteralPath $NasRoot)) {
    throw "VIPER_NAS_ROOT does not exist or is not reachable: $NasRoot"
}

$uri = (Resolve-Path -LiteralPath $NasRoot).Path
Set-Content -LiteralPath $ShortcutPath -Encoding ASCII -Value "[InternetShortcut]`nURL=file:///$($uri -replace '\\','/')`n"

[pscustomobject]@{
    status = "nas_link_created"
    shortcut = $ShortcutPath
    target = $uri
} | ConvertTo-Json -Compress
