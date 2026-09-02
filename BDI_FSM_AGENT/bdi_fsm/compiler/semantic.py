"""semantic.py — semantic analysis (type checking & binding).

Validates that operations are legal (matching types, declare-before-use) and
produces a symbol table + per-node type map decorating the AST. Deterministic,
stdlib-only.

Types: 'int' and 'bool'.
  + - * / %        : int x int -> int
  < > <= >= == !=  : int x int -> bool
  && ||            : bool x bool -> bool
  -                : int -> int
  !                : bool -> bool
  if/while cond    : bool
"""

from __future__ import annotations

from typing import Dict

from . import ast
from .errors import CompileError

_ARITH = {"+", "-", "*", "/", "%"}
_CMP = {"<", ">", "<=", ">=", "==", "!="}
_LOGIC = {"&&", "||"}


def _binop_type(op, l, r, line=None):
    if op in _ARITH:
        if l != "int" or r != "int":
            raise CompileError(f"operator '{op}' needs int operands, got {l} and {r}", line)
        return "int"
    if op in _CMP:
        if l != "int" or r != "int":
            raise CompileError(f"operator '{op}' needs int operands, got {l} and {r}", line)
        return "bool"
    if op in _LOGIC:
        if l != "bool" or r != "bool":
            raise CompileError(f"operator '{op}' needs bool operands, got {l} and {r}", line)
        return "bool"
    raise CompileError(f"unknown operator {op!r}", line)


def analyze(block: ast.Block):
    """Type-check the program. Returns (symbols, types) where types maps
    id(node) -> 'int'/'bool'. Raises CompileError on the first illegal use."""
    symbols: Dict[str, str] = {}
    types: Dict[int, str] = {}

    def expr(e) -> str:
        if isinstance(e, ast.Num):
            types[id(e)] = "int"; return "int"
        if isinstance(e, ast.Bool):
            types[id(e)] = "bool"; return "bool"
        if isinstance(e, ast.Var):
            if e.name not in symbols:
                raise CompileError(f"undefined variable {e.name!r}")
            types[id(e)] = symbols[e.name]; return symbols[e.name]
        if isinstance(e, ast.UnOp):
            t = expr(e.operand)
            if e.op == "-":
                if t != "int":
                    raise CompileError("unary '-' needs int operand")
                types[id(e)] = "int"; return "int"
            if e.op == "!":
                if t != "bool":
                    raise CompileError("unary '!' needs bool operand")
                types[id(e)] = "bool"; return "bool"
            raise CompileError(f"unknown unary {e.op!r}")
        if isinstance(e, ast.BinOp):
            lt = expr(e.left)
            rt = expr(e.right)
            t = _binop_type(e.op, lt, rt)
            types[id(e)] = t; return t
        raise CompileError(f"unknown expression {type(e).__name__}")

    def stmt(s):
        if isinstance(s, ast.Assign):
            t = expr(s.expr)
            symbols[s.name] = t
            types[id(s)] = t
        elif isinstance(s, ast.Print):
            expr(s.expr)
        elif isinstance(s, ast.If):
            if expr(s.cond) != "bool":
                raise CompileError("'if' condition must be bool")
            for x in s.then.statements:
                stmt(x)
            for x in s.otherwise.statements:
                stmt(x)
        elif isinstance(s, ast.While):
            if expr(s.cond) != "bool":
                raise CompileError("'while' condition must be bool")
            for x in s.body.statements:
                stmt(x)
        else:
            raise CompileError(f"unknown statement {type(s).__name__}")

    for s in block.statements:
        stmt(s)
    return symbols, types
