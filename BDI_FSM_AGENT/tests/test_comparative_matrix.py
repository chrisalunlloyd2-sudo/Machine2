#!/usr/bin/env python3
"""Deterministic tests for ComparativeMatrix — spectral engine, zero LLM."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bdi_fsm.comparative_matrix import (
    ComparativeMatrix, cosine_sim, power_iteration, second_eigenpair,
    archive_split_by_spectrum)


def test_cosine_sim_identical_orthogonal():
    assert abs(cosine_sim([1, 0], [1, 0]) - 1.0) < 1e-9
    assert abs(cosine_sim([1, 0], [0, 1]) - 0.0) < 1e-9
    assert abs(cosine_sim([1, 1], [1, 1]) - 1.0) < 1e-9


def test_cosine_sim_scale_invariant():
    assert abs(cosine_sim([2, 4], [1, 2]) - 1.0) < 1e-9


def test_power_iteration_known_eigenpair():
    # A = [[2,0],[0,1]] -> dominant lambda=2, v=[1,0]
    A = [[2.0, 0.0], [0.0, 1.0]]
    lam, v = power_iteration(A, seed=1)
    assert abs(lam - 2.0) < 1e-6, lam
    assert abs(abs(v[0]) - 1.0) < 1e-5 and abs(v[1]) < 1e-5, v


def test_power_iteration_identity():
    A = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    lam, v = power_iteration(A, seed=3)
    assert abs(lam - 1.0) < 1e-6, lam


def test_second_eigenpair_distinct():
    A = [[3.0, 0.0, 0.0], [0.0, 2.0, 0.0], [0.0, 0.0, 1.0]]
    lam1, v1 = power_iteration(A, seed=1)
    lam2, v2 = second_eigenpair(A, lam1, v1, seed=2)
    assert abs(lam1 - 3.0) < 1e-5
    assert abs(lam2 - 2.0) < 1e-5, lam2


def test_build_two_clusters_bisects():
    """Two tight clusters -> spectral bisection separates them."""
    cm = ComparativeMatrix(seed=5)
    for i in range(4):
        cm.add(f"a{i}", {"x": 1.0, "y": 1.0, "z": 0.0})
    for i in range(4):
        cm.add(f"b{i}", {"x": 0.0, "y": 0.0, "z": 1.0})
    r = cm.build()
    assert r["items"] == 8
    split = cm._spec["bisection"]
    a_side = {split[k] for k in split if k.startswith("a")}
    b_side = {split[k] for k in split if k.startswith("b")}
    assert len(a_side) == 1 and len(b_side) == 1, split
    assert a_side != b_side, split  # the two clusters land on opposite sides


def test_centrality_ranks_core_item():
    cm = ComparativeMatrix(seed=1)
    cm.add("hub", {"a": 1, "b": 1, "c": 1, "d": 1})
    cm.add("p1", {"a": 1, "b": 1, "c": 0, "d": 0})
    cm.add("p2", {"a": 0, "b": 1, "c": 1, "d": 0})
    cm.add("p3", {"a": 0, "b": 0, "c": 1, "d": 1})
    cm.build()
    cen = cm._spec["centrality"]
    assert cen["hub"] >= cen["p1"] and cen["hub"] >= cen["p3"], cen


def test_energy_lands_in_lowest_energy_basin():
    cm = ComparativeMatrix(seed=2)
    cm.add("bad", {"a": 1, "b": 1})
    cm.add("ok", {"a": 1, "b": 1})
    cm.add("good", {"a": 1, "b": 1})
    cm.build()
    des = {"bad": 0.1, "ok": 0.5, "good": 0.9}
    e = cm.energy(desirability=des)
    assert e["basin"] == "good", e  # lowest energy = highest desirability


def test_heat_ascii_renders():
    cm = ComparativeMatrix()
    cm.add("x", {"a": 0.0, "b": 1.0})
    cm.add("y", {"a": 1.0, "b": 0.0})
    txt = cm.heat_ascii()
    assert "x" in txt and "y" in txt


def test_archive_split_by_spectrum():
    cm = ComparativeMatrix(seed=9)
    for i in range(5):
        cm.add(f"keep{i}", {"f": 1.0, "g": 1.0})
    for i in range(3):
        cm.add(f"redundant{i}", {"f": 0.0, "g": 0.0})
    split = archive_split_by_spectrum(cm)
    assert len(split["keep"]) + len(split["archive"]) == 8
    assert "spectral_gap" in split


def test_save_load_roundtrip():
    cm = ComparativeMatrix(seed=4)
    cm.add("a", {"x": 1, "y": 0})
    cm.add("b", {"x": 0, "y": 1})
    cm.build()
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "cm.json")
        cm.save(p)
        cm2 = ComparativeMatrix.load(p)
        assert cm2.items == cm.items
        assert cm2._spec == cm._spec


def test_minimal_items_note():
    cm = ComparativeMatrix()
    cm.add("only", {"x": 1})
    r = cm.build()
    assert r["items"] == 1
    assert "note" in r


ALL = [v for k, v in sorted(globals().items()) if k.startswith("test_")]


def run_all():
    passed = 0
    for t in ALL:
        t()
        passed += 1
        print(f"  ok {t.__name__}")
    print(f"\n{passed}/{len(ALL)} comparative-matrix tests passed")
    return passed


if __name__ == "__main__":
    raise SystemExit(0 if run_all() == len(ALL) else 1)
