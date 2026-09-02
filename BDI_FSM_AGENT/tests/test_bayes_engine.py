"""Tests for the Bayes/Banburismus decision engine (deciban ledger + FSM)."""
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bdi_fsm.bayes_engine import BanLedger, BDIStateEngine, State, TransitionRule


def test_prior_encoding():
    l = BanLedger()
    l.register("h", prior_prob=0.5)
    assert abs(l.scores["h"]) < 1e-9          # 0 dBan
    l.register("g", prior_prob=0.9)
    assert abs(l.scores["g"] - 10*math.log10(9)) < 1e-6   # ~+9.54 dBan


def test_observe_accumulates():
    l = BanLedger()
    l.register("h")
    l.observe("h", 0.8, 0.2)   # +6.02
    l.observe("h", 0.95, 0.05) # +12.79
    assert abs(l.scores["h"] - (10*math.log10(4) + 10*math.log10(19))) < 1e-6


def test_eliminate_and_gate_skips():
    l = BanLedger(threshold_dban=20)
    l.register("a"); l.register("b")
    l.eliminate("a")                        # -inf
    l.observe("b", 0.9, 0.1)                # +9.54 (below threshold)
    assert l.evaluate_gate() is None        # b is best but not enough
    l.observe("b", 0.9, 0.1)                # +9.54 => 19.08 still < 20
    l.observe("b", 0.9, 0.1)                # +9.54 => 28.62 > 20
    fired = l.evaluate_gate()
    assert fired and fired[0] == "b"


def test_ledger_persists_across_ticks():
    """The core fix: evidence must survive step() boundaries."""
    eng = BDIStateEngine(threshold_dban=20)
    eng.context = {"db": True}
    eng.add_transition(State.IDLE, TransitionRule(
        State.EXECUTING_TOOL, "go", lambda c: c.get("db") is True))
    eng.step([{"action": "go", "p_h": 0.8, "p_not_h": 0.2}])
    eng.step([{"action": "go", "p_h": 0.95, "p_not_h": 0.05}])
    assert eng.ledger is not None
    assert abs(eng.ledger.scores["go"] - 18.81) < 0.05  # accumulated, not reset


def test_gate_fires_and_transitions():
    eng = BDIStateEngine(threshold_dban=20)
    eng.context = {"db": True, "api": False}
    ran = []
    eng.add_transition(State.IDLE, TransitionRule(
        State.EXECUTING_TOOL, "sql", lambda c: c.get("db") is True,
        lambda c: ran.append("sql")))
    eng.add_transition(State.IDLE, TransitionRule(
        State.EXECUTING_TOOL, "api", lambda c: c.get("api") is True))
    fired = None
    for _ in range(3):
        fired = eng.step([{"action": "sql", "p_h": 0.9, "p_not_h": 0.1}])
    assert fired and fired[0] == "sql"
    assert ran == ["sql"]
    assert eng.current_state is State.EXECUTING_TOOL
    assert eng.ledger is None  # reset after transition


def test_precondition_eliminates():
    eng = BDIStateEngine(threshold_dban=20)
    eng.context = {"db": False}   # precondition fails
    eng.add_transition(State.IDLE, TransitionRule(
        State.EXECUTING_TOOL, "sql", lambda c: c.get("db") is True))
    eng.step([{"action": "sql", "p_h": 0.99, "p_not_h": 0.01}])
    assert eng.ledger.scores["sql"] == float("-inf")
    assert eng.step([]) is None


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print(f"  {name} PASS")
    print("ALL bayes_engine tests passed")
