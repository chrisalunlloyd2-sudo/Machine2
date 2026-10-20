# v2 companion: same as cargo_test_vsdevshell.ps1 but appends the ScopeCppSDK
# import-lib dirs to LIB unconditionally (dev shell LIB dropped them 2026-10-18
# -> LNK1181 'kernel32.lib'); both dirs + libs verified on disk that day.
# Runs cargo test with FULL output (no Select-Object truncation) and prints CARGO_EXIT.
# NOTE: no $ErrorActionPreference='Stop' — cargo writes progress to stderr and
# Stop would turn it into a terminating NativeCommandError before cargo runs.
Set-Location C:/Viper/projects/py4qwhip/rust/pq
# strip Git-bash dirs so coreutils link.exe cannot shadow the MSVC linker
$gitdirs = ($env:Path -split ';') | Where-Object { $_ -like '*\Git\usr\bin' -or $_ -like '*\Git\mingw64\bin' }
$env:Path = ((($env:Path -split ';') | Where-Object { $gitdirs -notcontains $_ }) -join ';')
& "C:\Program Files\Microsoft Visual Studio\18\Insiders\Common7\Tools\Launch-VsDevShell.ps1" -VsInstallationPath "C:\Program Files\Microsoft Visual Studio\18\Insiders" -Arch amd64 -HostArch amd64 | Out-Null
$sc = "C:\Program Files\Microsoft Visual Studio\18\Insiders\SDK\ScopeCppSDK\vc15"
$extra = "$sc\SDK\lib;$sc\VC\lib"
if ($env:LIB -notlike "*ScopeCppSDK*") {
    $env:LIB = "$env:LIB;$extra"
}
$env:Path = "$env:USERPROFILE\.cargo\bin;" + $env:Path
Write-Output "LIB=$env:LIB"
& "$env:USERPROFILE\.cargo\bin\cargo.exe" test 2>&1 | Out-String -Width 400
Write-Output "CARGO_EXIT=$LASTEXITCODE"