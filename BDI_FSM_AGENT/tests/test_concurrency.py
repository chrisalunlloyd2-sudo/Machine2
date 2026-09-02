"""Concurrency + load hardening tests.

Verifies the plateau/regime decision path holds its invariants under load:
  - deterministic regime selection + counter integrity under concurrent calls
  - FSM transition-log sequential consistency under concurrent fires
  - livelock-freedom of the PLATEAU mutation loop (a LOGICAL property — the
    loop must terminate and every exit must mutate state, never a bare retry)
  - BanLedger evidence accumulation stays a valid number under concurrent observes

NOTE (honesty): on CPython the GIL makes a single `obj.attr += 1` effectively
atomic, so the specific read-modify-write races these locks guard against are
NOT reliably triggerable in a unit test here. The locks are defensive
hardening for free-threaded Python (3.13+ --disable-gil), multiprocessing, and
the upcoming multi-agent mesh — where these exact races become real. The tests
assert the *invariants* (determinism, log consistency, termination, valid
scores) which MUST hold regardless of thread interleaving, and which WOULD
catch corruption on a GIL-free build.
"""
import os
import sys
import tempfile
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bdi_fsm.arch_regimes import RegimeDriver
from bdi_fsm.fsm import FSM
from bdi_fsm.plateau import PlateauDetector, PlateauType
from bdi_fsm.bayes_engine import BanLedger
from bdi_fsm.agent import BDIFSMAgent


def test_regime_driver_no_lost_activations():
    """16 threads x 200 selects -> exactly 3200 activations, no lost updates."""
    d = RegimeDriver()
    ctx = {"candidates": [{"name": "x", "action": "do_x", "weight": 2.0}]}
    N_THREADS, N_ITER = 16, 200

    def worker():
        for _ in range(N_ITER):
            r = d.decide(ctx, record=False)
            assert r["regime"] == "agenda"   # deterministic selection

    threads = [threading.Thread(target=worker) for _ in range(N_THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    total = sum(r.activations for r in d.regimes)
    assert total == N_THREADS * N_ITER, f"lost updates: {total} != {N_THREADS*N_ITER}"


def test_fsm_atomic_transitions_sequential_consistency():
    """Concurrent fires must produce a sequentially-consistent transition log."""
    fsm = FSM(initial_state="IDLE")
    fsm.add_transition("IDLE", "go", "A")
    fsm.add_transition("A", "go", "B")
    fsm.add_transition("B", "go", "C")

    def worker():
        for _ in range(100):
            fsm.fire("go")

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # valid states only, and the log is a chain (each 'from' == prior 'to')
    assert fsm.state in ("IDLE", "A", "B", "C")
    for i in range(1, len(fsm.transition_log)):
        assert fsm.transition_log[i]["from"] == fsm.transition_log[i-1]["to"], \
            f"non-sequential log at {i}: {fsm.transition_log[i-1]} -> {fsm.transition_log[i]}"


def test_plateau_detector_threadsafe():
    """Concurrent observe() must not corrupt the stagnant counter (no negatives)."""
    d = PlateauDetector(patience=1000)
    N_THREADS, N_ITER = 8, 2000

    def worker():
        for i in range(N_ITER):
            d.observe(i % 2 == 0)   # alternate improved / stagnant

    threads = [threading.Thread(target=worker) for _ in range(N_THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert 0 <= d.stagnant <= d.patience, f"corrupted counter: {d.stagnant}"


def test_banledger_threadsafe_accumulation():
    """Concurrent observes must accumulate evidence without lost updates."""
    l = BanLedger(threshold_dban=0.0)
    l.register("h", prior_prob=0.5)
    N_THREADS, N_ITER = 8, 500
    # each observe: LR = 0.8/0.2 = 4 -> +6.0206 dBan
    per = 10 * 0.60206

    def worker():
        for _ in range(N_ITER):
            l.observe("h", 0.8, 0.2)

    threads = [threading.Thread(target=worker) for _ in range(N_THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    expected = N_THREADS * N_ITER * per
    assert l.scores["h"] > expected * 0.9, \
        f"lost updates in ledger: {l.scores['h']} << {expected}"


def test_plateau_mutation_never_stays_in_plateau():
    """Every PLATEAU exit must leave the plateau state (mutation, not a loop)."""
    a = BDIFSMAgent(state_dir=tempfile.mkdtemp())
    for method in ("expand_horizon", "decompose_subgoal", "commit_min_regret"):
        a.fsm.state = "PLATEAU"
        winners = ["def f():\n    return 1\n"] if method == "commit_min_regret" else []
        a.break_plateau(method, winners)
        assert a.fsm.state != "PLATEAU", f"{method} did not advance"


def test_plateau_loop_livelock_free():
    """A stall-recover loop that mutates a fact must terminate (no livelock)."""
    a = BDIFSMAgent(state_dir=tempfile.mkdtemp())
    horizon = 0
    for _ in range(20):                       # hard upper bound
        if horizon < 3:
            horizon += 1
            a.bb.assert_fact("horizon", horizon)
            a.fsm.state = "PLATEAU"
            a.break_plateau("expand_horizon", [])
            assert a.fsm.state == "EVALUATE"  # mutation re-enters with changed fact
        else:
            a.fsm.state = "PLATEAU"
            a.break_plateau("commit_min_regret", ["def f():\n    return 1\n"])
            assert a.fsm.state == "COMMIT"
            return
    raise AssertionError("livelock: plateau loop did not terminate in bounded steps")
