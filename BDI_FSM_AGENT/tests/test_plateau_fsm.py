"""PLATEAU FSM tests — soft-stall state, mutation-only exits, no bare retry."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bdi_fsm.agent import BDIFSMAgent


def _agent():
    return BDIFSMAgent(state_dir=tempfile.mkdtemp())


def test_retry_removed_from_blocked():
    a = _agent()
    a.fsm.state = "BLOCKED"
    assert a.fsm.can("retry") is False          # the invariant loop is gone
    assert a.fsm.can("give_up") is True


def test_plateau_has_mutation_only_exits():
    a = _agent()
    a.fsm.state = "PLATEAU"
    assert a.fsm.can("expand_horizon") is True
    assert a.fsm.can("decompose_subgoal") is True
    assert a.fsm.can("commit_min_regret") is True
    assert a.fsm.can("give_up") is True
    assert a.fsm.can("retry") is False          # no bare retry from PLATEAU


def test_break_plateau_commit_min_regret():
    a = _agent()
    a.fsm.state = "PLATEAU"
    r = a.break_plateau("commit_min_regret", ["def f():\n    return 1\n"])
    assert r["state"] == "COMMIT"
    assert a.fsm.state == "COMMIT"


def test_break_plateau_expand_horizon():
    a = _agent()
    a.fsm.state = "PLATEAU"
    r = a.break_plateau("expand_horizon", [])
    assert r["state"] == "EVALUATE"
    assert a.fsm.state == "EVALUATE"


def test_break_plateau_decompose_subgoal():
    a = _agent()
    a.fsm.state = "PLATEAU"
    r = a.break_plateau("decompose_subgoal", [])
    assert r["state"] == "EVALUATE"
    assert a.fsm.state == "EVALUATE"


def test_break_plateau_unknown_method_stays():
    a = _agent()
    a.fsm.state = "PLATEAU"
    r = a.break_plateau("nope", [])
    assert r["state"] == "PLATEAU"


def test_break_plateau_commit_no_winner():
    a = _agent()
    a.fsm.state = "PLATEAU"
    r = a.break_plateau("commit_min_regret", [])
    assert r["state"] == "BLOCKED"
    assert r["reason"] == "no winner to commit"


def test_resolve_slot_tie_routes_to_plateau():
    """Two compilable candidates, no discriminator => soft plateau (tie)."""
    a = _agent()

    def gen():
        return ["def f():\n    return 1\n", "def f():\n    return 2\n"]

    r = a.resolve_slot("f", "test", candidate_generator=gen, test_fn=None)
    assert r["state"] == "PLATEAU", r
    assert r["reason"] == "candidate_tie"
    assert len(r["winners"]) == 2
