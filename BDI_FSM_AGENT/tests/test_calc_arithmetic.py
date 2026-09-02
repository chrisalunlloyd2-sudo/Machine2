"""Tests for the ARITHMETIC half of bdi_fsm.calc — exact evaluation and bookmarks.

(The evidence half — bans, Nash threshold, entropy — is covered by test_calc.py.
Both live in calc.py: belief and value are different questions and the agent needs both.)

Three properties, in order of how badly getting them wrong would hurt:

  1. SAFE. This evaluates text arriving from chat. If the whitelist leaks, the chat box is a
     shell. Every refusal case below is an attempted escape.
  2. HONEST. A date must never silently become a number. "2026-08-14" parsing as 2026-8-14 = 2004
     puts a computed-looking figure into a reply that nobody computed.
  3. LOUD. Symbolism it cannot resolve must leave a bookmark. A detector that never fires is
     indistinguishable from text that never contained the thing — which is the exact failure mode
     the bookmarks exist to prevent, and two of the original rules had it.
"""
import os
import sys
import tempfile

sys.path.insert(0, r"C:\Viper\projects\BDI_FSM_AGENT")

from bdi_fsm import calc


# ── 1. correct ───────────────────────────────────────────────────────────────
def test_exact_arithmetic():
    for expr, want in [("17 * 23", 391), ("2**10", 1024), ("(1+2)*3 - 4/2", 7),
                       ("sqrt(144)", 12), ("log2(1024)", 10), ("gcd(1071, 462)", 21),
                       ("factorial(10)", 3628800)]:
        r = calc.evaluate(expr)
        assert r["ok"], (expr, r)
        assert r["value"] == want, (expr, r["value"], want)


def test_integral_floats_come_back_as_ints():
    # sqrt(144) is 12.0; reporting "12.0 files" reads like a rounding artefact.
    assert calc.evaluate("sqrt(144)")["value"] == 12
    assert isinstance(calc.evaluate("sqrt(144)")["value"], int)


def test_precision_is_preserved_where_it_matters():
    assert calc.evaluate("round(22/7, 5)")["value"] == 3.14286


# ── 2. safe ──────────────────────────────────────────────────────────────────
def test_refuses_every_escape_attempt():
    for expr in ["__import__('os').system('dir')", "open('x').read()", "[].__class__",
                 "os.getcwd()", "lambda: 1", "(1).__class__.__bases__",
                 "globals()", "exec('x=1')", "'a'*99999999"]:
        r = calc.evaluate(expr)
        assert not r["ok"], "ALLOWED: %s" % expr


def test_refuses_maths_that_would_hang_the_box():
    assert not calc.evaluate("2**99999999")["ok"]
    assert not calc.evaluate("factorial(999999)")["ok"]


def test_division_by_zero_is_an_error_not_a_crash():
    r = calc.evaluate("1/0")
    assert not r["ok"] and "zero" in r["error"]


def test_non_numbers_are_refused():
    assert not calc.evaluate("'string'")["ok"]
    assert not calc.evaluate("True")["ok"]


# ── 3. honest about what is NOT arithmetic ───────────────────────────────────
def test_a_date_is_never_computed():
    """2026-08-14 parsed as 2026 - 8 - 14 = 2004 and was reported as a computed value."""
    r = calc.find_math("version 1.2.3 released on 2026-08-14")
    assert r["expressions"] == [], r


def test_a_range_is_never_computed():
    assert calc.find_math("a range of 5-10 items")["expressions"] == []


def test_real_arithmetic_still_found():
    r = calc.find_math("the throttle is 2 * 3 seconds")
    assert len(r["expressions"]) == 1
    assert r["expressions"][0]["value"] == 6


# ── 4. loud about what it cannot resolve ─────────────────────────────────────
def test_percent_is_bookmarked():
    """The rule ended in \\b, and % is not a word character, so it never fired."""
    kinds = [u["kind"] for u in calc.find_math("coverage went from 24% to 100%")["unresolved"]]
    assert "value with a unit" in kinds


def test_free_variable_equation_is_bookmarked():
    """"H = -sum p log2 p" — the minus sign hid it from the original rule."""
    kinds = [u["kind"] for u in
             calc.find_math("entropy H = -sum p log2 p over the row")["unresolved"]]
    assert "symbolic equation with a free variable" in kinds


def test_complexity_notation_is_bookmarked():
    kinds = [u["kind"] for u in calc.find_math("complexity is O(n log n)")["unresolved"]]
    assert "complexity notation" in kinds


def test_plain_prose_bookmarks_nothing():
    r = calc.find_math("plain prose with no maths in it at all")
    assert r["expressions"] == [] and r["unresolved"] == []


def test_scan_writes_a_bookmark_that_can_be_read_back():
    d = tempfile.mkdtemp(prefix="calc_bm_")
    calc.scan("coverage went from 24% to 100%", state_dir=d, source="unit-test")
    marks = calc.bookmarks(d)
    assert marks, "nothing bookmarked"
    assert marks[-1]["source"] == "unit-test"
    assert marks[-1]["kind"] == "symbolism"


def test_bookmarks_on_a_missing_ledger_is_empty_not_an_error():
    assert calc.bookmarks(tempfile.mkdtemp(prefix="calc_none_")) == []
