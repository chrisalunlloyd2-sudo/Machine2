"""Nash threshold wiring — the gate's frozen 20 dBan becomes theta* = 10*log10(C_miss/C_false)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bdi_fsm.bayes_engine import (BanLedger, NashTuner, nash_threshold_dban,
                                  BDIStateEngine)
from bdi_fsm.code_patcher import CodeSynthesisGate


def test_nash_threshold_dban_units():
    # bans -> dBan: 10 * log10(ratio)
    assert abs(nash_threshold_dban(100, 1) - 20.0) < 1e-9   # frozen 20 dBan == ratio 100
    assert abs(nash_threshold_dban(10, 1) - 10.0) < 1e-9    # 1 ban == 10 dBan
    assert abs(nash_threshold_dban(1, 1) - 0.0) < 1e-9      # symmetric costs -> 0


def test_banledger_nash_derived():
    l = BanLedger(c_miss=100, c_false=1)
    assert abs(l.threshold_dban - 20.0) < 1e-9
    l2 = BanLedger(c_miss=10, c_false=1)
    assert abs(l2.threshold_dban - 10.0) < 1e-9


def test_banledger_default_backcompat():
    # no args -> historic frozen 20 dBan (nothing regresses)
    assert BanLedger().threshold_dban == 20.0
    assert BanLedger(threshold_dban=20.0).threshold_dban == 20.0


def test_banledger_explicit_override_wins():
    # explicit fixed threshold beats Nash costs
    l = BanLedger(threshold_dban=30, c_miss=100, c_false=1)
    assert l.threshold_dban == 30.0


def test_nashtuner_tracks_outcomes():
    t = NashTuner(c_miss=1.0, c_false=1.0)
    assert abs(t.threshold_dban() - 0.0) < 1e-9          # 1/1 -> 0 dBan
    t.record_miss()
    assert abs(t.threshold_dban() - nash_threshold_dban(2, 1)) < 1e-9
    t.record_false_alarm()
    assert abs(t.threshold_dban() - nash_threshold_dban(2, 2)) < 1e-9


def test_banledger_live_tuner():
    tuner = NashTuner(c_miss=100.0, c_false=1.0)
    l = BanLedger(tuner=tuner)
    assert abs(l._effective_threshold() - 20.0) < 1e-9
    tuner.record_false_alarm()  # C_false 1 -> 2
    assert abs(l._effective_threshold() - nash_threshold_dban(100, 2)) < 1e-9


def test_gate_fires_at_nash_threshold():
    l = BanLedger(c_miss=10, c_false=1)   # theta* = 10 dBan
    l.register("h", prior_prob=0.5)        # 0 dBan
    assert l.evaluate_gate() is None       # 0 < 10 -> no fire
    # LR = 100 -> +20 dBan, clears 10 dBan
    l.observe("h", p_evidence_given_h=100 / 101, p_evidence_given_not_h=1 / 101)
    fired = l.evaluate_gate()
    assert fired is not None and fired[0] == "h"
    assert fired[1] >= 10.0


def test_engine_passes_costs_through():
    eng = BDIStateEngine(c_miss=100, c_false=1)
    assert eng.c_miss == 100 and eng.c_false == 1


def test_codesynthesisgate_nash_threshold():
    g = CodeSynthesisGate(c_miss=100, c_false=1)
    assert abs(g.threshold_dban - 20.0) < 1e-9
