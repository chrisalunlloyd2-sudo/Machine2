# Original User Request

## Initial Request — 2026-06-25T20:25:54-06:00

You are the Implementation Track Sub-orchestrator spawned by the top-level Project Orchestrator (Conversation ID: 2f44f8c0-f68b-4cb6-adb6-02b6e727791b).
Your working directory is C:\Users\viper\gan-otg-db\.agents\sub_orch_impl\.
Your mission is to coordinate the implementation of the Moe Desktop Swarm Orchestrator, JavaFX Swarm Dashboard, and Talon Voice Control Integration.
Follow the Project Pattern guidelines:
1. Create C:\Users\viper\gan-otg-db\.agents\sub_orch_impl\SCOPE.md and C:\Users\viper\gan-otg-db\.agents\sub_orch_impl\progress.md.
2. Read the requirements in C:\Users\viper\gan-otg-db\.agents\ORIGINAL_REQUEST.md.
3. Coordinate the implementation of the following milestones:
   - Milestone M2: R1 (desktop_moe_orchestrator.py) - Implement the structured dispatcher that routes queries to the 11 specialist agents. Ensure "show CPU load", "commit modified scripts", and "modify projects schema" route correctly. Schema migration agent must check SOP-000 first. Use Ask_Kai or local model routing to select the correct agent.
   - Milestone M3: R2 (JavaFX Swarm Dashboard) - Add the JavaFX visual controller tab in MoeGUI that interfaces with desktop_moe_orchestrator.py via viper-package (JSON stream over stdin/stdout) to show agent status, telemetry, and 100-step blueprint completion.
   - Milestone M4: R3 (Talon Integration) - Re-target Talon paths from chris to viper, map commands to MoE, and add hook to write status updates to C:\Users\viper\.kai\moe_heartbeat.txt.
   - Milestone M5: Final verification - Pass 100% of the E2E tests (poll for TEST_READY.md at project root) and perform adversarial coverage hardening (Tier 5).
Your parent is 2f44f8c0-f68b-4cb6-adb6-02b6e727791b.
Please update your progress.md heartbeat frequently and send a message when done.
