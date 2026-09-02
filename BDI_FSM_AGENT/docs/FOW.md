# FOW Placement — Fog-of-War hex grid

Every BDI_FSM_AGENT component lives on the fleet hex grid. The agent only
"sees" its own hex + 1-hop neighbors (spatial fog-of-war) — this stops
attention scattering and duplicate execution.

## Registry

| Hex | Node | Component |
|---|---|---|
| (0,0) | `bdi-fsm-agent` | tower root / agent core |
| (1,0) | `blackboard-core` | BB1 blackboard |
| (0,1) | `memory-harness` | learnings / recipes / NMCT / NMTD |
| (-1,0) | `hardened-sandbox` | CoW + RLIMIT execution |
| (0,-1) | `agent-core` | FSM + BDI + control |
| (2,0) | `production-daemon` | live workspace loop |
| (2,1) | `self-test-gate` | 58-check deterministic gate |
| (1,1) | `deployment` | git / heartbeat wiring |
| (3,0) | `fleet-integration` | 4D HEX GAME player, task pool |
| (3,1) (1,2) (2,-1) | `betterment-*` | rotating betterment hexes |

## Claim/release protocol

```python
from bdi_fsm.fow import FOW
fow = FOW("/tmp/bdi_state/fow.json")
fow.claim("task_x")     # True if acquired, False if already held
fow.release("task_x")
fow.snapshot()          # current claims
```

- Claims expire after TTL (default 480s) — no deadlocks
- FOW is file-backed — survives shell restarts and cron overlaps
- The agent's heartbeat shows its `visible` set (1-hop neighbors):
  `['home', 'blackboard-core', ...]`

## Fleet grid (existing nodes)

```
          (-1,1) connectivity
  (-2,1) nyx-governor   (0,1) memory-harness
  (-1,0) hardened-sandbox (0,0) bdi-fsm-agent (1,0) blackboard-core
          (0,-1) agent-core
  (2,0) production-daemon  (2,1) self-test-gate  (3,0) fleet-integration
```
