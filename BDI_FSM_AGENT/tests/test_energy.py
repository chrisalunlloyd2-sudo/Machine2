#!/usr/bin/env python3
"""Deterministic tests for the Energy Manifold — Q.E.D. zero-repeat
guarantee, verified numerically."""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bdi_fsm.energy import (
    EnergyManifold, gaussian_bump, finite_gradient, verify_zero_repeat_guarantee)


def test_base_energy_min_at_goal():
    m = EnergyManifold(goal=(0.0, 0.0))
    assert m.base_energy((0.0, 0.0)) == 0.0
    assert m.base_energy((1.0, 1.0)) > 0.0
    assert m.base_energy((2.0, 2.0)) > m.base_energy((1.0, 1.0))  # convex


def test_gaussian_bump_localized():
    assert abs(gaussian_bump((0, 0), (0, 0), 1.0, 1.0) - 1.0) < 1e-9
    far = gaussian_bump((0, 0), (10, 0), 1.0, 1.0)
    assert far < 1e-9  # decays to ~0 outside the ball


def test_finite_gradient_linear_field():
    # E(x,y) = x^2 + y^2 -> grad = (2x, 2y)
    g = finite_gradient(lambda p: p[0] ** 2 + p[1] ** 2, (3.0, 4.0), eps=1e-3)
    assert abs(g[0] - 6.0) < 1e-2, g
    assert abs(g[1] - 8.0) < 1e-2, g


def test_inject_failure_raises_energy():
    m = EnergyManifold(goal=(0.0, 0.0))
    e_before = m.total_energy((1.0, 0.0))
    m.inject_failure((1.0, 0.0), amplitude=5.0)
    e_after = m.total_energy((1.0, 0.0))
    assert e_after > e_before
    assert len(m.obstacles) == 1


def test_alignment_score_positive_toward_goal():
    m = EnergyManifold(goal=(0.0, 0.0))
    # at (2,0), field toward goal (0,0) = (-1,0); -grad E = (-2x, -2y) = (-4,0)
    V = m._plan_field_toward((2.0, 0.0), (0.0, 0.0))
    s = m.alignment_score((2.0, 0.0), V)
    assert s > 0, s


def test_obstacle_flips_score_to_negative():
    """After injecting a bump at x_f, a plan heading to x_f gets S <= 0."""
    m = EnergyManifold(goal=(0.0, 0.0))
    x_f = (0.4, 0.0)          # on the way to the goal -> c0 > 0
    V = m._plan_field_toward((0.8, 0.0), x_f)
    s_before = m.alignment_score((0.8, 0.0), V)
    assert s_before > 0, s_before   # failing plan WAS making progress
    m.inject_failure(x_f, amplitude=m.required_amplitude(x_f))
    s_after = m.alignment_score((0.8, 0.0), V)
    assert s_after <= 0, s_after    # bump flips it to rejection


def test_select_plan_rejects_failed_trajectory():
    m = EnergyManifold(goal=(0.0, 0.0))
    x = (0.5, 0.5)
    x_f = (2.0, 2.0)
    plans = [("good", (0.0, 0.0)), ("doomed", x_f)]
    picked = m.select_plan(x, plans)
    assert picked == "good", picked  # doomed rejected before bump even
    m.inject_failure(x_f, amplitude=m.required_amplitude(x_f))
    picked2 = m.select_plan(x, plans)
    assert picked2 == "good", picked2


def test_select_plan_after_bump_prefers_goal():
    """With bump active, the failing plan's score is negative -> never
    selected even when it's the only candidate above min_score 0."""
    m = EnergyManifold(goal=(0.0, 0.0))
    x_f = (2.0, 2.0)
    m.inject_failure(x_f, amplitude=m.required_amplitude(x_f))
    x = (1.5, 1.5)
    # only candidate is the doomed plan; min_score 0 -> no admission
    picked = m.select_plan(x, [("doomed", x_f)], min_score=0.0)
    assert picked is None, picked


def test_qed_theorem_holds_numerically():
    """THE PROOF: max score in the failure ball flips from positive to
    negative once the obstacle bump is injected at amplitude A*."""
    r = verify_zero_repeat_guarantee()
    assert r["max_score_before"] > 0, r
    assert r["theorem_holds"] is True, r
    assert r["max_score_after_bump"] <= 0, r
    assert r["amplitude_A_star"] > 0, r


def test_required_amplitude_grows_with_score():
    """A* scales with the unconstrained score c0."""
    m1 = EnergyManifold(goal=(0.0, 0.0), eps=1e-2)
    m2 = EnergyManifold(goal=(0.0, 0.0), eps=1e-3)
    assert m2.required_amplitude((2.0, 0.0)) > m1.required_amplitude((2.0, 0.0))


ALL = [v for k, v in sorted(globals().items()) if k.startswith("test_")]


def run_all():
    passed = 0
    for t in ALL:
        t()
        passed += 1
        print(f"  ok {t.__name__}")
    print(f"\n{passed}/{len(ALL)} energy tests passed")
    return passed


if __name__ == "__main__":
    raise SystemExit(0 if run_all() == len(ALL) else 1)
