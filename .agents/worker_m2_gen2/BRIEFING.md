# BRIEFING — 2026-06-26T06:28:00Z

## Mission
Implement desktop_moe_orchestrator.py routing logic, specialist agents, GUI telemetry JSON interface, local/Ask_Kai model routing tiers, database/SOP checking logic, and verify it all.

## 🔒 My Identity
- Archetype: worker
- Roles: implementer, qa, specialist
- Working directory: C:\Users\viper\gan-otg-db\.agents\worker_m2_gen2\
- Original parent: 7c6f2ec7-310d-4d8d-8cfb-328b62a9f47e
- Milestone: M2: R1

## 🔒 Key Constraints
- CODE_ONLY network mode: no external HTTP/curl/wget (except localhost model API or ask_kai.py)
- Route queries to 11 specialist agents
- Block non-read-only queries in database_query_agent
- Implement system CPU/RAM load in systems_info_agent
- Implement policy_enforcement_agent for SOP-000 to SOP-003 and DePIN gating
- Schema migration agent must check SOP-000 and backup to C:\Viper\backups\databases
- Interface with MoeGUI via JSON streams on stdin/stdout, telemetry_request handling
- Handoff report in worker_m2_gen2\handoff.md

## Current Parent
- Conversation ID: 7c6f2ec7-310d-4d8d-8cfb-328b62a9f47e
- Updated: not yet

## Task Summary
- **What to build**: Desktop swarm orchestrator (desktop_moe_orchestrator.py) with specialist routing.
- **Success criteria**: Correct routing (deterministic, local, Ask_Kai), read-only checks, backup checks, SOP checking, telemetry responses, passes all tests.
- **Interface contracts**: desktop_moe_orchestrator.py routing, JSON stdin/stdout.
- **Code layout**: Root directory (C:\Users\viper\gan-otg-db\desktop_moe_orchestrator.py).

## Change Tracker
- **Files modified**: None
- **Build status**: Untested
- **Pending issues**: None

## Quality Status
- **Build/test result**: Untested
- **Lint status**: Untested
- **Tests added/modified**: None

## Loaded Skills
- **Source**: None
- **Local copy**: None
- **Core methodology**: None

## Key Decisions Made
- Will check existing project for any files related to SOPs, Ask_Kai, or other agents.

## Artifact Index
- C:\Users\viper\gan-otg-db\desktop_moe_orchestrator.py — Main orchestrator file.
