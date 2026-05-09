# VIPER Tiny Model Manifest

Local GGUF weights are intentionally git-ignored.

```text
chooser:
  repo: Qwen/Qwen2.5-0.5B-Instruct-GGUF
  file: qwen2.5-0.5b-instruct-q4_k_m.gguf
  role: max-100-word active lens, rolling triplet control

retrieval:
  repo: unsloth/SmolLM2-360M-Instruct-GGUF
  file: SmolLM2-360M-Instruct-Q4_K_M.gguf
  role: closest 50-word axiomatic DB match

retrieval_fallback:
  repo: h2oai/h2o-danube3-500m-chat-GGUF
  file: h2o-danube3-500m-chat-Q4_K_M.gguf
  role: fallback matcher when SmolLM2 is unavailable
```

Environment overrides:

```powershell
$env:VIPER_TINY_CHOOSER_MODEL="C:\path\to\qwen2.5-0.5b-instruct-q4_k_m.gguf"
$env:VIPER_RETRIEVAL_MATCHER_MODEL="C:\path\to\SmolLM2-360M-Instruct-Q4_K_M.gguf"
$env:VIPER_RETRIEVAL_FALLBACK_MODEL="C:\path\to\h2o-danube3-500m-chat-Q4_K_M.gguf"
```
