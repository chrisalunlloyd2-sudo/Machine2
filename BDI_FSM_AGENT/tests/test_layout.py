from bdi_fsm.layout import (RuleBank, features_from, choose_strategy,
                            correction_to_rule, train_correction,
                            log_trace, load_traces)
import os, tempfile


def test_features_comparison():
    f = features_from("compare python and javascript", [], ["python", "javascript"])
    assert f["intent"] == "comparison" and f["columns"] == 2


def test_choose_strategy_comparison_table():
    f = {"intent": "comparison", "columns": 2}
    assert choose_strategy(f) == "table"


def test_choose_strategy_default_list():
    f = {"intent": None, "columns": 1}
    assert choose_strategy(f) == "list"


def test_correction_to_rule():
    f = {"intent": "comparison", "columns": 2, "item_count": 2}
    r = correction_to_rule(f, "list", "table")
    assert r["then"] == {"layout": "table"}
    assert r["if"]["columns_min"] == 2


def test_train_correction_adds_rule():
    bank = RuleBank([])  # empty bank
    f = {"intent": "comparison", "columns": 3}
    train_correction(bank, f, "list", "table")
    assert bank.choose_layout(f) == "table"
    # a non-comparison feature still defaults
    assert bank.choose_layout({"intent": None, "columns": 1}) == "list"


def test_trace_log_roundtrip():
    d = tempfile.mkdtemp()
    p = os.path.join(d, "traces.jsonl")
    log_trace(p, {"intent": "comparison", "layout": "table", "judgment": "good"})
    log_trace(p, {"intent": "list", "layout": "list", "judgment": "bad"})
    tr = load_traces(p)
    assert len(tr) == 2 and tr[0]["judgment"] == "good"


def test_rule_bank_empty_list_is_really_empty():
    # regression: RuleBank([]) used to fall back to DEFAULT_RULE_BANK
    # because "[] or DEFAULT" treats [] as falsy.
    bank = RuleBank([])
    f = {"intent": "comparison", "columns": 2}
    assert bank.choose_layout(f) == "list"  # no seeded rules -> default
    assert bank.choose_layout({"intent": None, "columns": 1}) == "list"
