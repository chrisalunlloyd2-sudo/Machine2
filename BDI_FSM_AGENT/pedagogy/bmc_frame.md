# BMC: the frame constraint that killed teleportation

*Seed generated 2026-08-16 14:30 — deterministic, zero-LLM.*

## Concept
Naive bounded-model-checking forced every enabled edge to fire AND let the goal pop into existence without a predecessor. The frame constraint fixes both: a state at t+1 must be reachable from t, exactly-one choice per time-step.

## Where it lives
`sophia/reach.py`

## Symbols verified live
- `bounded_path_formula`: present
- `path_exists`: present

## Why it matters
Sound reachability = the difference between 'looks right' and provably right.

## Practice
1. Re-read the module. 2. Find where the concept is applied. 3. Write a test
that would FAIL if the concept were removed.
