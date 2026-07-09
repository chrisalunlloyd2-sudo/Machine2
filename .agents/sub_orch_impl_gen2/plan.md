# Implementation Plan: Moe Swarm Orchestrator and Dashboard (Implementation Track)

## Synthesis of Exploration Results

### 1. Milestone M2: R1 (desktop_moe_orchestrator.py)
- **Target Location**: `C:\Users\viper\gan-otg-db\desktop_moe_orchestrator.py`
- **Dispatcher Logic**:
  - Tier 1: Regex/keyword matches:
    - `"show CPU load"` -> `systems_info_agent`
    - `"commit modified scripts"` -> `git_sync_agent`
    - `"modify projects schema"` -> `schema_migration_agent`
  - Tier 2: Local model query fallback (via SmolLM2/qwen).
  - Tier 3: Ask_Kai / Parental routing fallback (via `kqml_bridge` / `ask_kai.py`).
- **Specialist Agent Implementations**:
  - `systems_info_agent`: Calls `resource_governor.py` and `cpu_governor.py` to get CPU/RAM/affinity metrics.
  - `schema_migration_agent`: Checks `SOP-000` compliance (prohibiting DROP/DELETE/TRUNCATE) before performing any database updates on projects/research/code/nmct. Backs up database to `C:\Viper\backups\databases` first.
  - `database_query_agent`: Accesses sqlite databases in read-only mode, rejecting write actions.
  - `policy_enforcement_agent`: Evaluates compliance with SOP-000, SOP-001, SOP-002, SOP-003, and integrates `depin_gate.py` leashing.
  - Other specialist agents (`file_management_agent`, `com_excel_agent`, `git_sync_agent`, `voice_integration_agent`, `aider_bridge_agent`, `search_research_agent`, `memory_episodic_agent`) map to their existing scripts or mock actions.

### 2. Milestone M3: R2 (JavaFX Swarm Dashboard)
- **Target Files**: Under `MoeGUI/src/main/java/com/viper/moe/`:
  - `PythonBridge.java`: Re-route target to `C:\Users\viper\gan-otg-db\desktop_moe_orchestrator.py`. Update `readLoop` to process telemetry JSON packets.
  - `MoeController.java` & `MoeApp.java`: Replace `SplitPane` with a `TabPane`.
    - Tab 1: Chat interface (original sidebar + history).
    - Tab 2: Swarm Dashboard (Telemetry clocks/progress bars, Agent Status grid of 11 cards, 100-step blueprint progress and checklist).
  - Trigger telemetry query `{"telemetry_request": true}` every 5 seconds.

### 3. Milestone M4: R3 (Talon Integration)
- **Target Files**: Under `viper-scripts/talon/viper/`:
  - Symlink `C:\Users\viper\.talon\user\viper` -> `C:\Users\viper\gan-otg-db\viper-scripts\talon\viper`
  - Re-target all hardcoded `chris` path references to `viper` in `moe_mcp_server.py`, `prefetch.py`, `heartbeat_responder.py`, `moe-report.py`, `viper_llm_server.py`, and `wrappers.py`.
  - Update `viper_moe.py` to append timestamped voice activation records to `C:\Users\viper\.kai\moe_heartbeat.txt`.

---

## Execution Checklist

### Milestone M2: R1 (desktop_moe_orchestrator.py & specialist agents)
- [ ] Create `desktop_moe_orchestrator.py` at project root with the modular agent architecture and JSON-stdio interface.
- [ ] Implement query classification routing (Tier 1 deterministic, Tier 2 local model, Tier 3 Ask_Kai).
- [ ] Implement `systems_info_agent` querying resource governor telemetry.
- [ ] Implement `schema_migration_agent` DDL/DML runner with backup creation and SOP-000 safety validation.
- [ ] Implement `database_query_agent` read-only wrapper.
- [ ] Implement `policy_enforcement_agent` checking SOP-000/001/002/003 and DePIN gating.
- [ ] Validate orchestrator manually using mock JSON inputs and verify it outputs proper JSON stream packets.

### Milestone M3: R2 (MoeGUI JavaFX Dashboard)
- [ ] Refactor `MoeController.java` and `MoeApp.java` to use a `TabPane`.
- [ ] Add the Swarm Dashboard tab UI layout (telemetry indicators, agent status grid, blueprint progress board).
- [ ] Update `PythonBridge.java` process execution to point to `desktop_moe_orchestrator.py`.
- [ ] Modify `PythonBridge.java` read loop to parse and update the UI with telemetry and agent status.
- [ ] Add the 5-second `telemetry_request` query scheduler in `MoeController.java`.

### Milestone M4: R3 (Talon path retargeting and heartbeat hook)
- [ ] Sweep `viper-scripts` for all occurrences of `C:\Users\chris` (and `chrisalunlloyd2-sudo` if needed) and replace with `C:\Users\viper`.
- [ ] Implement `write_moe_heartbeat` hook in `viper_moe.py` writing to `C:\Users\viper\.kai\moe_heartbeat.txt` on command triggers.
- [ ] Set up the active profile symlink `C:\Users\viper\.talon\user\viper`.

### Milestone M5: Final verification
- [ ] Confirm E2E test suite is ready (`TEST_READY.md`).
- [ ] Run the complete E2E test suite and ensure all features of R1, R2, R3 pass.
- [ ] Perform Tier 5 adversarial coverage hardening.
