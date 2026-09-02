# Developer Instruction Manual

For extending BDI_FSM_AGENT.

## Module map

| Module | Extend when... |
|---|---|
| `bdi_fsm/blackboard.py` | you need new shared state semantics |
| `bdi_fsm/fsm.py` | adding states/transitions to the behavior tree |
| `bdi_fsm/bdi.py` | adding plans/desires/tools (the rules engine) |
| `bdi_fsm/foundry.py` | new genetic operators or critic metrics |
| `bdi_fsm/hardened.py` | stronger isolation (cgroups, seccomp) |
| `bdi_fsm/memory.py` | learnings/recipes schema changes |
| `bdi_fsm/nmct.py` | vault formats (canonical AST, tape algorithms) |
| `bdi_fsm/nmtd.py` | incident schema / guardrail extraction |
| `bdi_fsm/toc_tok.py` | knowledge-tree navigation |
| `bdi_fsm/maslow.py` | NEW modular needs |
| `bdi_fsm/fow.py` | hex locking semantics |
| `bdi_fsm/control.py` | Aegis approval protocol |
| `bdi_fsm/agent.py` | assembling new subsystems |
| `bdi_fsm/daemon.py` | live workspace loop / AST inspector |

## Adding a tool

```python
# in agent.py _build_tools():
self.tools["my_tool"] = lambda **kw: {"result": deterministic(kw)}
# then a plan:
from bdi_fsm.bdi import BDIPlan
self.bdi.add_plan(BDIPlan("UseMyTool", ["status == EVALUATE"], "my_tool",
                          {"arg": 1}, priority=10))
```

## Adding a Maslow need

```python
from bdi_fsm.maslow import Need
def check():
    return {"satisfied": condition(), "detail": "..."}
agent.maslow.register(Need("my_need", "My need", "physiological", check))
```

## Testing discipline
- Every change must keep `tests/test_all.py` green.
- Add a `test_*` function for new behavior — deterministic, no mocks of
  the model (there is no model).
- Run: `python3 tests/test_all.py`

## Commit discipline
1. `python3 tests/test_all.py` (58/58)
2. `git add -A && git commit -m "type: description"`
3. `git push origin main`
4. Log the betterment: `python3 heartbeat/betterment.py`
