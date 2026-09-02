"""Symbolic planner proofs: deadlock / liveness / termination / total-correctness."""
import sys, os, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bdi_fsm.planner_proofs import (deadlock_report, liveness, termination,
                                    total_correctness, planner_audit)
from bdi_fsm.fsm import FSM
from bdi_fsm.agent import BDIFSMAgent


def _fsm_with(*edges, states=None):
    f = FSM("IDLE")
    for s in states or ["IDLE"]:
        f.add_state(s)
    for a, ev, b, *g in edges:
        f.add_transition(a, ev, b, guard=g[0] if g else None)
    return f


def test_deadlock_no_outgoing():
    # STUCK is NOT declared a terminal -> deadlock; END IS declared -> exit
    f = _fsm_with(("IDLE", "go", "STUCK"), ("IDLE", "fin", "END"),
                  states=["IDLE", "STUCK", "END"])
    r = deadlock_report(f, terminals=["END"])
    assert not r["holds"]
    assert r["deadlock_states"][0]["state"] == "STUCK"
    assert r["deadlock_states"][0]["cause"] == "no_outgoing"


def test_deadlock_all_guards_unsat():
    f = _fsm_with(("IDLE", "go", "STUCK", "p & ~p"), states=["IDLE", "STUCK"])
    r = deadlock_report(f)
    assert not r["holds"]
    assert r["deadlock_states"][0]["cause"] == "all_guards_unsat"


def test_deadlock_free_when_escape_exists():
    f = _fsm_with(("A", "go", "END"), ("A", "stay", "A"), states=["A", "END"])
    assert deadlock_report(f)["holds"]


def test_liveness_all_states_reach_terminal():
    f = _fsm_with(("IDLE", "go", "END"), states=["IDLE", "END"])
    r = liveness(f)
    assert r["holds"]


def test_liveness_trap_detected():
    # TRAP only self-loops; END unreachable from it
    f = _fsm_with(("IDLE", "go", "TRAP"), ("TRAP", "spin", "TRAP"),
                  ("IDLE", "fin", "END"), states=["IDLE", "TRAP", "END"])
    r = liveness(f)
    assert not r["holds"]


def test_liveness_unsat_path_detected():
    f = _fsm_with(("IDLE", "go", "MID", "p & ~p"), ("MID", "fin", "END"),
                  states=["IDLE", "MID", "END"])
    r = liveness(f)
    assert not r["holds"]


def test_termination_dag_holds():
    f = _fsm_with(("IDLE", "go", "MID"), ("MID", "fin", "END"),
                  states=["IDLE", "MID", "END"])
    assert termination(f)["holds"]


def test_termination_cycle_fails():
    f = _fsm_with(("A", "go", "B"), ("B", "loop", "A"), ("B", "fin", "END"),
                  states=["A", "B", "END"])
    r = termination(f)
    assert not r["holds"]
    assert r["cycles"]


def test_termination_self_loop_fails():
    f = _fsm_with(("A", "spin", "A"), ("A", "fin", "END"), states=["A", "END"])
    assert not termination(f)["holds"]


def test_total_correctness_accepting_terminals():
    f = _fsm_with(("IDLE", "go", "GOOD"), ("IDLE", "bad", "BAD"),
                  states=["IDLE", "GOOD", "BAD"])
    r = total_correctness(f, accepting=["GOOD", "BAD"])
    assert r["holds"]


def test_total_correctness_bad_state_blocks_goal_liveness():
    # BAD has no exit, so with GOAL=GOOD liveness fails (BAD cannot reach it)
    f = _fsm_with(("IDLE", "go", "GOOD"), ("IDLE", "bad", "BAD"),
                  states=["IDLE", "GOOD", "BAD"])
    r = total_correctness(f, goals=["GOOD"])
    assert not r["holds"]
    assert not r["liveness"]


def test_agent_fsm_liveness_to_success():
    # The agent is a cyclic control loop: no no-outgoing terminals, so the
    # meaningful liveness property is "COMMIT reachable from every state".
    a = BDIFSMAgent(state_dir=tempfile.mkdtemp())
    audit = planner_audit(a.fsm, goals=["COMMIT"])
    assert audit["deadlock"]["holds"]          # every state can leave
    assert audit["liveness"]["holds"]          # every state can reach COMMIT
    assert not audit["termination"]["holds"]   # cycles exist (see below)


def test_agent_fsm_livelock_cycles_detected():
    a = BDIFSMAgent(state_dir=tempfile.mkdtemp())
    t = planner_audit(a.fsm, goals=["COMMIT"])["termination"]
    livelocks = t["livelock_cycles"]
    paths = {" -> ".join(e["from"] for e in c) + " -> " + c[-1]["to"] for c in livelocks}
    # two real design findings:
    assert any("BLOCKED -> IDLE -> EVALUATE -> SYNTHESIZE -> VERIFY -> BLOCKED" == p
               for p in paths)   # failed tasks can be retried forever
    assert any("EVALUATE -> PLATEAU -> EVALUATE" == p for p in paths)
    # the main loop passes through COMMIT = success each cycle
    assert any("COMMIT -> WAIT_AEGIS -> COMMIT" == p
               for p in {" -> ".join(e["from"] for e in c) + " -> " + c[-1]["to"]
                         for c in t["task_cycles"]})


def test_agent_exposes_audit_method():
    a = BDIFSMAgent(state_dir=tempfile.mkdtemp())
    audit = a.planner_audit()  # defaults to goals=["COMMIT"]
    assert audit["deadlock"]["holds"] is True
    assert audit["liveness"]["holds"] is True
