# Project: Moe Desktop Swarm Orchestrator

## Architecture
- **desktop_moe_orchestrator.py**: The central dispatcher routing queries (using Ask_Kai or local model routing) to 11 specialist agents.
- **Specialist Agents**:
  1. `systems_info_agent`: Queries resource governor telemetry, CPU/RAM levels, and logs telemetry metrics.
  2. `file_management_agent`: Manages secure sandbox wraps (`encrypted_sandbox`), file registers, and directory cleanup/shredding.
  3. `database_query_agent`: Queries projects, research, code, and nmct catalog SQLite databases.
  4. `schema_migration_agent`: Safely executes DDL/DML schema modifications and updates tables.
  5. `com_excel_agent`: Automates win32com Excel and Access spreadsheet sync operations without resource locks.
  6. `git_sync_agent`: Monitors repo git status and handles automated staging, commits, and pushes to GitHub.
  7. `voice_integration_agent`: Synchronizes Talon profile directories and writes voice heartbeat logs.
  8. `aider_bridge_agent`: Manages pending aider plans and triggers the review/approval pipeline.
  9. `search_research_agent`: Runs local FTS5 research matching and crawler queries.
  10. `memory_episodic_agent`: Manages information tree nodes and logs transaction events.
  11. `policy_enforcement_agent`: Enforces SOP compliance (SOP-000, 001, 002, 003) and DePIN gate leashing.
- **MoeGUI Dashboard**: A JavaFX visual controller tab (Blueprint Tracker, Swarm Orchestrator, Telemetry Visualizer) communicating with `desktop_moe_orchestrator.py` via `viper-package` (JSON stream over stdin/stdout).
- **Talon Voice Control Integration**: Re-targeted scripts under `viper-scripts/talon/` using `viper` instead of `chris`, with hook to write heartbeat logs to `C:\Users\viper\.kai\moe_heartbeat.txt`.

## Code Layout
- `desktop_moe_orchestrator.py` -> `C:\Users\viper\gan-otg-db\desktop_moe_orchestrator.py`
- `viper-package` updates -> `C:\Users\viper\gan-otg-db\viper-package\`
- `MoeGUI` updates -> `C:\Users\viper\gan-otg-db\MoeGUI\`
- `Talon` scripts updates -> `C:\Users\viper\gan-otg-db\viper-scripts\talon\`
- E2E Tests -> `C:\Users\viper\gan-otg-db\viper-scripts\test_moe_e2e_new.py`

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | M1: E2E Testing Suite | Create requirement-driven E2E tests for R1, R2, R3 | None | IN_PROGRESS (Conv: 090ca5ab-30d6-4757-8634-69b0ea2133a1) |
| 2 | M2: Swarm Dispatcher | Implement `desktop_moe_orchestrator.py` and 11 specialist agents | M1 | IN_PROGRESS (Conv: 7c6f2ec7-310d-4d8d-8cfb-328b62a9f47e) |
| 3 | M3: JavaFX Dashboard | Implement Blueprint Tracker, Swarm Orchestrator, and Telemetry in MoeGUI | M1, M2 | IN_PROGRESS (Conv: 7c6f2ec7-310d-4d8d-8cfb-328b62a9f47e) |
| 4 | M4: Talon Voice | Re-target user path mappings, map voice commands, add status hooks | M1, M2 | IN_PROGRESS (Conv: 7c6f2ec7-310d-4d8d-8cfb-328b62a9f47e) |
| 5 | M5: E2E Integration Verification | Run E2E tests to verify full system integration and pass audit | M1, M2, M3, M4 | IN_PROGRESS (Conv: 7c6f2ec7-310d-4d8d-8cfb-328b62a9f47e) |

## Interface Contracts
### JavaFX GUI ↔ desktop_moe_orchestrator.py (via viper-package / stdin/stdout)
- Input: `{"query": "...", "project": "..."}` or `{"telemetry_request": true}`
- Output: `{"token": "..."}` (optional stream), `{"answer": "...", "done": true}` (final) or `{"telemetry": {"cpu": X, "ram": Y}, "blueprint": {"completed_pct": Z}}`
