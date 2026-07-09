## 2026-06-26T02:26:31Z
Investigate the requirements for implementation of the Moe Desktop Swarm Orchestrator, JavaFX Swarm Dashboard, and Talon voice control integration.
Specifically:
1. Locate where `desktop_moe_orchestrator.py` should be created. Examine existing Python agents in `ArchivalMoe/agents/` and see how they map to the 11 specialist agents. Check if any mock/scaffold implementations exist for the 11 specialist agents.
2. Locate SOP-000 or guidelines on checking it for the schema migration agent.
3. Locate `Ask_Kai` or model routing utilities in the codebase.
4. Examine the JavaFX project under `MoeGUI/`. Inspect `MoeApp.java`, `MoeController.java`, and `PythonBridge.java`. Determine how the new Blueprint Tracker and Swarm Orchestrator tabs, telemetry visualizer (CPU/RAM metrics), and blueprint completion board should be added. How does JavaFX communicate with python? Check the stdin/stdout JSON format.
5. Examine files in `viper-scripts/talon/`. Find all instances of `chris` (directories or profile names) that need to be retargeted to `viper`. Find where voice commands and heartbeat logic are/should be.
6. Write your findings to C:\Users\viper\gan-otg-db\.agents\explorer_m2\handoff.md. Be detailed and specify file paths, code snippets, and exact implementation strategies for each milestone.
