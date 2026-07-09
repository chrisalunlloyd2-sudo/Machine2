# Scope: Moe Desktop Swarm Orchestrator and Integration (Implementation Track)

## Architecture
- **desktop_moe_orchestrator.py**: The dispatcher that routes queries to the 11 specialist agents. Interfaced by JavaFX via JSON streams.
- **MoeGUI** (JavaFX): Visual controller dashboard that spawns and communicates with `desktop_moe_orchestrator.py` via `viper-package` protocol (JSON stream over stdin/stdout).
- **Talon Integration**: Retargeted Talon scripts mapping voice commands to the desktop Moe engine and writing heartbeat logs to `C:\Users\viper\.kai\moe_heartbeat.txt`.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M2 | R1 (Desktop Moe Orchestrator) | Implement `desktop_moe_orchestrator.py` with 11 specialist agents and query routing, using `Ask_Kai` or local model routing. Routes CPU load, git commits, schema modification (checking SOP-000 first). | None | PLANNED |
| M3 | R2 (JavaFX Swarm Dashboard) | Add JavaFX visual controller tab in MoeGUI interfacing via viper-package to show agent status, telemetry, and 100-step blueprint completion. | M2 | PLANNED |
| M4 | R3 (Talon Integration) | Retarget user profiles from chris to viper under `viper-scripts/talon/`, map voice commands, write voice heartbeat to `C:\Users\viper\.kai\moe_heartbeat.txt`. | M2 | PLANNED |
| M5 | Final Verification & Hardening | Pass 100% E2E tests, poll for `TEST_READY.md`, perform Tier 5 adversarial coverage hardening. | M2, M3, M4 | PLANNED |

## Interface Contracts
### JavaFX MoeGUI ↔ desktop_moe_orchestrator.py
- JSON stream over stdin/stdout.
- Input format: `{"query": "...", "project": "..."}` or `{"telemetry_request": true}`
- Output format: `{"token": "..."}` for streaming, and `{"answer": "...", "done": true}` as the final response, OR telemetry responses like `{"telemetry": {"cpu": X, "ram": Y}, "blueprint": {"completed_pct": Z}}`

### Talon Script ↔ Heartbeat
- Talon python scripts write regular timestamped logs to `C:\Users\viper\.kai\moe_heartbeat.txt`.
