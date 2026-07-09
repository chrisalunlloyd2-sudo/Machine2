## 2026-06-26T06:21:59Z
You are the E2E Test Implementer worker spawned by the E2E Testing Orchestrator (Conversation ID: 090ca5ab-30d6-4757-8634-69b0ea2133a1).
Your working directory is C:\Users\viper\gan-otg-db\.agents\worker_e2e_impl_3\.
Your mission is to implement the complete E2E testing suite and runner for the Moe Desktop Swarm Orchestrator project.

### Core Objectives
1. Implement exactly 38 test cases in a 4-tier hierarchy within a single Python script at `C:\Users\viper\gan-otg-db\viper-scripts\test_moe_e2e_new.py`.
2. The 38 test cases must cover the following features:
   - Feature 1: R1. 11-agent desktop MoE router (queries "show CPU load", "commit modified scripts", "modify projects schema", uses Ask_Kai or local model routing).
   - Feature 2: R2. JavaFX Swarm Dashboard (Blueprint Tracker, Swarm Orchestrator, Telemetry Visualizer showing completion board/percentage, active agents status, execution log, CPU/RAM metrics).
   - Feature 3: R3. Talon Voice Control Integration (re-target Talon paths from chris to viper, map commands to new MoE, heartbeat log hook C:\Users\viper\.kai\moe_heartbeat.txt).
3. The 4-tier test case hierarchy must consist of:
   - Tier 1: Feature Coverage (>=5 test cases per feature = >=15 cases).
   - Tier 2: Boundary & Corner (>=5 test cases per feature = >=15 cases).
   - Tier 3: Cross-Feature Combinations (>=3 cases).
   - Tier 4: Real-world Application Scenarios (>=5 cases).
   Total minimum: 38 test cases.
4. Support dual execution modes based on `os.environ.get("VIPER_E2E_MODE", "mock").lower()`:
   - "mock" mode (default): Mock all SQLite database connections, subprocesses (e.g. executing desktop_moe_orchestrator.py, git, gh), file I/O operations (reading Talon scripts, writing/reading C:\Users\viper\.kai\moe_heartbeat.txt, reading Java files in MoeGUI) using unittest.mock, patch, or in-memory SQLite tables, so that running `python C:\Users\viper\gan-otg-db\viper-scripts\test_moe_e2e_new.py` runs and passes all 38 tests immediately.
   - "live" mode: Run real commands, read real SQLite databases under `C:\Viper\databases\`, check that no references to "chris" exist in the actual Talon python/talon scripts under `C:\Users\viper\gan-otg-db\viper-scripts\talon\`, verify Java GUI controller files (`MoeController.java`, `MoeApp.java`) contain the new tabs (Blueprint Tracker, Swarm Orchestrator, Telemetry Visualizer) and controls, and verify the heartbeat file is correctly updated.
5. Create `C:\Users\viper\gan-otg-db\TEST_INFRA.md` explaining the test philosophy, runner, format, and layout.
6. Create `C:\Users\viper\gan-otg-db\TEST_READY.md` explaining the test runner command, count, and checklists.
7. Run the tests in mock mode to verify all 38 tests pass.
8. Document your progress in C:\Users\viper\gan-otg-db\.agents\worker_e2e_impl_3\progress.md and write a handoff report at C:\Users\viper\gan-otg-db\.agents\worker_e2e_impl_3\handoff.md.

### MANDATORY INTEGRITY WARNING
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Please update your progress.md heartbeat frequently and send a message when done.

## 2026-06-26T06:24:01Z
CRITICAL CORRECTION NOTICE:
The previous worker mistakenly kept the existing tests in `tests/e2e_runner.py` and `TEST_INFRA.md` which test `nmct_db_manager` and `otg_db_bridge`. This is incorrect!
You must COMPLETELY OVERWRITE `C:\Users\viper\gan-otg-db\tests\e2e_runner.py` and `C:\Users\viper\gan-otg-db\TEST_INFRA.md` to implement tests for the Moe Desktop Swarm Orchestrator project based on the design in `C:\Users\viper\gan-otg-db\.agents\explorer_e2e_design\analysis.md`.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Please perform these steps:
1. Initialize your BRIEFING.md and progress.md (update Last visited timestamps).
2. Read the E2E test design in C:\Users\viper\gan-otg-db\.agents\explorer_e2e_design\analysis.md.
3. Completely overwrite C:\Users\viper\gan-otg-db\tests\e2e_runner.py. Write the 38 test cases designed by the explorer covering:
   - Feature 1: 11-agent desktop MoE router.
   - Feature 2: JavaFX Swarm Dashboard.
   - Feature 3: Talon Voice Control Integration.
   The tests must support dual execution modes (mock vs live).
4. Run the test suite in "mock" mode first, and verify all 38 tests pass. Record the command run and output.
5. Completely overwrite C:\Users\viper\gan-otg-db\TEST_INFRA.md explaining the E2E test philosophy, the runner execution command, the test case formats, and the directory layout.
6. Write your handoff.md and send a message back to the E2E Testing Orchestrator.
