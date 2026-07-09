# Handoff Report: JavaFX Swarm Dashboard & Talon Integration Exploration

This handoff report summarizes the findings from the discovery phase of Milestone M3: R2 (JavaFX Swarm Dashboard) and Milestone M4: R3 (Talon Integration).

---

## 1. Observation

*   **JavaFX Files Location**:
    The main Java GUI workspace files are located under `C:\Users\viper\gan-otg-db\MoeGUI\src\main\java\com\viper\moe\`:
    *   `MoeApp.java` (line 16: `MoeController controller = new MoeController();`, line 30: `controller.startLiveUpdates();`)
    *   `MoeController.java` (line 26: `private final PythonBridge bridge = new PythonBridge();`, line 288: `boolean started = bridge.start();`)
    *   `PythonBridge.java` (line 19: `private static final String MOE_SERVER = "C:\\Viper\\projects\\ArchivalMoe\\moe_server.py";`)
    *   `DbStatus.java` (line 12: `static final String PROJ_DB = "C:\\Viper\\databases\\projects\\projects.db";`)

*   **Talon Mappings Location**:
    Talon configuration files are located under:
    *   `C:\Users\viper\gan-otg-db\viper-scripts\talon\viper\viper_moe.py`
    *   `C:\Users\viper\gan-otg-db\viper-scripts\talon\viper\viper_moe.talon`

*   **Active Talon User Profile**:
    Running `Test-Path C:\Users\viper\.talon\user` returned `True`. Running `Test-Path C:\Users\viper\.talon\user\viper` returned `False` (meaning the repository Talon scripts are currently unlinked/inactive).

*   **Hardcoded 'chris' Paths**:
    Grep search identified several instances of `C:\Users\chris` across `viper-scripts`:
    *   `viper-scripts/moe_mcp_server.py` (line 120): `p = r"C:\Users\chris\.kai\moe_heartbeat.txt"`
    *   `viper-scripts/prefetch.py` (line 20): `HEARTBEAT = r"C:\Users\chris\.kai\moe_heartbeat.txt"`
    *   `viper-scripts/heartbeat_responder.py` (line 22-23): `HEARTBEAT = r"C:\Users\chris\.kai\moe_heartbeat.txt"`, `HBLOG = r"C:\Users\chris\.kai\heartbeat.log"`
    *   `viper-scripts/moe-report.py` (line 20): `DESKTOP = r"C:\Users\chris\Desktop"`
    *   `viper-scripts/viper_llm_server.py` (lines 174-180): LMStudio paths under `C:\Users\chris\.lmstudio` and `C:\Users\chris\OneDrive\Desktop\...`
    *   `viper-scripts/wrappers.py` (line 20): `OLLAMA = r"C:\Users\chris\.lmstudio\..."`

*   **100-Step Blueprint Parser**:
    `viper-scripts/blueprint_orchestrator.py` exists and contains:
    *   Line 26: `def parse_blueprint():`
    *   Line 77: `def evaluate_blueprint_status():`

---

## 2. Logic Chain

1.  **Redirection to Orchestrator**: Since `PythonBridge.java` currently spawns `moe_server.py` directly, redirecting this target to `desktop_moe_orchestrator.py` is the baseline requirement to route visual controller requests to the new 11-agent dispatcher.
2.  **Telemetry Integration**: By leveraging a JavaFX `Timeline` to write `{"telemetry_request": true}` JSON queries over stdin and updating `PythonBridge.readLoop` to handle the incoming telemetry message (e.g. CPU/RAM and blueprint stats), the dashboard can update UI elements in real-time.
3.  **Talon Profile Linking**: Because Talon loads configurations from the active user directory `C:\Users\viper\.talon\user\`, creating a symbolic link to `viper-scripts/talon/viper/` will register and load the customized voice mappings.
4.  **Heartbeat Writing**: The E2E tests check for updates to `C:\Users\viper\.kai\moe_heartbeat.txt`. Adding a hook inside the Talon python script (`viper_moe.py`) to append log lines during voice action triggers will satisfy this verification condition.
5.  **Refactoring Chris Path References**: Multiple legacy scripts reference the `chris` path for heartbeats, models, and desktop directories. Swapping them to `viper` is mandatory for these services to run under the Machine 2 environment.

---

## 3. Caveats

*   **Talon Restart**: Talon must be manually restarted or reloaded after establishing the symlink for the new profile to take effect.
*   **Orchestrator Backend**: The implementation of `desktop_moe_orchestrator.py` is being handled under Milestone M2; our dashboard design assumes the orchestrator matches the communication interface contracts defined in `PROJECT.md` and `SCOPE.md`.

---

## 4. Conclusion

The JavaFX dashboard and Talon integration can be implemented by:
1.  Symlinking the Talon profile and adding status hook logic in `viper_moe.py` to write to `moe_heartbeat.txt`.
2.  Redesigning `MoeController.java` with a `TabPane`, adding a Swarm Dashboard tab to monitor agent status, CPU/RAM telemetry, and the 100-step blueprint completion board (queried via standard stdin/stdout JSON lines).
3.  Sweeping and refactoring the hardcoded `chris` path references to `viper`.

---

## 5. Verification Method

1.  **Code Review**: Verify that `MoeController.java` contains the necessary JavaFX controls (`TabPane`, `ProgressBar`, `GridPane`) and `PythonBridge.java` points to `desktop_moe_orchestrator.py`.
2.  **Symlink Check**: Run `Test-Path C:\Users\viper\.talon\user\viper` to verify that the profile symlink exists.
3.  **Heartbeat Verification**: Trigger a Talon command (or execute `python viper_moe.py` directly) and inspect `C:\Users\viper\.kai\moe_heartbeat.txt` to confirm that the hook logs the action.
4.  **E2E Tests**: Run the E2E verification test suite:
    ```powershell
    python tests/e2e_runner.py
    ```
    Verify that mock tests pass successfully.

---

## 6. Remaining Work

1.  Create the symlink from `C:\Users\viper\gan-otg-db\viper-scripts\talon\viper` to `C:\Users\viper\.talon\user\viper`.
2.  Clean up hardcoded `chris` paths in `moe_mcp_server.py`, `prefetch.py`, `heartbeat_responder.py`, `moe-report.py`, `viper_llm_server.py`, and `wrappers.py`.
3.  Implement the hook logic in `viper_moe.py` to write status updates to `C:\Users\viper\.kai\moe_heartbeat.txt`.
4.  Modify `MoeController.java` and `PythonBridge.java` to support the Swarm Dashboard tab, periodic telemetry query loop, and agent status grid.
