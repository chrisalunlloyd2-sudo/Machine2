# Prune to the knee: the asymptotic dream

*Seed generated 2026-08-16 14:30 — deterministic, zero-LLM.*

## Concept
Effectiveness-vs-retention curves have a knee: past it, the tail is redundant. Kneedle finds the knee; we prune to it and ARCHIVE never delete. Real corpus: 40.5% retention kept 67.2% of value.

## Where it lives
`BDI_FSM_AGENT/bdi_fsm/asymptotic.py`

## Symbols verified live
- `find_knee`: present
- `prune_to_knee`: present

## Why it matters
Memory must stay bounded while information survives — the steady-state doctrine.

## Practice
1. Re-read the module. 2. Find where the concept is applied. 3. Write a test
that would FAIL if the concept were removed.
