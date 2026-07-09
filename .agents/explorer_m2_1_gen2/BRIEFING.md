# BRIEFING — 2026-06-26T06:26:35Z

## Mission
Explore the codebase and recommend a strategy for implementing Milestone M2: R1 (desktop_moe_orchestrator.py).

## 🔒 My Identity
- Archetype: Teamwork explorer
- Roles: explorer_1, teamwork_preview_explorer
- Working directory: C:\Users\viper\gan-otg-db\explorer_m2_1_gen2\
- Original parent: 7c6f2ec7-310d-4d8d-8cfb-328b62a9f47e
- Milestone: M2: R1

## 🔒 Key Constraints
- Read-only investigation — do NOT implement
- Only write to folder C:\Users\viper\gan-otg-db\.agents\explorer_m2_1_gen2\
- CODE_ONLY network mode: no external HTTP requests, etc.

## Current Parent
- Conversation ID: 7c6f2ec7-310d-4d8d-8cfb-328b62a9f47e
- Updated: 2026-06-26T06:26:45Z

## Investigation State
- **Explored paths**:
  - `ArchivalMoe/moa_orchestrator.py`
  - `viper-scripts/ask_kai.py`
  - `viper-scripts/ask_claude.py`
  - `viper-scripts/resource_governor.py`
  - `viper-scripts/encrypted_sandbox.py`
  - `viper-scripts/file-registry.py`
  - `viper-scripts/excel_access_automation.py`
  - `viper-scripts/depin_gate.py`
  - `viper-scripts/approve_aider_plan.py`
  - `viper-scripts/search-code.py`
  - `ArchivalMoe/crawler/playwright_crawler.py`
  - `viper-scripts/mic_ring.py`
  - `viper-scripts/talon/viper/viper_moe.py`
  - `viper-scripts/config/policies/SOP-000.md`, `SOP-001.md`, `SOP-002.md`
- **Key findings**:
  - Located the implementation target for `desktop_moe_orchestrator.py` at `C:\Users\viper\gan-otg-db\desktop_moe_orchestrator.py`.
  - Mapped all 11 specialist agents to their exact functional equivalents/tools in `viper-scripts` and layout in `ArchivalMoe/agents/`.
  - Designed the query dispatcher to utilize deterministic keyword/regex classification first (instant, lightweight), falling back to local model routing (via local Ollama/SmolLM or `ask_kai.py`).
- **Unexplored areas**: None.

## Key Decisions Made
- Hybrid routing model: deterministic priority routing followed by LLM classification.
- Structure of the orchestrator to communicate via stdin/stdout JSON lines to support MoeGUI.

## Artifact Index
- C:\Users\viper\gan-otg-db\.agents\explorer_m2_1_gen2\analysis.md — Recommendation report
- C:\Users\viper\gan-otg-db\.agents\explorer_m2_1_gen2\handoff.md — Handoff report
