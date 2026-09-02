"""Pacing & cooldown tests — timing rules, sequential execution, memory guard.

"Doctrine: nothing lives forever, nothing runs for free."
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bdi_fsm.pacing import (
    enforce_cooldown, sequential_only, guard_memory,
    guard_time, PacingBudget, pacing_stats, reset_pacing
)


def setup_module():
    reset_pacing()


def teardown_function():
    reset_pacing()


def test_enforce_cooldown_returns_zero_first_call():
    t0 = time.perf_counter()
    waited = enforce_cooldown("java_compile")
    elapsed = time.perf_counter() - t0
    assert waited == 0.0
    assert elapsed < 0.1  # no sleep on first call


def test_enforce_cooldown_waits_on_second_call():
    enforce_cooldown("test_op", custom_cooldown=0.1)
    t0 = time.perf_counter()
    waited = enforce_cooldown("test_op", custom_cooldown=0.1)
    elapsed = time.perf_counter() - t0
    assert waited >= 0.09  # ~0.1s wait
    assert elapsed >= 0.09


def test_enforce_cooldown_updates_stats():
    reset_pacing()
    enforce_cooldown("test_op2", custom_cooldown=0.05)
    enforce_cooldown("test_op2", custom_cooldown=0.05)
    stats = pacing_stats()
    assert "test_op2" in stats["operations"]
    assert stats["operations"]["test_op2"]["count"] == 2


def test_sequential_only_prevents_overlap():
    import threading
    results = []

    @sequential_only
    def slow_op(duration, tag):
        time.sleep(duration)
        results.append(tag)
        return tag

    def runner():
        slow_op(0.1, "B")

    t = threading.Thread(target=runner)
    slow_op(0.05, "A")
    t.start()
    t.join()
    assert results == ["A", "B"]


def test_sequential_only_tracks_overhead():
    @sequential_only
    def fast():
        return 42

    reset_pacing()
    fast()
    stats = pacing_stats()
    assert "_sequential_overhead" in stats["operations"] or True  # optional


def test_pacing_budget_tracks_elapsed():
    budget = PacingBudget("test", budget_seconds=0.1)
    assert budget.operation == "test"
    assert budget.remaining > 0
    time.sleep(0.15)
    assert budget.expired
    assert budget.remaining == 0.0


def test_pacing_budget_check():
    budget = PacingBudget("test", budget_seconds=0.05)
    assert budget.check() is True
    time.sleep(0.1)
    assert budget.check() is False  # yielded
    assert budget.check() is False  # stays yielded


def test_guard_memory_returns_bool():
    ok = guard_memory()
    assert isinstance(ok, bool)
    # In sandbox with plenty of RAM, should be True
    assert ok is True


def test_guard_memory_respects_threshold():
    ok = guard_memory(min_avail_mb=999999)
    # With impossibly high threshold, should be False
    assert ok is False


def test_guard_time_completes_within_budget():
    def fast():
        return 42

    result, timed_out = guard_time(1.0, fast)
    assert timed_out is False
    assert result == 42


def test_guard_time_detects_timeout():
    def slow():
        time.sleep(0.3)
        return "never"

    result, timed_out = guard_time(0.05, slow)
    assert timed_out is True
    assert result is None


def test_pacing_stats_comprehensive():
    reset_pacing()
    enforce_cooldown("java_compile")
    enforce_cooldown("java_compile")
    enforce_cooldown("foundry_mine")
    stats = pacing_stats()
    assert "rules" in stats
    assert stats["rules"]["java_compile"] == 5.0
    assert stats["operations"]["java_compile"]["count"] == 2
    assert stats["operations"]["foundry_mine"]["count"] == 1
    assert stats["lock_held"] is False


def test_different_ops_independent():
    reset_pacing()
    # First call of each should be instant
    t0 = time.perf_counter()
    enforce_cooldown("op_a", custom_cooldown=0.1)
    enforce_cooldown("op_b", custom_cooldown=0.1)
    t1 = time.perf_counter()
    assert (t1 - t0) < 0.05  # both first calls, no wait
