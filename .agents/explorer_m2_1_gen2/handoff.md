# Explorer 1 Handoff Report — Milestone M2: R1 Strategy

## 1. Observation
We observed the following files and directories in `C:\Users\viper\gan-otg-db`:
*   **Target Path**: `PROJECT.md` line 21 explicitly designates:
    > `desktop_moe_orchestrator.py` -> `C:\Users\viper\gan-otg-db\desktop_moe_orchestrator.py`
*   **Specialist Agent Descriptions**: `PROJECT.md` lines 5–16 lists the 11 specialist agents:
    > 1. `systems_info_agent`: Queries resource governor telemetry...
    > 2. `file_management_agent`: Manages secure sandbox wraps...
    > 3. `database_query_agent`: Queries projects, research...
    > 4. `schema_migration_agent`: Safely executes DDL/DML schema modifications...
    > 5. `com_excel_agent`: Automates win32com Excel and Access spreadsheet sync...
    > 6. `git_sync_agent`: Monitors repo git status and handles automated staging...
    > 7. `voice_integration_agent`: Synchronizes Talon profile directories...
    > 8. `aider_bridge_agent`: Manages pending aider plans...
    > 9. `search_research_agent`: Runs local FTS5 research matching...
    > 10. `memory_episodic_agent`: Manages information tree nodes...
    > 11. `policy_enforcement_agent`: Enforces SOP compliance...
*   **Telemetry Integration**: `viper-scripts/resource_governor.py` lines 137–142 contains:
    ```python
    def snapshot() -> dict:
        cpu, ram = _cpu_ram()
        state = "critical" if (cpu >= CRITICAL_CPU or ram >= CRITICAL_RAM) else \
                "idle" if cpu < 25 else "normal" if cpu < 55 else "busy"
        return {"cpu": round(cpu, 1), "ram": round(ram, 1), "state": state,
                "ts": datetime.now().isoformat(timespec="seconds")}
    ```
*   **Policy Constraints**: `viper-scripts/config/policies/SOP-000.md` lines 1-4:
    > # SOP: Never Delete Codebases
    > **ID:** SOP-000 | **Version:** 1.0.0
    > All scripts must keep original headers and structure. Never do destructive updates or truncates of existing files.
*   **DePIN Gate Leash**: `viper-scripts/depin_gate.py` lines 56–74 details the `gate` function checking telemetry before communication.
*   **GUI Interface Contract**: `PROJECT.md` lines 37-39 specifies the JSON schema:
    > - Input: `{"query": "...", "project": "..."}` or `{"telemetry_request": true}`
    > - Output: `{"token": "..."}` (optional stream), `{"answer": "...", "done": true}` (final) or `{"telemetry": {"cpu": X, "ram": Y}, "blueprint": {"completed_pct": Z}}`

---

## 2. Logic Chain
1. **Target Identification**: Based on `PROJECT.md` line 21, the orchestrator script must be placed at `C:\Users\viper\gan-otg-db\desktop_moe_orchestrator.py`.
2. **Specialist Mapping**: Each of the 11 agents corresponds directly to scripts in `viper-scripts/` or `ArchivalMoe/agents/` (e.g. `systems_info_agent` delegates to `resource_governor.py`, `com_excel_agent` calls `excel_access_automation.py`, `policy_enforcement_agent` applies `depin_gate.py` gating and SOP verification).
3. **Safety Compliance**: Since `schema_migration_agent` modifies DB schemas, it must run a verification step reading `viper-scripts/config/policies/SOP-000.md` to check that the transaction is non-destructive (e.g. no DROP, DELETE, or truncate calls) before executing.
4. **Three-Tier Query Dispatching**:
    *   To guarantee instant responses to specified test queries, **Tier 1 (Deterministic Keyword/Regex)** intercepts `"show CPU load"` (routes to `systems_info_agent`), `"commit modified scripts"` (routes to `git_sync_agent`), and `"modify projects schema"` (routes to `schema_migration_agent`).
    *   **Tier 2 (Local LLM Classifier)** uses the local Ollama API running `qwen2.5-coder:0.5b` or `SmolLM2` for lightweight, non-deterministic routing.
    *   **Tier 3 (Ask_Kai/Parental Routing)** provides a fallback when the local environment is under resource pressure or offline, using `ask_kai.py`'s bridge to delegate classification to the parent Kai agent.
5. **Dashboard Communication**: The orchestrator must run a continuous non-blocking loop listening to `sys.stdin` and writing JSON-encoded lines to `sys.stdout` to fulfill the MoeGUI interface contract.

---

## 3. Caveats
*   We assumed the local Ollama service (`http://127.0.0.1:11434`) is running or will be running during deployment of M2.
*   We did not test the physical Talon voice profile directories or win32com Excel interactions as this is a read-only investigation.
*   `kqml_bridge.py` does not reside locally in `gan-otg-db/viper-scripts`, but is imported by `ask_kai.py`, which suggests it is provided by the global Python environment on the host machine.

---

## 4. Conclusion
Milestone M2: R1 should be implemented by creating a root-level script `C:\Users\viper\gan-otg-db\desktop_moe_orchestrator.py`. It should integrate the 11 specialist agents by importing their corresponding functional scripts from `viper-scripts/`. It must utilize a three-tier hybrid dispatcher (Deterministic Keyword $\rightarrow$ Local LLM Classifier $\rightarrow$ Ask_Kai Bridge) and support a stdin/stdout JSON lines stream matching the MoeGUI interface contract.

---

## 5. Verification Method
1. Inspect the implementation of `desktop_moe_orchestrator.py` at `C:\Users\viper\gan-otg-db\desktop_moe_orchestrator.py`.
2. Verify communication using JSON line inputs via command line:
   ```powershell
   echo '{"telemetry_request": true}' | python C:\Users\viper\gan-otg-db\desktop_moe_orchestrator.py
   ```
   Ensure it returns correct telemetry keys.
3. Validate routing for query `"show CPU load"` and check that `systems_info_agent` is targeted.
