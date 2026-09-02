# Steps & Phases

The BDI_FSM_AGENT is built and grown in phases. Each phase is FOW-placed
(a hex claim, see [FOW.md](FOW.md)) and gated by the deterministic
self-test suite. **No phase uses an LLM or SLM.**

## Phase 0 — Foundation (DONE)
- Repo creation `chrisalunlloyd2-sudo/BDI_FSM_AGENT`
- Package skeleton, LICENSE, .gitignore
- **FOW hex:** (0,0) `bdi-fsm-agent` — tower root

## Phase 1 — Core engine (DONE)
- Blackboard (BB1), FSM, BDI engine, Subsumption arbiter
- **FOW hex:** (1,0) `blackboard-core`

## Phase 2 — Memory & verification (DONE)
- ToK Memory Harness, learnings.md, recipe book
- Wrapped NMCT vault (seal/verify/audit)
- Wrapped NMTD incident DB (never-make-mistakes-twice)
- **FOW hex:** (0,1) `memory-harness`

## Phase 3 — Sandbox & foundry (DONE)
- Hardened CoW sandbox (RLIMIT, timeout→124, process-tree kill)
- Brute Genetic Foundry (actor-critic + Non-TLStop pruner)
- **FOW hex:** (-1,0) `hardened-sandbox`

## Phase 4 — Agent & control (DONE)
- Assembled `BDIFSMAgent` (FSM+BDI+blackboard+memory+tower)
- Aegis Control Channel (propose/approve/deny)
- Maslow needs hierarchy + auto-tell
- **FOW hex:** (0,-1) `agent-core`

## Phase 5 — Production daemon (DONE)
- ProductionDaemon live workspace loop (AST scan → resolve → verify → commit)
- ASTInspector slot finder, NonTLStopPruner
- Heartbeat betterment module
- **FOW hex:** (2,0) `production-daemon`

## Phase 6 — Self-test suite (DONE)
- `tests/test_all.py` — 58 deterministic checks, zero LLM
- **FOW hex:** (2,1) `self-test-gate`

## Phase 7 — Deployment (IN PROGRESS)
- Push to GitHub, gitpage, heartbeat cron wiring
- Cancel LLM heartbeats → one betterment per heartbeat
- **FOW hex:** (1,1) `deployment`

## Phase 8 — Fleet integration (NEXT)
- Wire into the 4D HEX GAME as a player
- Consume task_pool.json thousands-of-items lists
- Aegis review loop: let the bot go, swoop in, correct the ~50% good code
- **FOW hex:** (3,0) `fleet-integration`

## Phase 9 — Perfection loop (CONTINUOUS)
- One betterment per heartbeat from logs + Aegis judgment
- Maslow-driven self-sufficiency (system satisfies unmet needs)
- Compounding determinism: recipe/vault hit rate → 100%
- **FOW hex:** rotates across (3,1) (1,2) (2,-1) as betterments land

## Growth doctrine
- **ADD only, never DELETE**
- 1 real GitHub task per hour (pacing doctrine)
- Every change passes `tests/test_all.py` before commit
- Every external action requires Aegis approval (control channel)
