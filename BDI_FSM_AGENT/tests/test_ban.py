"""BAN (hartley/dit) soul tests — base-10 information theory, step-by-step."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bdi_fsm.ban import Ban, BanLedger


def test_definition_one_hartley():
    assert abs(Ban.self_info(0.1) - 1.0) < 1e-9
    assert abs(Ban.hartley(10) - 1.0) < 1e-9


def test_conversions():
    assert abs(Ban.to_bits(1.0) - math.log2(10.0)) < 1e-9
    assert abs(Ban.to_nats(1.0) - math.log(10.0)) < 1e-9
    assert abs(Ban.from_bits(1.0) - 1.0 / math.log2(10.0)) < 1e-9


def test_fair_coin_is_one_bit():
    h = Ban.entropy([0.5, 0.5])
    assert abs(h - math.log10(2.0)) < 1e-9
    assert abs(Ban.to_bits(h) - 1.0) < 1e-9


def test_fair_ten_way_is_one_ban():
    assert abs(Ban.entropy([0.1] * 10) - 1.0) < 1e-6


def test_certainty():
    assert Ban.certainty(0.0) == 1.0
    assert abs(Ban.certainty(1.0) - 0.1) < 1e-9


def test_ledger_step_and_done():
    l = BanLedger()
    l.step("observe", [0.1] * 10, [1.0] + [0.0] * 9)
    assert l.is_done()
    assert abs(l.total_gain() - 1.0) < 1e-6


def test_zero_gain_step_is_wasted():
    l = BanLedger()
    l.step("noop", [1.0], [1.0])
    assert l.wasted_steps() and l.wasted_steps()[0]["step"] == "noop"


def test_verdict_gate():
    l = BanLedger()
    v = l.verdict("resolve", [0.1] * 10, [1.0] + [0.0] * 9)
    assert v["verdict"] == "DONE"
    v2 = l.verdict("half", [0.1] * 10, [0.5, 0.5] + [0.0] * 8)
    assert v2["verdict"] == "GO"
    v3 = l.verdict("noop", [1.0], [1.0])
    assert v3["verdict"] == "STEP_BACK"


def test_kl_divergence_bans():
    k = Ban.kl([0.5, 0.5], [0.5, 0.5])
    assert abs(k) < 1e-9
    k2 = Ban.kl([1.0, 0.0], [0.5, 0.5])
    assert abs(k2 - 1.0 * math.log10(2.0)) < 1e-9  # 0.301 bans


def test_ban_gain_verifier_in_certainty_gate():
    from bdi_fsm.certainty import CertaintyGate
    g = CertaintyGate()
    r = g.assess({"name": "s", "checks": [("ban_gain", 0.5)]},
                 {"output": "x", "ban_gain": 1.0})
    assert r["verdict"] == "PASS"
    r2 = g.assess({"name": "s", "checks": [("ban_gain", 0.5)]},
                  {"output": "x", "ban_gain": 0.0})
    assert r2["verdict"] == "STEP_BACK"
