# Runbook — Instruction Manual

## 1. The agent lifecycle

```
IDLE → EVALUATE → SYNTHESIZE → VERIFY → COMMIT → IDLE
                          ↘ BLOCKED ↗   ↘ WAIT_AEGIS → (approved) → COMMIT
```

## 2. Commands

### Self-test (deterministic, zero LLM)
```bash
python3 tests/test_all.py
```

### Heartbeat pass (needs + orientation + FOW)
```bash
python3 -m bdi_fsm.agent --heartbeat
# prints: hex, fsm_state, needs_status, visible nodes, pending proposals
```

### Resolve one slot (full ToK lifecycle)
```python
from bdi_fsm.agent import BDIFSMAgent
a = BDIFSMAgent("/tmp/bdi_state")
r = a.resolve_slot(
    "calc.py", "test",
    candidate_generator=lambda: ["def calc(x):\n    return x*2",
                                  "def calc(x):\n    return x+1"],
    test_fn=lambda c: "x*2" in c,
    require_approval=True)          # True = wait for Aegis
print(r)                            # {'state': 'WAIT_AEGIS', 'proposal_id': ...}
```

### Aegis approves / denies
```python
from bdi_fsm.control import ControlChannel
c = ControlChannel("/tmp/bdi_state/control")
c.respond("<proposal_id>", "approve", "looks good")
```

### Production daemon (live workspace loop)
```bash
python3 -m bdi_fsm.daemon --workspace /path/to/repo --test "python3 -m pytest" --max 3
# scans repo for stubs (pass / NotImplementedError), resolves via agent,
# verifies in CoW sandbox, commits green code, NMTD-logs failures
```

### Heartbeat betterment (replaces ALL LLM heartbeats)
```bash
python3 heartbeat/betterment.py
# picks ONE improvement from logs + state, records to betterments.jsonl
```

### Maslow needs auto-tell
```bash
python3 -c "import sys; sys.path.insert(0,'.'); from bdi_fsm.agent import BDIFSMAgent; import tempfile; a=BDIFSMAgent(tempfile.mkdtemp()); s=a.heartbeat()['needs']; print(a.maslow.unmet_summary())"
# e.g. "UNMET NEEDS — auto-tell to system:\n  [physiological] resources: ..."
```

## 3. The thousand-item-list workflow (Chris doctrine)

1. Write a task list (any length — hundreds or thousands of items).
2. Feed it to the agent as slots (each task = a slot to resolve).
3. The agent runs deterministically: recipe → NMCT → foundry → sandbox.
4. ~50% of generated code is good; Aegis reviews, corrects the rest.
5. The corrected winners get sealed in the NMCT vault → next time the
   same slot resolves from the vault instantly (compounding determinism).

## 4. Never-make-mistakes-twice

Every failure records an NMTD incident (SHA-256 fingerprinted). The same
error signature can never be retried blind — `NMTD.check()` is consulted
before attempting work, and a guardrail is written to learnings.md.

## 5. FOW discipline

- Every task claims a hex before running (`FOW.claim`)
- Stale claims (> TTL) auto-release
- Duplicate execution across cron/manual/restart is impossible
- See [FOW.md](FOW.md)

## 6. Aegis control

- Agent proposes external actions → `proposals.jsonl`
- Aegis responds → `responses.jsonl`
- Nothing external happens without approval
- Heartbeat betterments are the ONLY autonomous external cadence (1/heartbeat)
