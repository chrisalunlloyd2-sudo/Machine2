$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $Root
$JarPath = Join-Path $Root "dist\viper-java-sdk-standalone.jar"
$LocalJava = Join-Path $ProjectRoot ".runtime\jdk21\bin\java.exe"

if (!(Test-Path $JarPath)) {
    & (Join-Path $Root "BUILD_STANDALONE_APP.ps1")
}

if (Test-Path $LocalJava) {
    & $LocalJava -jar $JarPath
} elseif (Get-Command java -ErrorAction SilentlyContinue) {
    & java -jar $JarPath
} else {
    Write-Output "JAVA_NOT_FOUND: install or add java to PATH."
    exit 1
}
