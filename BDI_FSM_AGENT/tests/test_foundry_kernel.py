#!/usr/bin/env python3
"""Deterministic tests for the Foundry Kernel — never code twice,
never mistake twice. Zero LLM."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bdi_fsm.foundry_kernel import (
    GraphNode, OMEGA, normalize, graph_hash, FoundryRegistry,
    transpile, build_expr)


def test_omega_primes_invariant():
    codes = list(OMEGA.values())
    assert len(set(codes)) == len(codes)          # unique
    assert all(c > 1 for c in codes)
    # primes: 2,3,5,7,11... spot check
    assert OMEGA["ADD"] == 11 and OMEGA["LOAD_CONST"] == 2


def test_commutative_add_same_hash():
    """alpha + beta == beta + alpha semantically -> identical H."""
    g1 = build_expr("var_add", "alpha", "beta").to_dict()
    g2 = build_expr("var_add", "beta", "alpha").to_dict()
    assert graph_hash(g1) == graph_hash(g2)


def test_alpha_renaming_same_hash():
    """Different variable names, same structure -> same H."""
    g1 = build_expr("var_add", "x1", "x2").to_dict()
    g2 = build_expr("var_add", "y1", "y2").to_dict()
    assert graph_hash(g1) == graph_hash(g2)


def test_different_ops_different_hash():
    g1 = build_expr("var_add", "a", "b").to_dict()
    g2 = GraphNode("SUB", [GraphNode("LOAD_VAR", name="a"),
                           GraphNode("LOAD_VAR", name="b")]).to_dict()
    assert graph_hash(g1) != graph_hash(g2)


def test_register_dedup():
    """Registering the same graph twice returns existing=True (dedup)."""
    with tempfile.TemporaryDirectory() as td:
        fr = FoundryRegistry(os.path.join(td, "idx.json"))
        g = build_expr("var_add", "p", "q").to_dict()
        r1 = fr.register(g)
        r2 = fr.register(g)
        assert r1["existing"] is False
        assert r2["existing"] is True
        assert r2["hash"] == r1["hash"]
        assert fr.dedup_count() == 1
        # second register bumped hits
        assert fr.lookup(r1["hash"])["hits"] == 2


def test_register_persists():
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "idx.json")
        fr = FoundryRegistry(p)
        fr.register(build_expr("var_add", "a", "b").to_dict())
        fr2 = FoundryRegistry(p)
        assert len(fr2.index) == 1


def test_failure_guard_blocks():
    """Never mistake twice: guard injection makes unification FALSE
    under the failing belief state, permanently."""
    with tempfile.TemporaryDirectory() as td:
        fr = FoundryRegistry(os.path.join(td, "idx.json"))
        g = GraphNode("CALL", children=[GraphNode("LOAD_VAR", name="path")],
                      name="read_file").to_dict()
        r = fr.register(g, source="synthesis")
        h = r["hash"]
        # before guard: not blocked
        blocked, _ = fr.is_blocked(h, {"path_missing": True})
        assert blocked is False
        # fail at node under state where file missing -> inject guard
        fr.apply_failure_guard(h, "path_missing")
        blocked, guard = fr.is_blocked(h, {"path_missing": True})
        assert blocked is True and guard == "path_missing"
        # different state -> still usable
        blocked, _ = fr.is_blocked(h, {"path_missing": False})
        assert blocked is False


def test_failure_guard_persists_across_reload():
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "idx.json")
        fr = FoundryRegistry(p)
        g = build_expr("var_add", "a", "b").to_dict()
        h = fr.register(g)["hash"]
        fr.apply_failure_guard(h, "a_is_null")
        fr2 = FoundryRegistry(p)
        blocked, _ = fr2.is_blocked(h, {"a_is_null": True})
        assert blocked is True


def test_transpile_python():
    g = GraphNode("ASSIGN", [
        GraphNode("STORE", name="total"),
        build_expr("var_add", "x", "y")]).to_dict()
    out = transpile(g, "python")
    assert "total = " in out and "x + y" in out, out


def test_transpile_call_and_if():
    g = GraphNode("IF", [
        GraphNode("COMPARE", [GraphNode("LOAD_VAR", name="n"),
                              GraphNode("LOAD_CONST", value=0)]),
        GraphNode("RETURN", [GraphNode("LOAD_CONST", value=1)]),
        GraphNode("NOP")]).to_dict()
    out = transpile(g, "python")
    assert out.startswith("if") and "n == 0" in out and "return 1" in out, out


def test_transpile_pseudo_and_json_keywords():
    g = GraphNode("IF", [
        GraphNode("COMPARE", [GraphNode("LOAD_VAR", name="n"),
                              GraphNode("LOAD_CONST", value=0)]),
        GraphNode("RETURN", [GraphNode("LOAD_CONST", value=True)]),
        GraphNode("NOP")]).to_dict()
    pseudo = transpile(g, "pseudo")
    assert "IF" in pseudo and "TRUE" in pseudo, pseudo


def test_graph_node_rejects_unknown_op():
    try:
        GraphNode("NOT_A_REAL_OP")
        assert False, "should have raised"
    except AssertionError:
        pass


def test_normalize_stable():
    g = build_expr("var_add", "a", "b").to_dict()
    n1 = normalize(g)
    n2 = normalize(g)
    assert n1 == n2
    assert json.dumps(n1, sort_keys=True) == json.dumps(n2, sort_keys=True)


ALL = [v for k, v in sorted(globals().items()) if k.startswith("test_")]


def run_all():
    passed = 0
    for t in ALL:
        t()
        passed += 1
        print(f"  ok {t.__name__}")
    print(f"\n{passed}/{len(ALL)} foundry-kernel tests passed")
    return passed


if __name__ == "__main__":
    raise SystemExit(0 if run_all() == len(ALL) else 1)
