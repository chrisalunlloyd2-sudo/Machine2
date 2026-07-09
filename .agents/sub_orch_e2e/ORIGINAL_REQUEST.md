# Original User Request

## Initial Request — 2026-06-25T20:25:51-06:00

You are the E2E Testing Orchestrator spawned by the top-level Project Orchestrator (Conversation ID: 2f44f8c0-f68b-4cb6-adb6-02b6e727791b).
Your working directory is C:\Users\viper\gan-otg-db\.agents\sub_orch_e2e\.
Your mission is to design and implement the E2E testing suite for the Moe Desktop Swarm Orchestrator project.
Follow the E2E Testing Track guidelines in the Project Pattern:
1. Create C:\Users\viper\gan-otg-db\.agents\sub_orch_e2e\SCOPE.md and C:\Users\viper\gan-otg-db\.agents\sub_orch_e2e\progress.md.
2. Read the requirements in C:\Users\viper\gan-otg-db\.agents\ORIGINAL_REQUEST.md.
3. Design a comprehensive opaque-box test suite based on the features:
   - Feature 1: R1. 11-agent desktop MoE router (queries "show CPU load", "commit modified scripts", "modify projects schema", uses Ask_Kai or local model routing).
   - Feature 2: R2. JavaFX Swarm Dashboard (Blueprint Tracker, Swarm Orchestrator, Telemetry Visualizer showing completion board/percentage, active agents status, execution log, CPU/RAM metrics).
   - Feature 3: R3. Talon Voice Control Integration (re-target Talon paths from chris to viper, map commands to new MoE, heartbeat log hook C:\Users\viper\.kai\moe_heartbeat.txt).
4. Implement a 4-tier test case hierarchy containing:
   - Tier 1: Feature Coverage (>=5 test cases per feature = >=15 cases).
   - Tier 2: Boundary & Corner (>=5 test cases per feature = >=15 cases).
   - Tier 3: Cross-Feature Combinations (>=3 cases).
   - Tier 4: Real-world Application Scenarios (>=5 cases).
   Total minimum: 38 test cases.
5. Create `TEST_INFRA.md` at project root explaining test philosophy, runner, format, and layout.
6. Once the test suite is implemented and ready, write `TEST_READY.md` at project root containing the test runner command, count, and checklists.
Your parent is 2f44f8c0-f68b-4cb6-adb6-02b6e727791b.
Please update your progress.md heartbeat frequently and send a message when done.
