import pytest
from bdi_fsm.compiler import (compile, run, CompileError, tokenize, parse, analyze,
                              lower, optimize, allocate_registers)
from bdi_fsm.compiler.optimize import constant_fold
from bdi_fsm.compiler import ast


def test_lexer_keywords_idents_ints():
    toks = tokenize("x = 10; if (x > 3) { print x; } // comment")
    kinds = [t.kind for t in toks]
    assert "IDENT" in kinds and "INT" in kinds and "IF" in kinds and "EOF" in kinds
    # comment discarded
    assert "comment" not in " ".join(t.value for t in toks)


def test_parser_precedence():
    tree = parse("x = 1 + 2 * 3;")
    e = tree.statements[0].expr
    assert isinstance(e, ast.BinOp) and e.op == "+"
    assert isinstance(e.right, ast.BinOp) and e.right.op == "*"


def test_semantic_undefined_variable():
    with pytest.raises(CompileError):
        analyze(parse("print z;"))


def test_semantic_if_condition_must_be_bool():
    with pytest.raises(CompileError):
        analyze(parse("if (1 + 2) { print 1; }"))


def test_constant_folding():
    src = "x = 1 + 2 * 3; print x;"
    instrs, _ = lower(parse(src))
    folded = constant_fold(instrs)
    consts = [i for i in folded if i[0] == "const"]
    assert any(i[1] == "t0" and i[2] == 7 for i in consts) or \
           any(i[2] == 7 for i in consts)


def test_dead_code_elimination():
    from bdi_fsm.compiler.optimize import dead_code_eliminate
    instrs = [("const", "t0", 1), ("const", "t1", 2), ("print", "t0")]
    out = dead_code_eliminate(instrs)
    assert ("const", "t1", 2) not in out  # t1 never used


def test_end_to_end_arithmetic():
    r = compile("x = 1 + 2 * 3; print x;")
    assert run(r.asm) == [7]


def test_end_to_end_if_else():
    r = compile("x = 11; if (x > 10) { print 1; } else { print 0; }")
    assert run(r.asm) == [1]


def test_end_to_end_while_loop():
    r = compile("x = 5; s = 0; while (x > 0) { s = s + x; x = x - 1; } print s;")
    assert run(r.asm) == [15]


def test_end_to_end_boolean_and_division():
    r = compile("print (3 < 5) && (10 % 4 == 2);")
    assert run(r.asm) == [1]


def test_register_allocation_spills():
    # 4 temps live at once -> forces a spill with 3 registers
    instrs = [
        ("const", "a", 1), ("const", "b", 2), ("const", "c", 3), ("const", "d", 4),
        ("binop", "e", "+", "a", "b"),
        ("binop", "f", "+", "c", "d"),
        ("binop", "g", "+", "e", "f"),
        ("print", "g"),
    ]
    reg_map, spilled = allocate_registers(instrs, num_regs=3)
    assert len(spilled) >= 1  # at least one temp spilled


def test_compile_result_has_all_stages():
    r = compile("x = 3; print x;")
    assert r.tokens and r.tree and r.symbols and r.ir and r.asm
    assert "mov" in r.asm and "print" in r.asm and "halt" in r.asm
