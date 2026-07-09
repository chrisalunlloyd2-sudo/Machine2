# Original User Request

## Initial Request — 2026-06-26T02:23:53Z

<USER_REQUEST>
This project builds the **Moe Desktop Swarm Orchestrator** on Machine 2. It replicates the 11-agent MoE design but structures it explicitly for local desktop operations, file systems management, database lookups, schema migrations, and active Talon/GitHub integrations.

Working directory: `C:\Users\viper\gan-otg-db`
Integrity mode: `development`

## Requirements

### R1. Moe Desktop Swarm Orchestrator (11-Agent Desktop MoE)
- Implement a structured dispatcher `desktop_moe_orchestrator.py` that routes queries to the following 11 specialist agents:
  1. `systems_info_agent`: Queries resource governor telemetry, CPU/RAM levels, and logs telemetry metrics.
  2. `file_management_agent`: Manages secure sandbox wraps (`encrypted_sandbox`), file registers, and directory cleanup/shredding.
  3. `database_query_agent`: Queries projects, research, code, and nmct catalog SQLite databases.
  4. `schema_migration_agent`: Safely executes DDL/DML schema modifications and updates tables.
  5. `com_excel_agent`: Automates win32com Excel and Access spreadsheet sync operations without resource locks.
  6. `git_sync_agent`: Moniters repo git status and handles automated staging, commits, and pushes to GitHub.
  7. `voice_integration_agent`: Synchronizes Talon profile directories and writes voice heartbeat logs.
  8. `aider_bridge_agent`: Manages pending aider plans and triggers the review/approval pipeline.
  9. `search_research_agent`: Runs local FTS5 research matching and crawler queries.
  10. `memory_episodic_agent`: Manages information tree nodes and logs transaction events.
  11. `policy_enforcement_agent`: Enforces SOP compliance (SOP-000, 001, 002, 003) and DePIN gate leashing.

### R2. JavaFX Swarm Dashboard
- Add a JavaFX visual controller tab in `MoeGUI` that interfaces with `desktop_moe_orchestrator.py` via `viper-package` (JSON stream over stdin/stdout) to show:
  - Active agents status and execution log.
  - Live resource telemetry curves.
  - The 100-step blueprint completion board.

### R3. Talon Voice Control Integration
- Re-target all Talon user directory path mappings under `viper-scripts/talon/` to reference the local `viper` Windows profile path instead of hardcoded `chris` configurations.
- Map voice commands (e.g. "moe query projects", "moe sync excel", "moe database status") to trigger the new desktop MoE engine.
- Add hook logic in Talon python scripts to write status updates to the local heartbeat log `C:\Users\viper\.kai\moe_heartbeat.txt` on a regular cadence.

---

## Acceptance Criteria

### C1. 11-Agent Desktop MoE Router (R1)
- [ ] Querying `desktop_moe_orchestrator.py` with "show CPU load" triggers `systems_info_agent` and returns the metrics.
- [ ] Querying with "commit modified scripts" routes to `git_sync_agent` and pushes to GitHub.
- [ ] Querying with "modify projects schema" triggers `schema_migration_agent` which checks SOP-000 first.
- [ ] The orchestrator uses `Ask_Kai` or local model routing to select the correct agent.

### C2. JavaFX GUI Tabs (R2)
- [ ] Running the Swing/JavaFX application displays the new **Blueprint Tracker** and **Swarm Orchestrator** tabs.
- [ ] The tab successfully displays the completion percentage (e.g. `100.0%`) parsed from the system.
- [ ] The **Telemetry Visualizer** displays CPU/RAM metrics updated dynamically.

### C3. Talon & Heartbeat Verification (R3)
- [ ] No references to the username `chris` remain in the active Talon `.py` or `.talon` files.
- [ ] Activating a Talon script writes a timestamped record to `C:\Users\viper\.kai\moe_heartbeat.txt`.
</USER_REQUEST>
