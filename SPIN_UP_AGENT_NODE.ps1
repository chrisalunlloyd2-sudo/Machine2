param(
    [string]$NodeRoot = $env:VIPER_NODE_ROOT,
    [string]$NasRoot = $env:VIPER_NAS_ROOT
)

$ErrorActionPreference = "Stop"
$SourceRoot = "C:\Users\viper\VIPER_JAVA_RISC"
if ([string]::IsNullOrWhiteSpace($NodeRoot)) {
    $NodeRoot = Join-Path ([Environment]::GetFolderPath("Desktop")) "VIPER_AGENT_NODE"
}

New-Item -ItemType Directory -Force -Path $NodeRoot | Out-Null

$Include = @(
    "README.md",
    "JAVA_SDK_PERSISTENCE_DESIGN.md",
    "RESOURCE_NETWORK_PROTOCOL.md",
    "AGENT_APP_DEV_PROTOCOL.md",
    "AGENT_SPECS.md",
    "tools",
    "java_notes_suite",
    "models\tiny",
    "START_HOUSE_ENGINE_RECOVERY.ps1",
    "CREATE_VIPER_NAS_LINK.ps1"
)

foreach ($item in $Include) {
    $src = Join-Path $SourceRoot $item
    if (Test-Path -LiteralPath $src) {
        $dst = Join-Path $NodeRoot $item
        if ((Get-Item -LiteralPath $src).PSIsContainer) {
            Copy-Item -LiteralPath $src -Destination $dst -Recurse -Force
        } else {
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dst) | Out-Null
            Copy-Item -LiteralPath $src -Destination $dst -Force
        }
    }
}

$envFile = Join-Path $NodeRoot "VIPER_NODE_ENV.ps1"
Set-Content -LiteralPath $envFile -Encoding UTF8 -Value @"
`$env:VIPER_NODE_ROOT = "$NodeRoot"
`$env:VIPER_NAS_ROOT = "$NasRoot"
`$env:VIPER_TINY_CHOOSER_MODEL = "$NodeRoot\models\tiny\qwen2_5_0_5b_instruct\qwen2.5-0.5b-instruct-q4_k_m.gguf"
`$env:VIPER_RETRIEVAL_MATCHER_MODEL = "$NodeRoot\models\tiny\smollm2_360m_instruct\SmolLM2-360M-Instruct-Q4_K_M.gguf"
`$env:VIPER_RETRIEVAL_FALLBACK_MODEL = "$NodeRoot\models\tiny\h2o_danube3_500m_chat_fallback\h2o-danube3-500m-chat-Q4_K_M.gguf"
"@

[pscustomobject]@{
    status = "agent_node_staged"
    nodeRoot = $NodeRoot
    nasRoot = $NasRoot
    next = "Copy this folder to a node, run VIPER_NODE_ENV.ps1, then run START_HOUSE_ENGINE_RECOVERY.ps1 if that node owns house inference."
} | ConvertTo-Json -Compress
