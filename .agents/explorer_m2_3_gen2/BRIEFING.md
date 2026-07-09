# BRIEFING — 2026-06-26T06:21:26Z

## Mission
Investigate JavaFX Swarm Dashboard and Talon Integration, mapping voice commands and recommending implementation strategies.

## 🔒 My Identity
- Archetype: Teamwork explorer
- Roles: Read-only investigation: analyze problems, synthesize findings, produce structured reports.
- Working directory: C:\Users\viper\gan-otg-db\.agents\explorer_m2_3_gen2\
- Original parent: 7c6f2ec7-310d-4d8d-8cfb-328b62a9f47e
- Milestone: M3: R2 and M4: R3

## 🔒 Key Constraints
- Read-only investigation — do NOT implement
- Code-only mode (no internet)

## Current Parent
- Conversation ID: 7c6f2ec7-310d-4d8d-8cfb-328b62a9f47e
- Updated: 2026-06-26T06:23:55Z

## Investigation State
- **Explored paths**: MoeGUI/ (MoeApp, MoeController, PythonBridge, DbStatus), viper-scripts/talon/ (viper_moe.py, viper_moe.talon, viper_model.talon, viper_model_key.py), C:\Users\viper\.talon\user\, viper-package/ (__main__.py, README.md), viper-scripts/ (blueprint_orchestrator.py, CLAUDE_GAN_100_STEPS_BLUEPRINT.md, dashboard_helper.py, heartbeat_responder.py, sovereign_loop.py, prefetch.py), tests/e2e_runner.py
- **Key findings**: JavaFX MoeGUI communicates via JSON-over-stdio; PythonBridge currently launches moe_server.py and should be updated to launch desktop_moe_orchestrator.py; periodic telemetry queries {"telemetry_request": true} can pull system load, agent status, and 100-step blueprint stats; Talon scripts need to be symlinked to C:\Users\viper\.talon\user\viper; multiple hardcoded 'chris' path references in helper scripts need retargeting to 'viper'; status hook logic should be added to Talon python scripts to write to moe_heartbeat.txt.
- **Unexplored areas**: None.

## Key Decisions Made
- Use TabPane in MoeGUI to preserve existing chat interface while adding Swarm Dashboard tab.
- Use symbolic link to map repository Talon scripts into Talon user profiles.
- Standardize all heartbeat and log paths to C:\Users\viper\.kai\.

## Artifact Index
- C:\Users\viper\gan-otg-db\.agents\explorer_m2_3_gen2\analysis.md — Detailed analysis and recommendation report.
