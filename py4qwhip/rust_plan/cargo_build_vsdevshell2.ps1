# v2 build driver: dev shell + ScopeCppSDK LIB append, cargo build --release, full output.
Set-Location C:/Viper/projects/py4qwhip/rust/pq
$gitdirs = ($env:Path -split ';') | Where-Object { $_ -like '*\Git\usr\bin' -or $_ -like '*\Git\mingw64\bin' }
$env:Path = ((($env:Path -split ';') | Where-Object { $gitdirs -notcontains $_ }) -join ';')
& "C:\Program Files\Microsoft Visual Studio\18\Insiders\Common7\Tools\Launch-VsDevShell.ps1" -VsInstallationPath "C:\Program Files\Microsoft Visual Studio\18\Insiders" -Arch amd64 -HostArch amd64 | Out-Null
$sc = "C:\Program Files\Microsoft Visual Studio\18\Insiders\SDK\ScopeCppSDK\vc15"
$extra = "$sc\SDK\lib;$sc\VC\lib"
if ($env:LIB -notlike "*ScopeCppSDK*") {
    $env:LIB = "$env:LIB;$extra"
}
$env:Path = "$env:USERPROFILE\.cargo\bin;" + $env:Path
& "$env:USERPROFILE\.cargo\bin\cargo.exe" build --release 2>&1 | Out-String -Width 400
Write-Output "CARGO_EXIT=$LASTEXITCODE"