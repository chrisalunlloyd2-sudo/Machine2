# Install

## Dependencies

**Runtime: none.** The entire agent is **pure Python standard library** —
no numpy, no torch, no model files, no pip packages. Runs on any Python 3.8+.

Optional extras (for the demo only, not required):
- `git` — to clone and for the git-based examples
- `pytest` — if you prefer pytest over the bundled self-test runner

Verified environments:
- Alpine Linux sandbox (proot) — Python 3.12 — **58/58 tests green**
- Termux (Android) — Python 3.11+ — compatible (pure stdlib)
- Desktop Linux/macOS/Windows — Python 3.8+ — compatible

## Install

```bash
git clone https://github.com/chrisalunlloyd2-sudo/BDI_FSM_AGENT.git
cd BDI_FSM_AGENT
python3 tests/test_all.py          # expect: 58 passed, 0 failed
```

No `pip install` needed. No virtualenv needed. No model download.

## Verify install

```bash
python3 -c "import sys; sys.path.insert(0,'.'); from bdi_fsm.agent import BDIFSMAgent; import tempfile; a=BDIFSMAgent(tempfile.mkdtemp()); print('agent OK', a.heartbeat()['fsm_state'])"
# expect: agent OK IDLE
```

## Running from anywhere

```bash
export PYTHONPATH=/path/to/BDI_FSM_AGENT
python3 -m bdi_fsm.agent --heartbeat
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: bdi_fsm` | run from repo root or set `PYTHONPATH` |
| tests fail with `resource` import error | sandbox without `resource` — cosmetic; RLIMIT degrades gracefully |
| port/file locks | FOW claims auto-expire after TTL (default 480s) |
