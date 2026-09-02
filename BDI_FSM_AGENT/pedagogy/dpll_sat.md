# DPLL SAT: how the solver proves the livelock is dead

*Seed generated 2026-08-16 14:30 — deterministic, zero-LLM.*

## Concept
The DPLL solver walks a CNF formula: unit clauses force assignments, pure literals assign freely, conflicts backtrack. The classic bug we fixed: treating an already-SATISFIED clause as a unit and forcing its remaining literal — spurious UNSAT on satisfiable formulas.

## Where it lives
`sophia/sat.py`

## Symbols verified live
- `dpll`: present
- `_unit_propagate`: present

## Why it matters
The reachability verifier encodes 'can I reach the exit' as a SAT problem — the solver IS the proof machine.

## Practice
1. Re-read the module. 2. Find where the concept is applied. 3. Write a test
that would FAIL if the concept were removed.
