# Build Log

Chronological record of how BDI_FSM_AGENT was built (2026-08-10),
so every step is reproducible and auditable.

## Step 1 — Repo creation
```bash
curl -X POST https://api.github.com/user/repos \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -d '{"name":"BDI_FSM_AGENT","private":true,"auto_init":true}'
# → chrisalunlloyd2-sudo/BDI_FSM_AGENT (private)
```

## Step 2 — Source spec
Built from the self-sent email series (2026-08-10, UIDs 82389–82397):
- "ultimate non-LLM tool-calling super agent" (Subsumption+BB1+BDI+FSM)
- ToK Memory Harness (learnings/recipe/NMCT/NMTD)
- Kernel Isolation & Hardened Execution Engine (CoW, RLIMIT, exit 124)
- Production Deployment & Live Workspace Loop (ASTInspector + daemon)
- Non-TLStop Learning Pruning Engine (Genetic Actor-Critic)

## Step 3 — Core modules written
```bash
mkdir -p bdi_fsm heartbeat tests docs scripts examples
# bdi_fsm/blackboard.py fsm.py bdi.py foundry.py hardened.py memory.py
# bdi_fsm/nmct.py nmtd.py toc_tok.py maslow.py fow.py control.py
# bdi_fsm/agent.py daemon.py
# heartbeat/betterment.py
# tests/test_all.py
```

## Step 4 — Bugs found & fixed
1. **`toc_tok.py` attribute/method shadow** — `self.path` (attribute)
   shadowed the `path()` method → `TypeError: 'str' object is not callable`.
   Fix: renamed attribute to `self.store_path`, method to `resolve_path()`.
2. **`agent.py` hex type mismatch** — heartbeat returned tuple `(3,0)`,
   test expected list `[3,0]`. Fix: `list(self.hex)`.

## Step 5 — Self-tests
```bash
python3 tests/test_all.py
# RESULT: 58 passed, 0 failed  (zero LLM/SLM inference)
```

## Step 6 — Docs
README, ARCHITECTURE, PHASES, INSTALL, RUNBOOK, MASLOW, FOW, BUILD_LOG,
MANUAL_OPERATOR, MANUAL_DEVELOPER.

## Step 7 — Deployment (this step)
```bash
git add -A && git commit -m "..." && git push origin main
```

## Known limitations
- `resource.RLIMIT_AS` requires POSIX; degrades gracefully elsewhere
- `os.closerange` best-effort on exotic platforms
- FOW is advisory across separate sandbox sessions (file-lock based)
