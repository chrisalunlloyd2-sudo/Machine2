# VIPER Machine 2 — The Database & Mining Engine

> **Sovereign database orchestration, Karoo GP code mining, and dual-channel bridge to Machine 1.**

[![Machine 2](https://img.shields.io/badge/Machine-2-a78bfa?style=flat-square)](https://github.com/chrisalunlloyd2-sudo/Machine2)
[![Status](https://img.shields.io/badge/Status-LIVE-22c55e?style=flat-square)](#services)

---

## Architecture

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                    VIPER SYSTEM — DUAL MACHINE ARCHITECTURE                 ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ┌─────────────────────────┐        ┌─────────────────────────────────┐     ║
║  │     MACHINE 1           │        │        MACHINE 2                │     ║
║  │  (Aegis / Picoclaw)     │        │   (VIPER JAVA RISC)            │     ║
║  │                         │        │                                 │     ║
║  │  - SLM Agent Loop       │◄══════►│  - Karoo Code Miner            │     ║
║  │  - Aegis Prompts        ║CHANNEL ║  - OTG Dual Bridge             │     ║
║  │  - Inference            ║A:18283 ║  - Omniscient HUD              │     ║
║  │  - Research Tasks       ║B:18284 ║  - Database Engine             │     ║
║  │  - Reasoning Loops      │        │  - Sovereign Loop              │     ║
║  │                         │        │  - MoE Server                  │     ║
║  └─────────────────────────┘        └─────────────────────────────────┘     ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

Machine 2 Internal Data Flow:
═══════════════════════════════════════════════════════════════════════════════

  SOURCE FILES                   KAROO CODE MINER (:karoo_code_miner.py)
  ┌──────────┐                   ┌────────────────────────────────────────┐
  │ .py      │                   │  Extract:                              │
  │ .java    │──► scan ─────────►│  • Function/class blocks              │
  │ .js      │    all            │  • Algorithm patterns (sort, DP, etc) │
  │ .go      │    source         │  • Logit sequences                    │
  │ .rs      │    dirs           │  • Syntax tree nodes                  │
  │ .sql     │                   │  • Lexical vectors (token fingerprint)│
  └──────────┘                   └──────────────┬─────────────────────────┘
                                                 │
                                                 ▼
                                  ┌──────────────────────┐
                                  │   code.db            │
                                  │  (code_artifacts)    │◄── PRIMARY STORE
                                  │  hash | language     │
                                  │  code_text | vector  │
                                  │  block_type | status │
                                  └──────────┬───────────┘
                                             │
                    ┌────────────────────────┼────────────────────────┐
                    │                        │                        │
                    ▼                        ▼                        ▼
         ┌─────────────────┐   ┌──────────────────────┐   ┌─────────────────┐
         │  OTG Dual       │   │  Omniscient HUD      │   │  gemini_bridge  │
         │  Bridge         │   │  :18282              │   │  .db            │
         │  :18283 / 18284 │   │  /api/mined_blocks   │   │  (Karoo GP      │
         │  ─────────────  │   │  /api/dashboard/     │   │   evolution)    │
         │  ┌───────────┐  │   │  evolution-stats      │   └─────────────────┘
         │  │ Channel A │  │   │  /api/dashboard/     │
         │  │ (primary) │  │   │  phase5              │
         │  └───────────┘  │   └──────────────────────┘
         │  ┌───────────┐  │
         │  │ Channel B │  │──────────────────────────────► Machine 1
         │  │(redundant)│  │   blocks + patterns + logits
         │  └───────────┘  │
         └─────────────────┘


Port Map:
═════════
  :1234   LM Studio API          (enable server in LM Studio)
  :8765   SLM Station Proxy      → auto-routes to LM Studio or House Engine
  :11435  House Inference Engine → LM Studio (1234) or llama-cpp
  :18181  Java SDK Server        → Training Lab dashboard
  :18282  Omniscient HUD         → GAN metrics, Phase 5, evolution, blocks
  :18283  OTG Bridge Channel A   → Machine 1 PRIMARY comm
  :18284  OTG Bridge Channel B   → Machine 1 REDUNDANT comm


Service Registry:
═════════════════
  viper_omniscient_hud.py     → HUD & monitoring
  viper_slm_station_proxy.py  → LLM inference router
  viper_master_watchdog.py    → Keeps all services alive (supervisor)
  karoo_code_miner.py         → Code block mining from all source dirs
  otg_dual_bridge.py          → Dual-channel M1↔M2 bridge
  viper_daily_email.py        → 7am daily status to chrisa@gmail.com
  viper_dep_install.py        → Global dependency installer
  house_inference_engine.py   → Local LLM (LM Studio primary)
  sovereign_loop.py           → Regulated Moe→Kai→Qwen loop
  moe_server.py               → Mixture of Experts routing
  viper_llm_server.py         → OpenAI-compat LLM server :8765
  otg_db_bridge.py            → Original OTG bridge (Machine2 repo)
```

---

## Quick Start

```powershell
# 1. Install dependencies
python tools\viper_dep_install.py

# 2. Launch everything (one click)
.\LAUNCH_VIPER.ps1   # or double-click on Desktop

# 3. Start Karoo miner
python tools\karoo_code_miner.py

# 4. Start dual bridge (Machine 1 comms)
python tools\otg_dual_bridge.py

# 5. Schedule daily email
python tools\viper_daily_email.py --install-task
```

---

## GitHub Repos

| Repo | Contents |
|------|----------|
| [Machine2](https://github.com/chrisalunlloyd2-sudo/Machine2) | OTG bridge, MoE, sovereign loop, databases |
| [VIPER-HUD](https://github.com/chrisalunlloyd2-sudo/VIPER-HUD) | Omniscient HUD — GAN, Phase5, Karoo panels |
| [VIPER-Manifold](https://github.com/chrisalunlloyd2-sudo/VIPER-Manifold) | RISC Manifold chat + SLM proxy |
| [VIPER-Training-SDK](https://github.com/chrisalunlloyd2-sudo/VIPER-Training-SDK) | Java SDK training lab, Loihi topology |

---

## Karoo Code Miner

Mines blocks from all source directories for these languages:
`Python • Java • JavaScript • TypeScript • Go • Rust • SQL • C • C++ • Bash • PowerShell`

What it mines:
- **Function blocks** — complete functions/classes/methods
- **Algorithm patterns** — sort, search, DP, graph, ML, async, generators, decorators
- **Logit sequences** — token probability patterns from code structure
- **Lexical vectors** — top-20 token frequency fingerprints for fast similarity search

All blocks stored in `code.db` → served by HUD at `/api/mined_blocks` → sent to Machine 1 via OTG Bridge.

---

## Machine 1 Integration

Machine 1 polls Machine 2 at:
- `GET http://machine2:18283/api/blocks/recent?since=<id>&limit=50`
- `POST http://machine2:18283/api/m1/receive` (send logits/aegis prompts to M2)

Machine 2 pushes to Machine 1 at:
- `POST http://machine1/api/m2/receive` (new mined blocks, patterns)

**Dual channel**: If Channel A (18283) fails, Channel B (18284) auto-takes over. Messages queue with replay — no data lost.

---

## Daily Status Email

Sent to `chrisa@gmail.com` daily at 7:00 AM.

Setup:
```powershell
# 1. Get Gmail App Password: myaccount.google.com/apppasswords
# 2. Set it:
setx VIPER_EMAIL_PASS "xxxx xxxx xxxx xxxx"
# 3. Install task:
python tools\viper_daily_email.py --install-task
```

---

## Version

`v2.0.0` — Karoo miner, dual-bridge, daily email, LM Studio backend, watchdog v2.1
