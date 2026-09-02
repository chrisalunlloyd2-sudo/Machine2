# Safety & Governance

**This is a selling point.** BDI_FSM_AGENT is engineered so an autonomous
agent cannot damage the system, repeat mistakes, or act without oversight.

## 1. Human veto required for destructive actions

- Every **external** action (push, merge, write outside workspace, delete,
  install, network egress) flows through the **Aegis Control Channel**.
- The agent **proposes**; a controller (local LLM or human in PowerShell)
  must be **active and satisfied** before anything executes.
- **No controller = no action.** The agent stays in `WAIT_AEGIS` and
  reports the unmet controller need.
- Human can veto any proposal: `ControlChannel.respond(id, "deny", note)`.
- Veto is absolute and immediate — the FSM has no path around `DENIED`.

## 2. ADD-only mutation policy

- Agents **ADD, never DELETE** (Chris doctrine, 2026-08-08).
- The approval gate (`add_only_gate.py`) blocks any diff containing file
  deletions — `git diff --diff-filter=D --name-only` counts, not lines.
- A blocked diff is logged to the game ledger and flagged for human review.
- No agent has delete permission. Deletion requires human/Aegis veto.

## 3. Tamper audit via NMCT

- Every canonical code commit is **SHA-256 sealed** in the NMCT vault.
- `NMCT.audit()` verifies every entry: `sealed_valid` vs `tampered`.
- Any vault entry whose stored hash ≠ recomputed hash is flagged tampered.
- The agent refuses to use tampered entries — integrity is a **safety
  need** in the Maslow hierarchy (unmet integrity → agent blocks).

## 4. Never-mistakes-twice via NMTD

- Every failure records a **fingerprinted incident** (SHA-256 of the error).
- The same error signature can never be retried blind — `NMTD.check()`
  is consulted before attempting work.
- Each incident auto-extracts a **guardrail rule** into `learnings.md`
  (negative-constraint propagation to all future runs).
- Compounding determinism: the system literally cannot make the same
  mistake twice.

## 5. Defense in depth (the full gate stack)

```
[ FOW claim ]          — no duplicate execution, spatial fog-of-war
[ NMTD gate ]          — never repeat a known failure
[ Rule gate ]          — learnings.md negative constraints
[ Hardened sandbox ]   — CoW overlay, RLIMIT, timeout→124, no host mutation
[ NMCT seal ]          — tamper-evident canonical code
[ Controller gate ]    — local LLM or human must be active
[ Aegis control ]      — propose → approve/deny → execute
[ ADD-only gate ]      — deletions blocked at the repo boundary
```

## 6. No cloud. Ever.

- **Zero cloud LLMs.** All inference is LOCAL (llama-server :5001, gguf
  :5000). No OpenRouter, no external API endpoints.
- Controller discovery only probes `localhost` — it cannot reach the
  internet by construction.
- The entire agent core is pure stdlib, fully offline-capable.
