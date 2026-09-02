"""parser.py — syntax analysis (parsing).

Verifies the token stream against the grammar and builds the AST. Recursive
descent with precedence climbing. Deterministic, stdlib-only.

Grammar (EBNF):
    program  := statement*
    statement:= 'if' '(' expr ')' block ('else' block)?
              | 'while' '(' expr ')' block
              | 'print' expr ';'
              | IDENT '=' expr ';'
    block    := '{' statement* '}'
    expr     := or
    or       := and ('||' and)*
    and      := eq ('&&' eq)*
    eq       := rel (('=='|'!=') rel)*
    rel      := add (('<'|'>'|'<='|'>=') add)*
    add      := mul (('+'|'-') mul)*
    mul      := unary (('*'|'/'|'%') unary)*
    unary    := ('-'|'!') unary | primary
    primary  := INT | TRUE | FALSE | IDENT | '(' expr ')'
"""

from __future__ import annotations

from typing import List

from . import ast
from .errors import CompileError
from .lexer import Token, tokenize


class Parser:
    def __init__(self, tokens: List[Token]):
        self.toks = tokens
        self.i = 0

    def peek(self) -> Token:
        return self.toks[self.i]

    def next(self) -> Token:
        t = self.toks[self.i]
        self.i += 1
        return t

    def expect(self, kind: str) -> Token:
        t = self.peek()
        if t.kind != kind:
            raise CompileError(f"expected {kind}, got {t.value!r}", t.line, t.col)
        return self.next()

    def parse(self) -> ast.Block:
        stmts = []
        while self.peek().kind != "EOF":
            stmts.append(self.statement())
        return ast.Block(stmts)

    def statement(self):
        t = self.peek()
        if t.kind == "IF":
            return self.if_stmt()
        if t.kind == "WHILE":
            return self.while_stmt()
        if t.kind == "PRINT":
            return self.print_stmt()
        if t.kind == "IDENT":
            name = self.next().value
            self.expect("ASSIGN")
            e = self.expr()
            self.expect("SEMI")
            return ast.Assign(name, e)
        raise CompileError(f"unexpected {t.value!r}", t.line, t.col)

    def block(self) -> ast.Block:
        self.expect("LBRACE")
        stmts = []
        while self.peek().kind != "RBRACE":
            if self.peek().kind == "EOF":
                raise CompileError("unterminated block", self.peek().line, self.peek().col)
            stmts.append(self.statement())
        self.expect("RBRACE")
        return ast.Block(stmts)

    def if_stmt(self) -> ast.If:
        self.next()  # 'if'
        self.expect("LPAREN")
        cond = self.expr()
        self.expect("RPAREN")
        then = self.block()
        otherwise = ast.Block([])
        if self.peek().kind == "ELSE":
            self.next()
            otherwise = self.block()
        return ast.If(cond, then, otherwise)

    def while_stmt(self) -> ast.While:
        self.next()
        self.expect("LPAREN")
        cond = self.expr()
        self.expect("RPAREN")
        return ast.While(cond, self.block())

    def print_stmt(self) -> ast.Print:
        self.next()
        e = self.expr()
        self.expect("SEMI")
        return ast.Print(e)

    # precedence climbing
    def expr(self):
        return self.or_expr()

    def or_expr(self):
        e = self.and_expr()
        while self.peek().kind == "OR":
            self.next()
            e = ast.BinOp("||", e, self.and_expr())
        return e

    def and_expr(self):
        e = self.eq_expr()
        while self.peek().kind == "AND":
            self.next()
            e = ast.BinOp("&&", e, self.eq_expr())
        return e

    def eq_expr(self):
        e = self.rel_expr()
        while self.peek().kind in ("EQ", "NE"):
            op = self.next()
            e = ast.BinOp(op.value, e, self.rel_expr())
        return e

    def rel_expr(self):
        e = self.add_expr()
        while self.peek().kind in ("LT", "GT", "LE", "GE"):
            op = self.next()
            e = ast.BinOp(op.value, e, self.add_expr())
        return e

    def add_expr(self):
        e = self.mul_expr()
        while self.peek().kind in ("PLUS", "MINUS"):
            op = self.next()
            e = ast.BinOp(op.value, e, self.mul_expr())
        return e

    def mul_expr(self):
        e = self.unary()
        while self.peek().kind in ("STAR", "SLASH", "PERCENT"):
            op = self.next()
            e = ast.BinOp(op.value, e, self.unary())
        return e

    def unary(self):
        if self.peek().kind in ("MINUS", "NOT"):
            op = self.next()
            return ast.UnOp(op.value, self.unary())
        return self.primary()

    def primary(self):
        t = self.next()
        if t.kind == "INT":
            return ast.Num(int(t.value))
        if t.kind == "TRUE":
            return ast.Bool(True)
        if t.kind == "FALSE":
            return ast.Bool(False)
        if t.kind == "IDENT":
            return ast.Var(t.value)
        if t.kind == "LPAREN":
            e = self.expr()
            self.expect("RPAREN")
            return e
        raise CompileError(f"unexpected {t.value!r}", t.line, t.col)


def parse(src: str) -> ast.Block:
    return Parser(tokenize(src)).parse()
