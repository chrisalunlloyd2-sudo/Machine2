import ast
import pytest

from bdi_fsm.rotor_codec import (
    ROTOR_NAMES, brute_find, generate_program, key_to_enigma,
    plain_enumerate, rotor_permutation,
)

GRAMMAR = ["return a + b", "return a - b", "return a * b", "return a / b",
           "return a ** b", "return a + a", "return b + b", "return a * a",
           "return b * b", "return a", "return b", "return a + 1", "return b - 1"]

def _mult_crib(src):
    ns = {}
    try:
        exec(src, ns)
    except Exception:
        return 0.0
    f = ns.get("f")
    if not callable(f):
        return 0.0
    tests = [(3, 4, 12), (2, 5, 10), (7, 6, 42), (0, 9, 0), (5, 5, 25)]
    return sum(1 for a, b, want in tests if f(a, b) == want) / len(tests)

def test_rotor_permutation_is_a_valid_permutation():
    n = len(GRAMMAR)
    for key in range(20):
        p = rotor_permutation(n, key)
        assert sorted(p) == list(range(n)), f"key {key} not a permutation: {p}"

def test_rotor_permutation_collision_free():
    n = len(GRAMMAR)
    seen = {tuple(rotor_permutation(n, k)) for k in range(50)}
    assert len(seen) == 50, "distinct keys must give distinct permutations"

def test_key_to_enigma_deterministic():
    e1 = key_to_enigma(12345)
    e2 = key_to_enigma(12345)
    assert e1.positions() == e2.positions()

def test_generate_program_always_compiles():
    for key in range(100):
        src = generate_program(GRAMMAR, key, signature="def f(a, b):")
        ast.parse(src)  # must never emit invalid Python

def test_brute_find_finds_multiply():
    res = brute_find(GRAMMAR, _mult_crib, signature="def f(a, b):")
    assert res["found"] is True
    assert "return a * b" in res["source"]
    assert res["theta_bans"] > 0  # Nash stop threshold present

def test_plain_enumerate_finds_multiply():
    res = plain_enumerate(GRAMMAR, _mult_crib, signature="def f(a, b):")
    assert res["found"] is True
    assert "return a * b" in res["source"]

def test_plain_enumerate_is_no_fail():
    # a crib that nothing can satisfy still terminates cleanly
    res = plain_enumerate(GRAMMAR, lambda src: 0.0, signature="def f(a, b):")
    assert res["found"] is False and res["reason"] == "exhausted"
