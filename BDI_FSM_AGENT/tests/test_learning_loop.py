import os
import tempfile
from bdi_fsm.layout import log_trace
from bdi_fsm.learning_loop import (encode_trace, mine_patterns, run_learning_loop,
                                   load_sops)

_LOW = {
    "stability": {"min_occurrences": 3, "min_consistency": 0.8},
    "compression": {"min_events_explained": 5, "max_description_bits": 512},
    "predictive_utility": {"min_error_reduction": 0.1, "min_latency_improvement": 0.05},
    "integration": {"max_conflicts_with_sops": 0, "max_added_complexity_score": 0.2},
    "weights": {"stability": 0.35, "compression": 0.25,
                "predictive_utility": 0.25, "integration": 0.15},
    "promotion_threshold": 0.7,
}


def _make_traces(path, n_comparison=10, n_list=5, n_bad=2):
    for _ in range(n_comparison):
        log_trace(path, {"features": {"intent": "comparison", "columns": 2},
                         "strategy": "table", "quality": 1.0, "judgment": "good"})
    for _ in range(n_list):
        log_trace(path, {"features": {"intent": "list", "columns": 3},
                         "strategy": "list", "quality": 1.0, "judgment": "good"})
    for _ in range(n_bad):
        log_trace(path, {"features": {"intent": None, "columns": 1},
                         "strategy": "list", "quality": 0.0, "judgment": "bad"})


def test_encode_trace():
    t = {"features": {"intent": "comparison", "columns": 2},
         "strategy": "table", "judgment": "good"}
    assert encode_trace(t) == ["intent:comparison", "layout:table", "ok"]


def test_mine_patterns_finds_guard():
    d = tempfile.mkdtemp()
    p = os.path.join(d, "t.jsonl")
    _make_traces(p, n_comparison=3, n_list=0, n_bad=0)
    from bdi_fsm.layout import load_traces
    pats = mine_patterns(load_traces(p))
    assert ["intent:comparison", "layout:table"] in pats


def test_promotes_with_enough_evidence():
    d = tempfile.mkdtemp()
    tp, sp = os.path.join(d, "t.jsonl"), os.path.join(d, "s.json")
    _make_traces(tp)
    r = run_learning_loop(tp, sp, config=_LOW)
    assert r["promoted"] > 0
    got = [" -> ".join(s["pattern"]) for s in r["new_sops"]]
    assert any("intent:comparison" in g and "layout:table" in g for g in got)


def test_sop_persistence_no_duplicate():
    d = tempfile.mkdtemp()
    tp, sp = os.path.join(d, "t.jsonl"), os.path.join(d, "s.json")
    _make_traces(tp)
    run_learning_loop(tp, sp, config=_LOW)
    r2 = run_learning_loop(tp, sp, config=_LOW)
    assert r2["new_sops"] == []  # already stored, no duplicates
    assert len(load_sops(sp)) > 0


def test_entry_exit_report():
    d = tempfile.mkdtemp()
    tp, sp = os.path.join(d, "t.jsonl"), os.path.join(d, "s.json")
    _make_traces(tp, n_comparison=4, n_list=2, n_bad=1)
    r = run_learning_loop(tp, sp, config=_LOW)
    assert r["entry"]["comparison"] == 4
    assert r["exit"]["good"] == 6 and r["exit"]["bad"] == 1


def test_demotion_of_stale_sop():
    # promote an SOP, then let its pattern vanish from history -> demoted
    d = tempfile.mkdtemp()
    tp, sp = os.path.join(d, "t.jsonl"), os.path.join(d, "s.json")
    _make_traces(tp)
    r1 = run_learning_loop(tp, sp, config=_LOW)
    assert r1["promoted"] > 0
    # history changes: only 'form' intents now, comparison/list SOPs go stale
    open(tp, "w").close()
    for _ in range(8):
        log_trace(tp, {"features": {"intent": "form", "columns": 2},
                       "strategy": "form", "quality": 1.0, "judgment": "good"})
    r2 = run_learning_loop(tp, sp, config=_LOW)
    assert r2["demoted"] > 0
    # store no longer holds the stale comparison/list SOPs
    remaining = [s["pattern"] for s in load_sops(sp)]
    assert all("form" in " ".join(p) or "comparison" not in " ".join(p) for p in remaining)
