"""ir.py — IR lowering: AST -> three-address code (SSA-lite temps).

Each computed value gets a fresh single-assignment temp (t0, t1, ...); named
variables are memory locations (store/load). Control flow uses label + branch /
jump, i.e. basic blocks. Deterministic, stdlib-only.

IR instruction shapes (tuples):
  ("const", dest, value)          dest = value
  ("binop", dest, op, a, b)       dest = a op b
  ("unop",  dest, op, a)          dest = op a
  ("load",  dest, var)            dest = var (memory read)
  ("store", var, src)             var = src (memory write)
  ("copy",  dest, src)            dest = src
  ("branch", cond, tlabel, flabel)
  ("jump", label)
  ("label", name)
  ("print", src)
"""

from __future__ import annotations

from typing import List, Tuple

from . import ast
from .errors import CompileError

_PURE = ("const", "binop", "unop", "load", "copy")


def dest(instr: Tuple) -> str:
    op = instr[0]
    if op in _PURE:
        return instr[1]
    return None


def uses(instr: Tuple) -> List[str]:
    """Temp operands of an instruction (for liveness / register allocation)."""
    op = instr[0]
    if op == "const":
        return []
    if op == "binop":
        return [instr[3], instr[4]]
    if op == "unop":
        return [instr[3]]
    if op == "load":
        return []
    if op == "store":
        return [instr[2]]
    if op == "copy":
        return [instr[2]]
    if op == "branch":
        return [instr[1]]
    if op == "print":
        return [instr[1]]
    return []


class Lowerer:
    def __init__(self):
        self.instrs: List[Tuple] = []
        self.tmp = 0
        self.label = 0
        self.vars: List[str] = []

    def fresh_tmp(self) -> str:
        t = f"t{self.tmp}"
        self.tmp += 1
        return t

    def fresh_label(self, prefix: str = "L") -> str:
        l = f"{prefix}{self.label}"
        self.label += 1
        return l

    def emit(self, *instr):
        self.instrs.append(instr)

    def lower(self, block: ast.Block):
        for s in block.statements:
            self.stmt(s)
        return self.instrs, self.vars

    def stmt(self, s):
        if isinstance(s, ast.Assign):
            t = self.expr(s.expr)
            if s.name not in self.vars:
                self.vars.append(s.name)
            self.emit("store", s.name, t)
        elif isinstance(s, ast.Print):
            self.emit("print", self.expr(s.expr))
        elif isinstance(s, ast.If):
            c = self.expr(s.cond)
            tl = self.fresh_label("then")
            el = self.fresh_label("else")
            en = self.fresh_label("end")
            self.emit("branch", c, tl, el)
            self.emit("label", tl)
            for x in s.then.statements:
                self.stmt(x)
            self.emit("jump", en)
            self.emit("label", el)
            for x in s.otherwise.statements:
                self.stmt(x)
            self.emit("label", en)
        elif isinstance(s, ast.While):
            top = self.fresh_label("top")
            body = self.fresh_label("body")
            en = self.fresh_label("wend")
            self.emit("label", top)
            c = self.expr(s.cond)
            self.emit("branch", c, body, en)
            self.emit("label", body)
            for x in s.body.statements:
                self.stmt(x)
            self.emit("jump", top)
            self.emit("label", en)
        else:
            raise CompileError(f"unknown statement {type(s).__name__}")

    def expr(self, e) -> str:
        if isinstance(e, ast.Num):
            t = self.fresh_tmp()
            self.emit("const", t, e.value)
            return t
        if isinstance(e, ast.Bool):
            t = self.fresh_tmp()
            self.emit("const", t, 1 if e.value else 0)
            return t
        if isinstance(e, ast.Var):
            t = self.fresh_tmp()
            self.emit("load", t, e.name)
            return t
        if isinstance(e, ast.UnOp):
            a = self.expr(e.operand)
            t = self.fresh_tmp()
            self.emit("unop", t, e.op, a)
            return t
        if isinstance(e, ast.BinOp):
            a = self.expr(e.left)
            b = self.expr(e.right)
            t = self.fresh_tmp()
            self.emit("binop", t, e.op, a, b)
            return t
        raise CompileError(f"unknown expression {type(e).__name__}")


def lower(block: ast.Block):
    return Lowerer().lower(block)

# LOCATIONS - this file lives in more than one place
#
#   live:  C:\Viper\projects\BDI_FSM_AGENT
#          -> C:\Users\viper\gan-otg-db\BDI_FSM_AGENT
#   mirror: J:\ViperVault\code\projects\BDI_FSM_AGENT
#   mirror: C:\Users\viper\gan-otg-db\BDI_FSM_AGENT
#
#   live detail (freshness, git coverage): docs\LOCATIONS.md
#   regenerate: python location_stamp.py apply
# end LOCATIONS
