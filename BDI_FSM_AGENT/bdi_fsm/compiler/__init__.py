"""compiler — a multi-stage pipeline: source -> tokens -> AST -> IR -> assembly.

Chris 2026-08-15: "A compiler translates human-readable source code into
machine-executable instructions ... Front-End, Middle-End (Optimizer), Back-End."

    1. Front-End   lexer.py  (lexical analysis -> tokens)
                   parser.py (syntax analysis -> AST)
                   semantic.py (type checking & binding)
    2. Middle-End  ir.py      (AST -> three-address code, SSA-lite temps)
                   optimize.py (constant folding + dead code elimination)
    3. Back-End    codegen.py (instruction selection + register allocation)
                   vm.py      (tiny ISA interpreter, for end-to-end tests)

Deterministic, stdlib-only, zero-LLM.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from .errors import CompileError
from .lexer import tokenize, Token
from .parser import parse
from .semantic import analyze
from .ir import lower
from .optimize import optimize
from .codegen import generate, allocate_registers
from .vm import run

__all__ = ["CompileError", "Token", "tokenize", "parse", "analyze", "lower",
           "optimize", "generate", "allocate_registers", "run", "compile"]


class Result:
    """A full compile: source, tokens, AST, IR (opt + unopt), assembly."""

    def __init__(self, source, tokens, tree, symbols, ir, ir_opt, asm):
        self.source = source
        self.tokens = tokens
        self.tree = tree
        self.symbols = symbols
        self.ir = ir
        self.ir_opt = ir_opt
        self.asm = asm


def compile(source: str, optimize_ir: bool = True) -> Result:
    """Run the whole pipeline. Raises CompileError on any stage failure."""
    tokens = tokenize(source)
    tree = parse(source)
    symbols, _types = analyze(tree)
    ir, vars_ = lower(tree)
    ir_opt = optimize(ir) if optimize_ir else ir
    asm = generate(ir_opt, vars_)
    return Result(source, tokens, tree, symbols, ir, ir_opt, asm)
