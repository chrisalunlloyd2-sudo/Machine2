# BRIEFING — 2026-06-26T19:50:08-06:00

## Mission
Verify the build and test results of Moe Swarm Orchestrator and MoeGUI.

## 🔒 My Identity
- Archetype: teamwork_preview_orchestrator
- Roles: orchestrator, user_liaison, human_reporter, successor
- Working directory: C:\Users\viper\gan-otg-db\.agents\qa_orchestrator
- Original parent: main agent
- Original parent conversation ID: 2c2a5c89-126a-4c51-b21c-d74220b8124c

## 🔒 My Workflow
- Pattern: Project
- Scope document: C:\Users\viper\gan-otg-db\.agents\qa_orchestrator\SCOPE.md
1. **Decompose**: Decompose the build and verification tasks into subtasks.
2. **Dispatch & Execute** (pick ONE):
   - **Direct (iteration loop)**: Dispatch tasks to workers, reviewers, and auditors.
3. **On failure**:
   - Retry: nudge stuck agent or re-send task
   - Replace: spawn fresh agent with partial progress
   - Skip: proceed without (only if non-critical)
   - Redistribute: split stuck agent's remaining work
   - Redesign: re-partition decomposition
   - Escalate: report to parent (sub-orchestrators only, last resort)
4. **Succession**: Self-succeed at 16 spawns, write handoff.md, spawn successor.
- **Work items**:
  1. Compile/package MoeGUI with mvn clean package [pending]
  2. Execute e2e_runner.py [pending]
- **Current phase**: 1
- **Current focus**: Planning and dispatching compilation and E2E test run.

## 🔒 Key Constraints
- NEVER write, modify, or create source code files directly.
- NEVER run build/test commands yourself — require workers to do so.
- You MAY use file-editing tools ONLY for metadata/state files (.md) in your .agents/ folder.
- DO NOT CHEAT. All implementations must be genuine.
- Provide full stdout and stderr output in handoff report.
- Forensic Auditor verification will gate this turn.

## Current Parent
- Conversation ID: 2c2a5c89-126a-4c51-b21c-d74220b8124c
- Updated: not yet

## Key Decisions Made
- Dispatch mvn clean package and python tests/e2e_runner.py to teamwork_preview_worker.
- Spawn teamwork_preview_auditor to run forensics.

## Team Roster
| Agent | Type | Work Item | Status | Conv ID |
|-------|------|-----------|--------|---------|
| QA Worker (gen1) | teamwork_preview_worker | Compile MoeGUI & run E2E tests | failed | 25bb4077-676e-48d5-84e7-7d2dbe26c4af |
| QA Worker (gen2) | teamwork_preview_worker | Compile MoeGUI & run E2E tests | pending | 5b621373-80dc-493e-bff5-eddf9b83bab8 |

## Succession Status
- Succession required: no
- Spawn count: 2 / 16
- Pending subagents: 5b621373-80dc-493e-bff5-eddf9b83bab8
- Predecessor: none
- Successor: not yet spawned

## Active Timers
- Heartbeat cron: e68023e6-d420-43da-a858-c4e40510e8a5/task-29
- Safety timer: none

## Artifact Index
- C:\Users\viper\gan-otg-db\.agents\qa_orchestrator\BRIEFING.md — Working memory
- C:\Users\viper\gan-otg-db\.agents\qa_orchestrator\progress.md — Heartbeat and step tracking
- C:\Users\viper\gan-otg-db\.agents\qa_orchestrator\SCOPE.md — Scope document
