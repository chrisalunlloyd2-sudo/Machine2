"""Reachability verifier — 'prove you can reach the exit'."""
import sys, os, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from bdi_fsm import reachability
from bdi_fsm.fsm import FSM
from bdi_fsm.reachability import (truth_table, guard_verdict, path_to,
                                  verify_path, prove_exit, ReachabilityError)
from bdi_fsm.agent import BDIFSMAgent


def test_truth_table_tautology():
    assert truth_table("p -> p")["is_tautology"]
    assert truth_table("~p | p")["is_tautology"]


def test_truth_table_contradiction():
    tt = truth_table("p & ~p")
    assert not tt["is_satisfiable"]
    assert not tt["is_tautology"]


def test_truth_table_satisfiable_not_tautology():
    tt = truth_table("p & (q | ~q)")  # == p
    assert tt["is_satisfiable"]
    assert not tt["is_tautology"]


def test_guard_verdicts():
    assert guard_verdict(None)[0] == "TAUTOLOGY"
    assert guard_verdict("p -> p")[0] == "TAUTOLOGY"
    assert guard_verdict("p & q")[0] == "SATISFIABLE"
    assert guard_verdict("p & ~p")[0] == "UNSAT"
    assert guard_verdict(lambda: True)[0] == "RUNTIME"


def test_malformed_formula_raises():
    with pytest.raises(ReachabilityError):
        truth_table("p &")
    with pytest.raises(ReachabilityError):
        truth_table("(p | q")


def test_path_found():
    f = FSM("IDLE")
    for s in ["IDLE", "A", "B"]:
        f.add_state(s)
    f.add_transition("IDLE", "go", "A")
    f.add_transition("A", "go", "B")
    p = path_to(f, "B")
    assert p is not None
    assert [e["event"] for e in p] == ["go", "go"]


def test_unreachable_returns_none():
    f = FSM("IDLE")
    for s in ["IDLE", "A"]:
        f.add_state(s)
    f.add_transition("IDLE", "go", "A")
    assert path_to(f, "X") is None


def test_unsat_guard_blocks_path():
    f = FSM("IDLE")
    for s in ["IDLE", "EVALUATE", "VERIFY", "COMMIT"]:
        f.add_state(s)
    f.add_transition("IDLE", "start", "EVALUATE")
    f.add_transition("EVALUATE", "check", "VERIFY", guard="ready & ~ready")
    f.add_transition("VERIFY", "ok", "COMMIT")
    v = verify_path(f, "COMMIT")
    assert not v["reachable"]
    assert v["blocked"]["from"] == "EVALUATE"
    assert v["blocked"]["verdict"] == "UNSAT"


def test_satisfiable_guard_allows_with_note():
    f = FSM("IDLE")
    for s in ["IDLE", "COMMIT"]:
        f.add_state(s)
    f.add_transition("IDLE", "go", "COMMIT", guard="ready")
    v = verify_path(f, "COMMIT")
    assert v["reachable"]
    assert v["proofs"][0]["verdict"] == "SATISFIABLE"
    assert v["proofs"][0]["models"] >= 1


def test_cycle_safe():
    f = FSM("IDLE")
    for s in ["IDLE", "A", "B"]:
        f.add_state(s)
    f.add_transition("IDLE", "go", "A")
    f.add_transition("A", "go", "B")
    f.add_transition("B", "go", "A")
    p = path_to(f, "B")
    assert p is not None and len(p) == 2


def test_prove_exit_terminals():
    f = FSM("IDLE")
    for s in ["IDLE", "DONE", "DEAD"]:
        f.add_state(s)
    f.add_transition("IDLE", "ok", "DONE")
    f.add_transition("IDLE", "bad", "DEAD")
    pe = prove_exit(f)
    assert pe["all_reachable"]
    assert pe["summary"] == {"DONE": True, "DEAD": True}


def test_agent_verify_task_exit():
    a = BDIFSMAgent(state_dir=tempfile.mkdtemp())
    r = a.verify_task_exit()
    assert r["task_exit_provable"] is True
    assert any("EVALUATE" in s and "COMMIT" in s for s in (r["path"] or []))


def test_agent_prove_exit_live():
    a = BDIFSMAgent(state_dir=tempfile.mkdtemp())
    pe = a.prove_exit()
    assert pe["all_reachable"] is True
    assert pe["summary"].get("COMMIT") is True
