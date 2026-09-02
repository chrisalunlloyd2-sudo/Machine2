# Nothing runs forever: the N-retry doctrine

*Seed generated 2026-08-16 14:30 — deterministic, zero-LLM.*

## Concept
BLOCKED->give_up->IDLE looped forever by design (the code even admitted it). The fix: a retry budget (default 3) guards give_up; at exhaustion BLOCKED is a TRUE dead-end and the driver parks the task. The SAT verifier proved the design before implementation.

## Where it lives
`BDI_FSM_AGENT/bdi_fsm/agent.py`

## Symbols verified live
- `_retries_left`: present
- `_count_retry`: present

## Why it matters
Every system needs a bounded horizon — 'nothing runs forever' at the state-machine level.

## Practice
1. Re-read the module. 2. Find where the concept is applied. 3. Write a test
that would FAIL if the concept were removed.
