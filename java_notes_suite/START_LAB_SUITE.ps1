$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $Root
$Src = Join-Path $Root "src\com\viper\notes\ViperLabSuiteServer.java"
$Out = Join-Path $Root "out"
$LocalJdk = Join-Path $ProjectRoot ".runtime\jdk21"
$LocalJavac = Join-Path $LocalJdk "bin\javac.exe"
$LocalJava = Join-Path $LocalJdk "bin\java.exe"

if ((Test-Path $LocalJavac) -and (Test-Path $LocalJava)) {
    $Javac = $LocalJavac
    $Java = $LocalJava
} elseif ((Get-Command javac -ErrorAction SilentlyContinue) -and (Get-Command java -ErrorAction SilentlyContinue)) {
    $Javac = "javac"
    $Java = "java"
} else {
    Write-Output "JDK_NOT_FOUND: install or add javac to PATH before starting the Java lab suite."
    exit 1
}

New-Item -ItemType Directory -Force -Path $Out | Out-Null
& $Javac -encoding UTF-8 -d $Out $Src
& $Java -cp $Out com.viper.notes.ViperLabSuiteServer
