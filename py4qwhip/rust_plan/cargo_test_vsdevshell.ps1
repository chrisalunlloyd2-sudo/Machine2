# Runs the pq crate test suite inside the VS 2026 Insiders dev environment.
# Why: Git Bash's coreutils link.exe shadows MSVC link.exe, and PowerShell spawned
# from Git Bash inherits that PATH (or, if stripped, loses all MSVC paths).
# The VS dev shell is the only environment on this box that resolves LIB correctly
# (NETFXSDK + SDK\ScopeCppSDK\vc15\{SDK\lib,VC\lib}; there is NO Windows Kits\10 SDK).
# Usage:  powershell -NoProfile -ExecutionPolicy Bypass -File cargo_test_vsdevshell.ps1
Set-Location C:/Viper/projects/py4qwhip/rust/pq
# strip Git-bash dirs so coreutils link.exe cannot shadow the MSVC linker
$gitdirs = ($env:Path -split ';') | Where-Object { $_ -like '*\Git\usr\bin' -or $_ -like '*\Git\mingw64\bin' }
$env:Path = ((($env:Path -split ';') | Where-Object { $gitdirs -notcontains $_ }) -join ';')
& "C:\Program Files\Microsoft Visual Studio\18\Insiders\Common7\Tools\Launch-VsDevShell.ps1" -VsInstallationPath "C:\Program Files\Microsoft Visual Studio\18\Insiders" -Arch amd64 -HostArch amd64 | Out-Null
$env:Path = "$env:USERPROFILE\.cargo\bin;" + $env:Path
cargo test 2>&1 | Select-Object -Last 60