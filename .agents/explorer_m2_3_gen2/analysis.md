# Analysis and Implementation Recommendation Report: JavaFX Swarm Dashboard & Talon Integration

This report provides a comprehensive analysis of the existing JavaFX code (`MoeGUI`) and the voice control configuration (`Talon`), mapping out a robust implementation strategy for Milestones M3 and M4.

---

## 1. MoeGUI JavaFX Application Structure

The current JavaFX application files are located under `C:\Users\viper\gan-otg-db\MoeGUI\src\main\java\com\viper\moe\`:
*   **`MoeApp.java`**: Main JavaFX entry point. Spawns the Stage, loads `/css/dark.css`, initializes `MoeController`, and calls `startLiveUpdates()`.
*   **`MoeController.java`**: Constructs the layout using a `SplitPane` (left=Sidebar, right=Chat History and Input Bar) and handles query submission, database stats queries, and the live tick timer (5s database telemetry refresh / 30s project list reload).
*   **`PythonBridge.java`**: Initiates a JSON-over-stdio pipe to the Python backend (currently hardcoded to `C:\Viper\projects\ArchivalMoe\moe_server.py`) using a Jackson `ObjectMapper` and runs a daemon read-loop thread to process tokens and full replies.
*   **`DbStatus.java`**: A helper class querying local SQLite files directly via JDBC (`DriverManager.getConnection("jdbc:sqlite:...")`) to retrieve active project entries and row counts of standard tables.

---

## 2. JavaFX ↔ Orchestrator Communication Protocol

To support the Swarm Dashboard, `MoeGUI` needs to interface with `desktop_moe_orchestrator.py` via `viper-package` instead of direct LLM queries in `moe_server.py`. 

### A. Process Redirection
In `PythonBridge.java`, update the default server path to target `desktop_moe_orchestrator.py`:
```java
private static final String MOE_SERVER = "C:\\Users\\viper\\gan-otg-db\\desktop_moe_orchestrator.py";
```

### B. Message Schemas over Stdin/Stdout
1.  **Periodic Telemetry Query (JavaFX to Orchestrator)**:
    Every 5 seconds, the GUI sends:
    ```json
    {"telemetry_request": true}
    ```
2.  **Telemetry Response (Orchestrator to JavaFX)**:
    The orchestrator responds with:
    ```json
    {
      "telemetry": {
        "cpu": 15.2,
        "ram": 62.8
      },
      "blueprint": {
        "completed_pct": 82.0,
        "completed_steps": 82,
        "total_steps": 100
      },
      "agents": {
        "systems_info_agent": "idle",
        "file_management_agent": "idle",
        "database_query_agent": "idle",
        "schema_migration_agent": "idle",
        "com_excel_agent": "idle",
        "git_sync_agent": "running",
        "voice_integration_agent": "idle",
        "aider_bridge_agent": "idle",
        "search_research_agent": "idle",
        "memory_episodic_agent": "idle",
        "policy_enforcement_agent": "idle"
      }
    }
    ```
3.  **Active Query Updates (Orchestrator to JavaFX)**:
    When a normal query is running, progress is streamed via:
    ```json
    {"active_agent": "git_sync_agent", "status": "running", "completion_percentage": 45.0, "log_line": "Staging modified changes..."}
    ```
    And the final response:
    ```json
    {"answer": "Git repositories successfully committed and pushed to GitHub.", "done": true}
    ```

### C. UI layout Modifications in `MoeController.java`
*   Replace the top-level `SplitPane` layout with a `TabPane` containing two tabs:
    1.  **Moe Chat**: Houses the original chat and project sidebar layout (returned by the current `buildLayout()`).
    2.  **Swarm Dashboard**: A dashboard consisting of:
        *   *Telemetry Section*: Two `ProgressBar` or circular dial controls representing CPU and RAM utilization.
        *   *Agent Status Grid*: A `TilePane` or `GridPane` showing card layouts for all 11 specialist sub-agents (each containing a status light (red/green/yellow) and the agent's name).
        *   *Blueprint Tracker*: A visual progress bar of the 100-step blueprint showing overall percentage and an interactive scrollable list of the 8 phases (clicking on a phase expands it to list the individual step statuses parsed from `CLAUDE_GAN_100_STEPS_BLUEPRINT.md` via `blueprint_orchestrator.py`).
        *   *Control Center*: Quick trigger buttons for Excel Sync (win32com) and the Talon Loop.

---

## 3. Talon Script Locating & Retargeting

### A. Script Locations
Talon voice integration scripts are stored in:
*   `C:\Users\viper\gan-otg-db\viper-scripts\talon\viper\viper_moe.py`
*   `C:\Users\viper\gan-otg-db\viper-scripts\talon\viper\viper_moe.talon`
*   `C:\Users\viper\gan-otg-db\viper-scripts\talon\viper\viper_model.talon`
*   `C:\Users\viper\gan-otg-db\viper-scripts\talon\viper\viper_model_key.py`

### B. Profile Activation
Currently, the directory is not active. The Talon user profile resides at `C:\Users\viper\.talon\user\`.
*   **Recommendation**: To activate the scripts, create a symbolic link pointing to the repository:
    ```powershell
    New-Item -ItemType SymbolicLink -Path "C:\Users\viper\.talon\user\viper" -Target "C:\Users\viper\gan-otg-db\viper-scripts\talon\viper"
    ```

### C. Voice Commands Mappings
The voice commands in `viper_moe.talon` map spoken syntax to the actions defined in `viper_moe.py`:
*   `moe status` $\rightarrow$ `user.viper_moe_order("status all")`
*   `moe approve all` $\rightarrow$ `user.viper_moe_order("approve all")`
*   `moe organize notes` $\rightarrow$ `user.viper_moe_order("organize notes")`
*   `moe guardrails` $\rightarrow$ `user.viper_moe_order("guardrails status")`
*   `moe review <user.text>` $\rightarrow$ `user.viper_moe_order("code review {text}")`
*   `moe order <user.text>` $\rightarrow$ `user.viper_moe_order(text)`
*   `kai ask <user.text>` $\rightarrow$ `user.viper_ask_kai(text)`
*   `viper loop start` $\rightarrow$ `user.viper_loop_start()` (initiates a 5-minute cron loop running `loop_tick()`)
*   `viper loop stop` $\rightarrow$ `user.viper_loop_stop()`

### D. Hardcoded 'chris' Paths & Mappings
The following files outside `viper_moe.py` contain legacy references to the user `chris` (e.g. `C:\Users\chris\...` or `chrisalunlloyd2-sudo`) and must be refactored to `viper`:
1.  **`viper-scripts/moe_mcp_server.py`**:
    *   Line 120: `p = r"C:\Users\chris\.kai\moe_heartbeat.txt"` $\rightarrow$ change to `C:\Users\viper\...`
2.  **`viper-scripts/prefetch.py`**:
    *   Line 20: `HEARTBEAT = r"C:\Users\chris\.kai\moe_heartbeat.txt"` $\rightarrow$ change to `C:\Users\viper\...`
3.  **`viper-scripts/heartbeat_responder.py`**:
    *   Line 22-23: `HEARTBEAT = r"C:\Users\chris\.kai\moe_heartbeat.txt"`, `HBLOG = r"C:\Users\chris\.kai\heartbeat.log"` $\rightarrow$ change to `C:\Users\viper\...`
4.  **`viper-scripts/moe-report.py`**:
    *   Line 20: `DESKTOP = r"C:\Users\chris\Desktop"` $\rightarrow$ change to `C:\Users\viper\...`
5.  **`viper-scripts/viper_llm_server.py`**:
    *   Lines 174-180: Hardcoded paths pointing to LMStudio models under `C:\Users\chris\.lmstudio\...` and Tiny models under `C:\Users\chris\OneDrive\Desktop\...` $\rightarrow$ change to `C:\Users\viper\...`
6.  **`viper-scripts/wrappers.py`**:
    *   Line 20: `OLLAMA = r"C:\Users\chris\.lmstudio\..."` $\rightarrow$ change to `C:\Users\viper\...`
7.  **`viper-scripts/repo_describe.py`** and **`update.py`**:
    *   Git ownership check mapping `chrisalunlloyd2-sudo` $\rightarrow$ confirm compatibility or dynamically resolve user environment variables.

---

## 4. Heartbeat Status Hook Logic in Talon Scripts

To satisfy the E2E verification test suite (which monitors modifications to `C:\Users\viper\.kai\moe_heartbeat.txt`), we must insert status hooks inside the Talon python script (`viper_moe.py`).

### Hook Definition
Create a utility function inside `viper_moe.py` to append/update the heartbeat file:
```python
def write_moe_heartbeat(action_desc: str):
    """Writes status updates to the local heartbeat log."""
    from datetime import datetime
    import os
    hb_path = r"C:\Users\viper\.kai\moe_heartbeat.txt"
    try:
        os.makedirs(os.path.dirname(hb_path), exist_ok=True)
        # Append action activation log
        with open(hb_path, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.utcnow().isoformat()}] Talon voice trigger: {action_desc}\n")
    except Exception as e:
        print(f"[Talon Heartbeat Error] {e}")
```

### Hook Injection Mappings
Call `write_moe_heartbeat` within the Talon action implementations:
*   Inside `viper_moe_order(cmd)`:
    ```python
    write_moe_heartbeat(f"moe_order: {cmd}")
    ```
*   Inside `viper_ask_kai(question)`:
    ```python
    write_moe_heartbeat(f"ask_kai: {question}")
    ```
*   Inside `viper_loop_start()`:
    ```python
    write_moe_heartbeat("start_talon_loop")
    ```
*   Inside `viper_loop_stop()`:
    ```python
    write_moe_heartbeat("stop_talon_loop")
    ```

---

## 5. Detailed Implementation Strategy

To implement these changes without system regression:

### Phase A: Environment Preparation (Milestone M4 Preparation)
1.  **Symlink creation**: Create the symbolic link mapping the git repo's `viper` directory to the active Talon profile location.
2.  **Chris paths clean up**: Run a sweep over all `viper-scripts/*.py` files to swap `C:\Users\chris` paths with `C:\Users\viper`.
3.  **Ensure Directory**: Ensure `C:\Users\viper\.kai\` directory is created and permissioned.

### Phase B: Python Backend Telemetry Setup (Milestone M2 Dependents)
1.  Verify that `desktop_moe_orchestrator.py` handles input parsing of `{"telemetry_request": true}`.
2.  Wire up `desktop_moe_orchestrator.py` to retrieve CPU/RAM logs from WMIC/PS, read step statuses using `blueprint_orchestrator.py`, and inspect sub-agent statuses.
3.  Format output as a single JSON line on stdout.

### Phase C: JavaFX MoeGUI Dashboard Layout (Milestone M3 Implementation)
1.  **Redefine Main Layout**: Replace the `SplitPane` in `MoeApp` / `MoeController` with a `TabPane`.
2.  **Chat Tab**: Embed the original sidebar + chat history layout.
3.  **Dashboard Tab**:
    *   Design a grid-style dashboard.
    *   Create visual components: circular resource clocks, grid list for sub-agent lights, and a hierarchical list view for the 100-step blueprint.
4.  **JavaFX PythonBridge update**:
    *   Redirect server target file from `moe_server.py` to `desktop_moe_orchestrator.py`.
    *   Update `readLoop` to route `telemetry` JSON packets (which contain no `"done": true` or `"token"` fields) to a new UI updater callback, leaving standard streaming token processing intact.
5.  **Telemetry Timeline**: Set up a JavaFX `Timeline` running in `MoeController` that executes every 5 seconds to write `{"telemetry_request": true}` to the process output stream.

### Phase D: Testing and Audit Verification
1.  Launch the suite using `python tests/e2e_runner.py` in mock mode.
2.  Once validated, toggle `VIPER_E2E_MODE=live` to ensure real system calls, stdout/stdin parsing, file heartbeats, and JavaFX layout controls function correctly.
