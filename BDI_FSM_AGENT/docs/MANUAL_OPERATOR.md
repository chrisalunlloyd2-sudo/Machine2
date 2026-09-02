# Operator Instruction Manual

For the human (or Aegis) operating BDI_FSM_AGENT day to day.

## Daily operations

### 1. Check the agent is alive
```bash
python3 scripts/run_heartbeat.sh
```
You should see: `hex`, `fsm_state: IDLE`, `needs`, `visible` (1-hop hex),
`pending_proposals`.

### 2. Read the needs auto-tell
The heartbeat prints `needs`. If any need is unmet, the agent is
**waiting on the system** — satisfy it:
- `resources` -> free disk / RAM
- `integrity` -> audit the NMCT vault (`nmct.audit()`)
- `comms` -> check relay / control channel
- `trust` -> review the trust ledger
- `betterment` -> ensure betterments are being logged

### 3. Review pending proposals
```bash
python3 - <<'PYINNER'
import sys; sys.path.insert(0,'.')
from bdi_fsm.control import ControlChannel
c = ControlChannel("<state_dir>/control")
for p in c.pending():
    print(p["proposal_id"], p["action"], p["target"], p["reason"])
PYINNER
```
Approve: `c.respond(id, "approve", "note")`  ·  Deny: `c.respond(id, "deny", "note")`

### 4. Run the production loop
```bash
./scripts/run_daemon.sh /path/to/repo "python3 -m pytest" 5
```

### 5. Let it run (thousand-item workflow)
Write task lists as slots. The agent resolves deterministically. Aegis
reviews the ~50% good code, corrects, and seals winners in the NMCT vault.

## Safety rules (operator)
1. Never delete files the agent added (ADD-only doctrine).
2. Never approve a proposal without reading `reason` + payload.
3. Run `python3 tests/test_all.py` before any commit.
4. One GitHub task per hour max (pacing doctrine).
5. If the agent loops (BLOCKED repeatedly), read the NMTD incidents:
   `ls <state>/nmtd_db/` — the guardrail is already written to learnings.md.
