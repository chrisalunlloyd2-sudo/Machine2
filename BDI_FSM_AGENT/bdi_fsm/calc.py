"""calc.py — the cheap calculator flow (memoized, in-process, budgeted).

Chris 2026-08-15: "a lot of math, I don't want 20 processes on 1 calculation
in a Java env." Every unit of math the agent uses — decibans, logit, cosine,
Shannon entropy, the Nash threshold — provided as a single-pass, IN-PROCESS,
MEMOIZED flow. No subprocess, no numpy, deterministic.

Three levers make it cheap:
  1. memoize  — compute once, cache forever (the "store derivative" idea)
  2. small    — single-pass O(D) with no allocation where possible
  3. budget   — an op counter refuses to exceed a cap (nothing runs forever)
"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Sequence


@lru_cache(maxsize=None)
def logit(s: float) -> float:
    """[0,1] -> natural log-odds."""
    s = max(1e-9, min(1 - 1e-9, s))
    return math.log(s / (1 - s))


@lru_cache(maxsize=None)
def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


@lru_cache(maxsize=None)
def similarity_ban(s: float) -> float:
    """Cosine similarity [-1,1] -> BANS (log-odds, deciban)."""
    s = max(-0.999999, min(0.999999, s))
    return 10.0 * math.log10((1.0 + s) / (1.0 - s))


@lru_cache(maxsize=None)
def nash_threshold(c_miss: float, c_false: float) -> float:
    """theta* = log10(C_miss / C_false) bans (memoized)."""
    if c_false <= 0:
        return float("inf")
    return math.log10(c_miss / c_false)


@lru_cache(maxsize=None)
def shannon_entropy_bits(freqs: Sequence[int]) -> float:
    """Shannon entropy (bits) from a sequence of counts."""
    total = sum(freqs)
    if total <= 0:
        return 0.0
    h = 0.0
    for f in freqs:
        if f > 0:
            p = f / total
            h -= p * math.log2(p)
    return h


def cosine(a, b) -> float:
    """Single-pass cosine similarity, no allocation, O(len)."""
    dot = na = nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


class BudgetExceeded(Exception):
    pass


class CalcFlow:
    """A budgeted computation flow: every op spends from a cap.

    Enforces CORE LAW #1 ("nothing runs forever") at the arithmetic level —
    exceeding the budget raises instead of spinning. The memoized functions
    above mean repeat inputs are free (cache), not re-spent.
    """

    def __init__(self, budget: int = 1_000_000):
        self.budget = budget
        self.ops = 0

    def spend(self, n: int = 1) -> None:
        self.ops += n
        if self.ops > self.budget:
            raise BudgetExceeded(f"budget {self.budget} exceeded at {self.ops} ops")

    def ban(self, s: float) -> float:
        self.spend(1)
        return similarity_ban(s)

    def threshold(self, c_miss: float, c_false: float) -> float:
        self.spend(1)
        return nash_threshold(c_miss, c_false)

    def cosine(self, a, b) -> float:
        self.spend(len(a))
        return cosine(a, b)

    def entropy(self, freqs) -> float:
        self.spend(len(freqs))
        return shannon_entropy_bits(tuple(freqs))

    def stats(self) -> dict:
        return {"ops": self.ops, "budget": self.budget,
                "remaining": self.budget - self.ops,
                "ban_cache": similarity_ban.cache_info().currsize,
                "nash_cache": nash_threshold.cache_info().currsize}


# ═══════════════════════════════════════════════════════════════════════════════
# EXACT ARITHMETIC, and bookmarks for the maths it cannot resolve.
#
# Combined into this module 2026-08-16 (Chris: "combine them"). The two halves arrived
# independently under the same filename and do genuinely different jobs, which is exactly why
# they belong together rather than apart: this is the ONE place the agent does mathematics.
#
#   above   the EVIDENCE calculus — CalcFlow, nash_threshold, similarity_ban, shannon entropy.
#           How much a thing is believed, in bans.
#   below   the ARITHMETIC — ast-whitelisted evaluation, and a ledger of the symbolism it could
#           not resolve. What a thing actually equals.
#
# A Markov chain can emit "17 * 23 = 389" as fluently as the right answer, and a ban score says
# nothing about whether a sum is correct. Belief and value are different questions; the agent
# needs both and should not have to look in two places.
# ═══════════════════════════════════════════════════════════════════════════════

import ast
import json
import math
import operator
import os
import re
import time

# Node types an expression may contain. Anything else is refused at parse time.
_BINOPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}

# Named values and functions the agent may use. Deliberately small and mathematical: no builtins,
# no attribute access, nothing with a side effect.
_NAMES = {"pi": math.pi, "e": math.e, "tau": math.tau, "inf": math.inf}
_FUNCS = {
    "abs": abs, "round": round, "min": min, "max": max, "sum": sum,
    "sqrt": math.sqrt, "log": math.log, "log2": math.log2, "log10": math.log10,
    "exp": math.exp, "floor": math.floor, "ceil": math.ceil,
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "hypot": math.hypot, "factorial": math.factorial, "gcd": math.gcd,
}

# A power big enough to hang the box is not a calculation. 2**10_000_000 is instant to parse and
# never finishes formatting, which on a four-core Xeon is indistinguishable from a crash.
MAX_POW = 1_000_000

# Per-function argument ceilings. factorial(10_000) already has 35,660 digits; nothing anyone
# types in a chat box needs more, and every value above these is a hang rather than an answer.
_ARG_LIMITS = {"factorial": 10_000, "exp": 700, "log": 1e300, "log2": 1e300, "log10": 1e300}


BOOKMARKS = "math_bookmarks.jsonl"


class CalcError(Exception):
    """Refused, with a reason a person can act on."""


def _eval(node):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise CalcError("only numbers are allowed, got %r" % (node.value,))
        return node.value
    if isinstance(node, ast.BinOp):
        op = _BINOPS.get(type(node.op))
        if op is None:
            raise CalcError("operator not allowed: %s" % type(node.op).__name__)
        a, b = _eval(node.left), _eval(node.right)
        if op is operator.pow and (abs(b) > MAX_POW or (abs(a) > 1 and abs(b) > 4096)):
            raise CalcError("exponent too large to compute safely")
        if op in (operator.truediv, operator.floordiv, operator.mod) and b == 0:
            raise CalcError("division by zero")
        return op(a, b)
    if isinstance(node, ast.UnaryOp):
        op = _UNARY.get(type(node.op))
        if op is None:
            raise CalcError("unary operator not allowed")
        return op(_eval(node.operand))
    if isinstance(node, ast.Name):
        if node.id in _NAMES:
            return _NAMES[node.id]
        raise CalcError("unknown symbol %r" % node.id)
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _FUNCS:
            raise CalcError("unknown function")
        if node.keywords:
            raise CalcError("keyword arguments not allowed")
        args = [_eval(a) for a in node.args]
        # Guard the functions that explode on a small input, not just `**`.
        #
        # The exponent cap covered 2**99999999 and missed factorial(999999), which is four
        # characters and produces a number with millions of digits — the unit test that found this
        # took 17 seconds because it genuinely tried. On a four-core Xeon that is an outage
        # reachable from the chat box.
        limit = _ARG_LIMITS.get(node.func.id)
        if limit is not None and args and isinstance(args[0], (int, float)) \
                and abs(args[0]) > limit:
            raise CalcError("%s argument too large to compute safely (max %s)"
                            % (node.func.id, limit))
        return _FUNCS[node.func.id](*args)
    if isinstance(node, (ast.Tuple, ast.List)):
        return [_eval(e) for e in node.elts]
    raise CalcError("expression form not allowed: %s" % type(node).__name__)


def evaluate(expr):
    """Compute `expr` exactly. Returns {ok, value, expr} or {ok: False, error}."""
    text = (expr or "").strip().rstrip("=").strip()
    if not text:
        return {"ok": False, "error": "empty expression", "expr": expr}
    if len(text) > 500:
        return {"ok": False, "error": "expression too long", "expr": text[:60]}
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as e:
        return {"ok": False, "error": "not an expression: %s" % e.msg, "expr": text}
    try:
        value = _eval(tree.body)
    except CalcError as e:
        return {"ok": False, "error": str(e), "expr": text}
    except (ValueError, OverflowError, ZeroDivisionError, TypeError, RecursionError) as e:
        return {"ok": False, "error": "%s: %s" % (type(e).__name__, e), "expr": text}
    if isinstance(value, float) and value.is_integer() and abs(value) < 1e15:
        value = int(value)
    return {"ok": True, "value": value, "expr": text}


# ── finding math in language ─────────────────────────────────────────────────
# Arithmetic written inline, the shape a person types in chat.
#
# SPACES AROUND THE OPERATOR ARE REQUIRED. The first version allowed none, so "2026-08-14" parsed
# as 2026 - 8 - 14 and reported 2004 — a date silently becoming a number, injected into a reply as
# though it had been computed. Nobody writes a subtraction as "2026-08-14" and everybody writes
# dates that way, so demanding the spacing costs nothing real and removes the whole class:
# versions (1.2.3), dates, ranges (5-10) and hyphenated names all stop matching.
_EXPR_RE = re.compile(
    r"(?<![\w.])(\d[\d.,]*(?:\s+[-+*/^%]\s+\(?\s*[\d.]+\)?)+)(?![\w.])")

# Symbolism this cannot resolve but must not pretend it did not see. Each becomes a bookmark.
#
# Two of these were written wrong and quietly matched nothing, which is precisely the failure the
# bookmarks exist to prevent — a detector that never fires is indistinguishable from text that
# never contained the thing:
#   * the unit rule ended in \b, but "%" is not a word character, so "24% to 100%" required a
#     letter to follow the percent sign and never matched;
#   * the equation rule demanded [a-z0-9] straight after "=", so "H = -sum p log2 p" — the
#     canonical form in this codebase — was hidden behind its own minus sign.
_UNRESOLVED = [
    (re.compile(r"[∑∏∫√∞≈≠≤≥±∂∇⊕⊗]"), "unicode maths symbol"),
    (re.compile(r"(?<![\w.])\d+(?:\.\d+)?\s*(?:kb|mb|gb|tb|ms|hz|%)(?!\w)", re.I),
     "value with a unit"),
    (re.compile(r"(?<!\w)[A-Za-z]\s*=\s*[-+(]?\s*[A-Za-z0-9]"),
     "symbolic equation with a free variable"),
    (re.compile(r"\bO\(\s*n"), "complexity notation"),
    (re.compile(r"\d+\s*/\s*[a-z]", re.I), "rate with a named denominator"),
]


def find_math(text):
    """Every computable expression in `text`, with what could not be resolved alongside it."""
    t = text or ""
    found = []
    for m in _EXPR_RE.finditer(t):
        raw = m.group(1).strip()
        cleaned = raw.replace("^", "**").replace(",", "")
        r = evaluate(cleaned)
        found.append({"raw": raw, "ok": r["ok"],
                      "value": r.get("value"), "error": r.get("error")})
    unresolved = [{"kind": kind, "sample": rx.search(t).group(0)[:40]}
                  for rx, kind in _UNRESOLVED if rx.search(t)]
    return {"expressions": found, "unresolved": unresolved}


# ── bookmarks ────────────────────────────────────────────────────────────────
def bookmark(state_dir, source, text, reason, kind="unresolved"):
    """Record math that was seen and not resolved. Append-only; never raises into a caller.

    The point is that a gap leaves a trace. Skipping an equation silently makes text-with-maths
    indistinguishable from text-without, and then nobody can circle back because nobody knows
    there is anywhere to circle back to.
    """
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "source": str(source)[:200],
           "kind": kind, "reason": str(reason)[:200], "text": " ".join(str(text).split())[:300]}
    try:
        path = os.path.join(state_dir, BOOKMARKS)
        os.makedirs(state_dir, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return True
    except OSError:
        return False


def bookmarks(state_dir, limit=50):
    """Read the ledger back, newest last. The to-circle-back list."""
    path = os.path.join(state_dir, BOOKMARKS)
    out = []
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return out[-limit:]


def scan(text, state_dir=None, source="chat"):
    """Find, compute, and bookmark in one pass — the entry point for the chat path."""
    r = find_math(text)
    if state_dir:
        for u in r["unresolved"]:
            bookmark(state_dir, source, u["sample"], u["kind"], kind="symbolism")
        for e in r["expressions"]:
            if not e["ok"]:
                bookmark(state_dir, source, e["raw"], e["error"], kind="expression")
    return r
