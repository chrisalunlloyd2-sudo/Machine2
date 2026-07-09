# BRIEFING — 2026-06-27T02:22:00Z

## Mission
Implement the desktop swarm orchestrator (desktop_moe_orchestrator.py) with 11 specialist agents, compliant database, systems, policy, and routing logic.

## 🔒 My Identity
- Archetype: Worker
- Roles: implementer, qa, specialist
- Working directory: C:\Users\viper\gan-otg-db\.agents\worker_m2_gen2_retry2\
- Original parent: 7c6f2ec7-310d-4d8d-8cfb-328b62a9f47e
- Milestone: M2: R1

## 🔒 Key Constraints
- CODE_ONLY network mode: no external HTTP clients except mock/local.
- DO NOT CHEAT: no hardcoded expected outputs, maintain real behavior.
- Clean JSON stream over stdin/stdout.

## Current Parent
- Conversation ID: 7c6f2ec7-310d-4d8d-8cfb-328b62a9f47e
- Updated: 2026-06-27T02:22:00Z

## Task Summary
- **What to build**: Swarm orchestrator desktop_moe_orchestrator.py routing to 11 specialist agents (including schema_migration_agent with SOP check and backups, database_query_agent as read-only, systems_info_agent querying CPU/RAM, policy_enforcement_agent).
- **Success criteria**: Passes E2E tests, satisfies specific query routes, handles telemetry_request.
- **Interface contracts**: desktop_moe_orchestrator.py, stdout JSON stream.

## Change Tracker
- **Files modified**: None
- **Build status**: TBD
- **Pending issues**: TBD

## Quality Status
- **Build/test result**: TBD
- **Lint status**: TBD
- **Tests added/modified**: TBD

## Loaded Skills
- **Source**: None
- **Local copy**: None
- **Core methodology**: None

## Key Decisions Made
- None yet

## Artifact Index
- None
