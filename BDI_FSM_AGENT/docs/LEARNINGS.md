# AGENT LEARNINGS LEDGER

Deterministic fleet learnings recorded by Aegis (heartbeat betterment).
ADD-only — append, never delete entries.

## 2026-08-10 — matrixwince origin be03eb07 is known-bad (do not apply)

- **Issue**: repo_scanner re-evaluates matrixwince origin `be03eb07` every
  15 min and rejects it with the same three warnings, burning scan cycles.
- **Warnings**:
  1. 718 deletions in the diff — NOT doctrine-pure (ADD-only violated upstream).
  2. py_compile FAIL on archives: `code_evolver.py:40` (unterminated f-string),
     `orchestrator.py:20` (unterminated f-string), `matrix_operations.py:11`
     (invalid syntax — stray ``` in source).
  3. Stale port `11434` in `apk-compiler/wince-project/assets/commands.json`
     (GGUF server now lives on :5000, never 11434).
- **Action taken**: scanner correctly returned `not_better`; no apply, no push.
- **Future handling**: origin shas matching these warnings should be recorded
  in never_try_twice so the scanner skips re-evaluation (same doctrine as
  patch/command failures). Root fix lives upstream in MatrixWinCE repo —
  the broken archives + stale port need cleanup there, not in a local merge.
