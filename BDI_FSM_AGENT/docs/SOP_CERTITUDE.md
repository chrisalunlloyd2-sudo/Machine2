# SOP-010: 100% CERTITUDE DOCTRINE

*Chris directive 2026-08-11 — applies to every step of every task, including
Aegis's own actions.*

## The Rule

> Every step asks: **"is this going to work 100%?"**
> If the answer is not a guaranteed GO, **step back, assess, redo — until 100%.**

## Mechanics (deterministic, zero LLM)

1. **Binary gate** — a step is `GO` (confidence 1.0) or `NO-GO` (0.0). There is
   no "probably." The gate passes only when *every* check passes.
2. **Step-back** — on NO-GO: restore context, assess the failing checks, record
   in never-try-twice (NMTD), redo with a variant. Max 3 redoes, then course-change.
3. **Own-output checks** — each step's checks validate **that step's own output**,
   never a future fact (a future fact does not exist yet — checking it causes
   false redo loops).
4. **Long-horizon** — string blocks of logic serially (cellular chain doctrine).
   After **every** output, integrate it back into the blackboard and
   re-evaluate the remaining plan. Course change is the norm, not the exception.
5. **Precondition drift = course-change trigger** — if an integrated output makes
   a later block's precondition unsatisfiable, drop / re-order / re-abduct.
6. **ADD-only** — never delete. Journal every step-back and its fix (learning).

## Implementation

- `bdi_fsm/certainty.py` — `CertaintyGate.assess()` (binary verdicts) +
  `step_back()` (NMTD + redo variant). Verifiers: compile, test_run, file_exists,
  fact, dependency, constraint, not_blocked, not_empty.
- `bdi_fsm/horizon.py` — `Horizon.run()` (block stringing, 100% gate per block,
  integrate-on-output, course change) + `HorizonBlock` (run/checks/precondition/effect).
- `BDIFSMAgent.step_assess()` and `BDIFSMAgent.run_horizon()` expose both to the agent.

## Tests

`tests/test_certainty.py`, `tests/test_horizon.py` — clean chain DONE, flaky block
stepped-back+redone, exhausted redo → course change, precondition drift detected.
