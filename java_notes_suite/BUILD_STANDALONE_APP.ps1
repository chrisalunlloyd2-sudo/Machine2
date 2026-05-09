$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $Root
$SrcRoot = Join-Path $Root "src"
$Out = Join-Path $Root "out"
$Dist = Join-Path $Root "dist"
$LocalJdk = Join-Path $ProjectRoot ".runtime\jdk21"
$LocalJavac = Join-Path $LocalJdk "bin\javac.exe"
$LocalJar = Join-Path $LocalJdk "bin\jar.exe"

if ((Test-Path $LocalJavac) -and (Test-Path $LocalJar)) {
    $Javac = $LocalJavac
    $Jar = $LocalJar
} elseif ((Get-Command javac -ErrorAction SilentlyContinue) -and (Get-Command jar -ErrorAction SilentlyContinue)) {
    $Javac = "javac"
    $Jar = "jar"
} else {
    Write-Output "JDK_NOT_FOUND: install or add javac/jar to PATH."
    exit 1
}

New-Item -ItemType Directory -Force -Path $Out, $Dist | Out-Null
$Sources = Get-ChildItem -Path $SrcRoot -Recurse -Filter *.java | ForEach-Object { $_.FullName }
& $Javac -encoding UTF-8 -d $Out $Sources
$Manifest = Join-Path $Dist "MANIFEST.MF"
Set-Content -Path $Manifest -Encoding ASCII -Value @(
    "Manifest-Version: 1.0"
    "Main-Class: com.viper.notes.ViperLabSuiteApp"
    ""
)
& $Jar cfm (Join-Path $Dist "viper-java-sdk-standalone.jar") $Manifest -C $Out .
Write-Output "BUILT: $(Join-Path $Dist 'viper-java-sdk-standalone.jar')"
