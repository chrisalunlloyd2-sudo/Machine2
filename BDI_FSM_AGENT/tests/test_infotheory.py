"""Tests for info-theoretic decision self-model (source theory correlation)."""
import math
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bdi_fsm"))

from bdi_fsm.infotheory import (
    DecisionEntropy, directed_information_rate, entropy, entropy_rate,
    max_entropy, mutual_information, redundancy, channel_capacity_estimate,
)


def test_entropy_zero_deterministic():
    assert entropy(["a"] * 10) == 0.0


def test_entropy_uniform_two_symbols():
    assert abs(entropy(["a", "b"] * 50) - 1.0) < 1e-9


def test_entropy_uniform_four_symbols():
    assert abs(entropy(["a", "b", "c", "d"] * 25) - 2.0) < 1e-9


def test_max_entropy():
    assert max_entropy(1) == 0.0
    assert abs(max_entropy(4) - 2.0) < 1e-9


def test_redundancy_full():
    assert redundancy(["a"] * 10) == 1.0


def test_redundancy_zero_uniform():
    assert abs(redundancy(["a", "b"] * 50)) < 1e-9


def test_entropy_rate_alternating_predictable():
    # ABABAB: given previous symbol, next is fully determined -> rate 0
    seq = (["a", "b"] * 50)[:-1]  # odd length so bigrams exist
    assert entropy_rate(seq) < 1e-9


def test_entropy_rate_random_equals_marginal():
    # independent uniform: rate ~ H(X) (no history structure)
    import random
    random.seed(7)
    seq = [random.choice("abcd") for _ in range(2000)]
    assert abs(entropy_rate(seq) - entropy(seq)) < 0.05


def test_mutual_information_independent_zero():
    import random
    random.seed(3)
    x = [random.choice("ab") for _ in range(2000)]
    y = [random.choice("cd") for _ in range(2000)]
    assert mutual_information(x, y) < 0.02


def test_mutual_information_perfect_mapping():
    x = ["a", "b", "c"] * 100
    y = [{"a": "win", "b": "fail", "c": "block"}[s] for s in x]
    assert abs(mutual_information(x, y) - entropy(x)) < 1e-9


def test_channel_capacity_positive_for_coupled():
    x = ["a", "b", "c"] * 100
    y = [{"a": "win", "b": "fail", "c": "block"}[s] for s in x]
    assert channel_capacity_estimate(x, y) > 0.5


def test_directed_info_feedback_loop():
    """Learning loop: outcome of previous step shapes next outcome."""
    # x drives y, and y_{i-1} also influences y_i (feedback)
    x = []
    y = []
    prev = "ok"
    import random
    random.seed(11)
    for i in range(2000):
        xi = random.choice("ab")
        x.append(xi)
        if xi == "a":
            yi = "ok" if random.random() < 0.9 else "fail"
        else:
            yi = "fail" if random.random() < 0.9 else "ok"
        if prev == "fail" and random.random() < 0.5:
            yi = "ok"  # recovery feedback
        y.append(yi)
        prev = yi
    assert directed_information_rate(x, y) > 0.0


def test_decision_entropy_journal_load():
    d = tempfile.mkdtemp()
    jp = os.path.join(d, "journal.jsonl")
    with open(jp, "w") as f:
        for i in range(20):
            act = "act_a" if i % 2 == 0 else "act_b"
            out = "win" if i % 3 == 0 else "fail"
            f.write(f'{{"action": "{act}", "outcome": "{out}"}}\n')
    de = DecisionEntropy(journal_path=jp)
    assert len(de.decisions) == 20
    assert len(de.outcomes) == 20
    assert de.H() > 0.0
    assert de.I() >= 0.0
    assert de.capacity() >= 0.0
    assert de.directed() >= 0.0
    assert 0.0 <= de.R() <= 1.0


def test_report_structure():
    de = DecisionEntropy()
    for i in range(30):
        de.add("act_a" if i % 2 == 0 else "act_b",
               "win" if i % 3 == 0 else "fail")
    rep = de.report()
    for key in ("samples", "alphabet", "H", "Hmax", "rate", "I_XY",
                "capacity", "directed", "redundancy"):
        assert key in rep, key
    assert rep["samples"] == 30.0


def test_interpret_flags():
    de = DecisionEntropy()
    for i in range(30):
        de.add("same_act", "ok")   # fully habitual
    assert any("HABITUAL" in s for s in de.interpret())


def test_interpret_insufficient():
    de = DecisionEntropy()
    de.add("a", "ok")
    assert any("not enough" in s for s in de.interpret())


def test_to_ascii_renders():
    de = DecisionEntropy()
    for i in range(20):
        de.add("x" if i % 2 else "y", "ok" if i % 3 else "fail")
    out = de.to_ascii()
    assert "INFO-THEORETIC" in out
    assert "H=" in out


def test_directed_info_no_feedback_zero():
    """Without feedback conditioning, directed info ~ 0."""
    import random
    random.seed(5)
    x = [random.choice("ab") for _ in range(2000)]
    y = [random.choice("cd") for _ in range(2000)]
    assert directed_information_rate(x, y) < 0.02


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for fn in fns:
        try:
            fn()
            passed += 1
            print(f"  ok  {fn.__name__}")
        except Exception as e:
            failed += 1
            print(f"FAIL  {fn.__name__}: {e}")
            traceback.print_exc()
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
