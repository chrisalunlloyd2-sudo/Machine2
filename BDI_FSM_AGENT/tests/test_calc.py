import math
from bdi_fsm.calc import (CalcFlow, BudgetExceeded, cosine, nash_threshold,
                          shannon_entropy_bits, similarity_ban)


def test_similarity_ban_monotonic_and_memoized():
    a = similarity_ban(0.9)
    b = similarity_ban(0.9)
    assert a == b  # deterministic
    assert similarity_ban(0.9) > similarity_ban(0.0) > similarity_ban(-0.9)


def test_nash_threshold_matches_log10_ratio():
    assert nash_threshold(10.0, 1.0) == math.log10(10.0)  # == 1.0
    assert nash_threshold(1.0, 0.0) == float("inf")


def test_shannon_entropy():
    # uniform over 2 = 1 bit; over 4 = 2 bits
    assert abs(shannon_entropy_bits((1, 1)) - 1.0) < 1e-9
    assert abs(shannon_entropy_bits((1, 1, 1, 1)) - 2.0) < 1e-9


def test_cosine_single_pass():
    assert cosine([1, 0, 0], [1, 0, 0]) == 1.0
    assert cosine([1, 0, 0], [0, 1, 0]) == 0.0
    assert abs(cosine([1, 1], [1, -1])) < 1e-9


def test_calcflow_within_budget():
    f = CalcFlow(budget=100)
    assert f.ban(0.5) == similarity_ban(0.5)
    assert f.ops < f.budget


def test_calcflow_exceeds_budget_raises():
    f = CalcFlow(budget=5)
    try:
        for _ in range(10):
            f.ban(0.5)
        assert False, "expected BudgetExceeded"
    except BudgetExceeded:
        pass
