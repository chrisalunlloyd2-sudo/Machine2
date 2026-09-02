"""Architecture-regime meta-controller tests — BDI chooses the active regime."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bdi_fsm.arch_regimes import (Regime, RegimeDriver, build_default_regimes,
                                  _facts_ok)
from bdi_fsm.arch_vectors import AtlantisReflexVector, BB1AgendaVector


def test_facts_ok_language():
    f = {"controller_active": False, "disk_free_mb": 100, "mode": "dev"}
    assert _facts_ok("not_controller_active", f) is True
    assert _facts_ok("disk_free_mb<200", f) is True
    assert _facts_ok("mode==dev", f) is True
    assert _facts_ok("mode!=prod", f) is True
    assert _facts_ok("has_mode", f) is True
    assert _facts_ok("has_missing", f) is False


def test_default_regimes_built():
    regs = build_default_regimes()
    names = [r.name for r in regs]
    assert names[0] == "reflex"          # highest-priority (safety) first
    assert set(names) == {"reflex", "impasse", "learn", "sequence",
                          "agenda", "activate"}


def test_select_reflex_regime():
    d = RegimeDriver()
    # controller down -> reflex (seek_controller), no deliberation
    r = d.select_regime({"facts": {"controller_active": False}})
    assert r is not None and r.name == "reflex"


def test_select_agenda_regime():
    d = RegimeDriver()
    r = d.select_regime({"candidates": [{"name": "x", "action": "do_x",
                                         "weight": 1.0}]})
    assert r is not None and r.name == "agenda"


def test_select_none_falls_back():
    d = RegimeDriver()
    assert d.select_regime({}) is None


def test_decide_reflex_wins_over_agenda():
    # reflex facts present AND candidates present -> reflex dominates (priority)
    d = RegimeDriver()
    ctx = {"facts": {"controller_active": False},
           "candidates": [{"name": "x", "action": "do_x", "weight": 9.0}]}
    dec = d.decide(ctx)
    assert dec["regime"] == "reflex"
    assert dec["action"] == "seek_controller"


def test_decide_runs_only_regime_vectors():
    d = RegimeDriver()
    ctx = {"candidates": [{"name": "x", "action": "do_x", "weight": 2.0}]}
    dec = d.decide(ctx)
    assert dec["regime"] == "agenda"
    assert dec["vector"] == "bb1-agenda"   # only the BB1 vector ran


def test_decide_fallback_returns_idle():
    d = RegimeDriver()
    dec = d.decide({})
    assert dec["regime"] == "default"
    assert dec["action"] == "idle"


def test_impasse_regime_defers():
    d = RegimeDriver()
    ctx = {"impasse": True,
           "candidates": [{"name": "a", "action": "x", "weight": 1.0},
                          {"name": "b", "action": "y", "weight": 1.0}]}
    dec = d.decide(ctx)
    assert dec["regime"] == "impasse"
    # two equal-weight maxima -> SOAR tie impasse -> defer (no random resolve)
    assert dec["action"] == "defer"


def test_regime_repr_and_stats():
    d = RegimeDriver()
    d.decide({"facts": {"journal_fail_rate": 0.9}})
    st = d.stats()
    assert st["reflex"]["activations"] == 1
    assert "atlantis-controller" in st["reflex"]["vectors"]
