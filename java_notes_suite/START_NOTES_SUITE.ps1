$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$suite = Join-Path $root "java_notes_suite"
$src = Join-Path $suite "src"
$out = Join-Path $suite "out"

if (-not (Get-Command javac -ErrorAction SilentlyContinue)) {
    Write-Host "JAVA_NOTES_SUITE_DEFERRED: javac is not on PATH. Install/enable JDK before running."
    exit 2
}
if (-not (Get-Command java -ErrorAction SilentlyContinue)) {
    Write-Host "JAVA_NOTES_SUITE_DEFERRED: java is not on PATH. Install/enable JDK before running."
    exit 2
}

New-Item -ItemType Directory -Force -Path $out | Out-Null
javac -encoding UTF-8 -d $out (Join-Path $src "com\viper\notes\ViperNotesServer.java")
Push-Location (Split-Path -Parent $root)
try {
    java -Dviper.notes.port=8091 -cp $out com.viper.notes.ViperNotesServer
}
finally {
    Pop-Location
}
