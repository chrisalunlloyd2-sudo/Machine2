# Gist unification: so we all know what we are doing

*Seed generated 2026-08-16 14:30 — deterministic, zero-LLM.*

## Concept
Every agent appends its cycle status + successful workflow LOGITS (deciban bans) to one shared secret gist. Ban = what is right; logit = the record; gist = the shared memory.

## Where it lives
`Aegis_Unified/fleet.py`

## Symbols verified live
- `post_status`: present
- `log_workflow`: present

## Why it matters
A fleet that shares its logits learns which workflows score high — cross-machine learning with zero LLM.

## Practice
1. Re-read the module. 2. Find where the concept is applied. 3. Write a test
that would FAIL if the concept were removed.
