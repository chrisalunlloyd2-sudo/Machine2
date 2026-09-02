"""reachability.py — "prove you can reach the exit."

Deterministic path-reachability over the FSM state graph, with transition
GUARDS verified as boolean formulas by brute-force truth tables (the same
idea as Sophia's propositional engine, kept stdlib-only and self-contained).

For every candidate path found by BFS we report, per edge:
    TAUTOLOGY     - guard is None or always true  -> transition always fires
    SATISFIABLE   - guard formula has a model     -> transition CAN fire
    UNSAT         - guard formula has no model    -> edge is DEAD, path blocked
    RUNTIME       - guard is a callable           -> cannot statically prove;
                    existence is reported, proof deferred to execution

Chris 2026-08-15: "prove you can reach the exit" (FAQ / SMT direction).
"""

from __future__ import annotations

import itertools
import re
from collections import deque
from typing import Any, Callable, Dict, List, Optional, Tuple

__all__ = [
    "ReachabilityError", "tokenize_formula", "shunting_yard", "truth_table",
    "guard_verdict", "path_to", "verify_path", "prove_exit",
]

# ---- propositional guard formulas (tiny, stdlib-only) ---------------------

_ATOM = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_OPS = {"~": 4, "&": 3, "|": 2, "->": 1, "<->": 1}


class ReachabilityError(Exception):
    """Raised for malformed guard formulas or graphs."""


def tokenize_formula(formula: str) -> List[str]:
    """Tokenize a boolean formula: atoms, ~ & | -> <->, parens."""
    toks: List[str] = []
    i = 0
    while i < len(formula):
        c = formula[i]
        if c.isspace():
            i += 1
        elif c in "()":
            toks.append(c); i += 1
        elif formula.startswith("<->", i):
            toks.append("<->"); i += 3
        elif formula.startswith("->", i):
            toks.append("->"); i += 2
        elif c == "~":
            toks.append("~"); i += 1
        elif c == "&":
            toks.append("&"); i += 1
        elif c == "|":
            toks.append("|"); i += 1
        elif _ATOM.match(formula, i):
            m = _ATOM.match(formula, i)
            assert m is not None
            toks.append(m.group(0)); i = m.end()
        else:
            raise ReachabilityError(f"unexpected char {c!r} at {i} in {formula!r}")
    return toks


def shunting_yard(tokens: List[str]) -> List[str]:
    """Infix -> postfix (shunting-yard). ~ is right-associative unary."""
    out: List[str] = []
    stack: List[str] = []
    for t in tokens:
        if t == "(":
            stack.append(t)
        elif t == ")":
            while stack and stack[-1] != "(":
                out.append(stack.pop())
            if not stack:
                raise ReachabilityError("mismatched parens")
            stack.pop()
        elif t in _OPS:
            while stack and stack[-1] != "(" and stack[-1] in _OPS and (
                    _OPS[stack[-1]] > _OPS[t] or (
                        _OPS[stack[-1]] == _OPS[t] and t not in ("->", "<->", "~"))):
                out.append(stack.pop())
            stack.append(t)
        else:
            out.append(t)  # atom
    while stack:
        t = stack.pop()
        if t == "(":
            raise ReachabilityError("mismatched parens")
        out.append(t)
    return out


def _eval_postfix(postfix: List[str], env: Dict[str, bool]) -> bool:
    st: List[bool] = []
    for t in postfix:
        if t == "~":
            st.append(not st.pop())
        elif t in ("&", "|", "->", "<->"):
            b, a = st.pop(), st.pop()
            if t == "&":
                st.append(a and b)
            elif t == "|":
                st.append(a or b)
            elif t == "->":
                st.append((not a) or b)
            else:
                st.append(a == b)
        else:
            st.append(env.get(t, False))
    return st[0]


def truth_table(formula: str) -> Dict[str, Any]:
    """Full truth table for a guard formula.

    Returns {atoms, rows, is_tautology, is_satisfiable, models}.
    """
    toks = tokenize_formula(formula)
    post = shunting_yard(toks)
    atoms = sorted({t for t in toks if t not in _OPS and t not in "()"})
    rows: List[Tuple[Tuple[bool, ...], bool]] = []
    models = 0
    try:
        for bits in itertools.product([False, True], repeat=len(atoms)):
            env = dict(zip(atoms, bits))
            val = _eval_postfix(post, env)
            rows.append((bits, val))
            if val:
                models += 1
    except IndexError as e:
        raise ReachabilityError(f"malformed formula {formula!r}: {e}") from e
    return {
        "atoms": atoms, "rows": rows,
        "is_tautology": models == len(rows) and len(rows) > 0,
        "is_satisfiable": models > 0,
        "models": models,
    }


def guard_verdict(guard: Optional[Any]) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Classify a transition guard: TAUTOLOGY / SATISFIABLE / UNSAT / RUNTIME."""
    if guard is None:
        return "TAUTOLOGY", None
    if isinstance(guard, str):
        tt = truth_table(guard)
        if tt["is_tautology"]:
            return "TAUTOLOGY", tt
        if tt["is_satisfiable"]:
            return "SATISFIABLE", tt
        return "UNSAT", tt
    if callable(guard):
        return "RUNTIME", None
    return "RUNTIME", None


# ---- graph reachability ----------------------------------------------------

def _fsm_edges(fsm: Any) -> List[Dict[str, Any]]:
    """Flatten an FSM's transition table into edge dicts."""
    edges: List[Dict[str, Any]] = []
    for state, table in getattr(fsm, "_transitions", {}).items():
        for event, (next_state, guard) in table.items():
            edges.append({"from": state, "event": event, "to": next_state, "guard": guard})
    return edges


def path_to(fsm: Any, goal: str, start: Optional[str] = None,
            max_depth: Optional[int] = None) -> Optional[List[Dict[str, Any]]]:
    """BFS for the shortest event path start -> goal. Exact and cycle-safe.

    Returns a list of edge steps or None if unreachable. Guards are NOT
    evaluated for path search (existence), only reported (see verify_path).
    """
    edges = _fsm_edges(fsm)
    adj: Dict[str, List[Dict[str, Any]]] = {}
    for e in edges:
        adj.setdefault(e["from"], []).append(e)
    start = start or getattr(fsm, "state", None) or "IDLE"
    if start not in adj and start != goal:
        return None
    depth = max_depth if max_depth is not None else max(len(adj) + 1, 32)
    seen = {start}
    q: deque = deque([(start, [])])
    while q:
        cur, path = q.popleft()
        if cur == goal:
            return path
        if len(path) >= depth:
            continue
        for e in adj.get(cur, []):
            if e["to"] in seen:
                continue
            seen.add(e["to"])
            q.append((e["to"], path + [e]))
    return None


def verify_path(fsm: Any, goal: str, start: Optional[str] = None,
                max_depth: Optional[int] = None) -> Dict[str, Any]:
    """Prove (or disprove) reachability with per-edge guard verdicts."""
    path = path_to(fsm, goal, start, max_depth)
    if path is None:
        return {"reachable": False, "path": None, "proofs": [],
                "blocked": None, "reason": "no path in state graph"}
    proofs = []
    blocked = None
    for e in path:
        verdict, tt = guard_verdict(e["guard"])
        step = {"from": e["from"], "event": e["event"], "to": e["to"],
                "guard": e["guard"] if isinstance(e["guard"], str) else
                         ("<callable>" if e["guard"] is not None else None),
                "verdict": verdict}
        if tt is not None:
            step["models"] = tt["models"]
        proofs.append(step)
        if verdict == "UNSAT":
            blocked = step
            return {"reachable": False, "path": path, "proofs": proofs,
                    "blocked": blocked,
                    "reason": f"edge {e['from']} -{e['event']}-> {e['to']} "
                              f"guard {e['guard']!r} is UNSAT (no model)"}
    return {"reachable": True, "path": path, "proofs": proofs,
            "blocked": None, "reason": None}


def prove_exit(fsm: Any, goals: Optional[List[str]] = None,
               start: Optional[str] = None) -> Dict[str, Any]:
    """From start (default current state), prove each goal state is reachable.

    This is the 'prove you can reach the exit' check over the whole FSM.
    """
    edges = _fsm_edges(fsm)
    all_states = {e["from"] for e in edges} | {e["to"] for e in edges}
    start = start or getattr(fsm, "state", None) or "IDLE"
    if goals is None:
        # terminal states = states with no outgoing edges
        goals = sorted(s for s in all_states
                       if not any(e["from"] == s for e in edges))
    if not goals:
        return {"start": start, "goals": [], "results": {}, "all_reachable": False,
                "summary": {},
                "reason": "no terminal states exist (cyclic control loop); "
                          "call prove_exit(goals=[...]) with explicit success states"}
    results = {}
    for g in goals:
        results[g] = verify_path(fsm, g, start)
    ok = all(r["reachable"] for r in results.values())
    return {"start": start, "goals": goals, "results": results,
            "all_reachable": ok,
            "summary": {g: r["reachable"] for g, r in results.items()}}
