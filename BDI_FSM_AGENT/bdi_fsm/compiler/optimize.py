"""optimize.py — machine-independent optimizations.

Constant folding + dead code elimination (the two classic middle-end passes).
Deterministic, stdlib-only.
"""

from __future__ import annotations

from typing import List, Tuple

from .ir import uses, _PURE


def _fold_binop(op, a, b):
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op == "*":
        return a * b
    if op == "/":
        return a // b if b != 0 else None
    if op == "%":
        return a % b if b != 0 else None
    if op == "<":
        return 1 if a < b else 0
    if op == ">":
        return 1 if a > b else 0
    if op == "<=":
        return 1 if a <= b else 0
    if op == ">=":
        return 1 if a >= b else 0
    if op == "==":
        return 1 if a == b else 0
    if op == "!=":
        return 1 if a != b else 0
    if op == "&&":
        return 1 if (a and b) else 0
    if op == "||":
        return 1 if (a or b) else 0
    return None


def _fold_unop(op, a):
    if op == "-":
        return -a
    if op == "!":
        return 0 if a else 1
    return None


def constant_fold(instrs: List[Tuple]) -> List[Tuple]:
    """Fold binop/unop/copy when operands are known constants."""
    out: List[Tuple] = []
    const = {}
    for ins in instrs:
        op = ins[0]
        if op == "const":
            out.append(ins)
            const[ins[1]] = ins[2]
        elif op == "binop":
            _, d, o, a, b = ins
            if a in const and b in const:
                v = _fold_binop(o, const[a], const[b])
                if v is not None:
                    out.append(("const", d, v))
                    const[d] = v
                    continue
            out.append(ins)
        elif op == "unop":
            _, d, o, a = ins
            if a in const:
                v = _fold_unop(o, const[a])
                if v is not None:
                    out.append(("const", d, v))
                    const[d] = v
                    continue
            out.append(ins)
        elif op == "copy":
            _, d, s = ins
            if s in const:
                out.append(("const", d, const[s]))
                const[d] = const[s]
                continue
            out.append(ins)
        else:
            out.append(ins)
    return out


def dead_code_eliminate(instrs: List[Tuple]) -> List[Tuple]:
    """Remove pure instructions whose dest temp is never used (fixpoint)."""
    instrs = list(instrs)
    changed = True
    while changed:
        changed = False
        used = set()
        for ins in instrs:
            for u in uses(ins):
                used.add(u)
        out = []
        for ins in instrs:
            if ins[0] in _PURE and ins[1] not in used:
                changed = True
                continue
            out.append(ins)
        instrs = out
    return instrs


def optimize(instrs: List[Tuple]) -> List[Tuple]:
    """constant folding then dead code elimination."""
    return dead_code_eliminate(constant_fold(instrs))
