"""lexer.py — lexical analysis (scanning/tokenization).

Breaks raw source text into a token stream (keywords, identifiers, operators,
literals) while discarding whitespace and comments. Deterministic, stdlib-only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .errors import CompileError

KEYWORDS = {"if", "else", "while", "print", "true", "false"}

_OPS2 = {"<=": "LE", ">=": "GE", "==": "EQ", "!=": "NE", "&&": "AND", "||": "OR"}
_OPS1 = {"+": "PLUS", "-": "MINUS", "*": "STAR", "/": "SLASH", "%": "PERCENT",
         "<": "LT", ">": "GT", "=": "ASSIGN", "!": "NOT"}
_PUNCT = {"{": "LBRACE", "}": "RBRACE", "(": "LPAREN", ")": "RPAREN", ";": "SEMI"}


@dataclass
class Token:
    kind: str
    value: str
    line: int
    col: int

    def __repr__(self) -> str:
        return f"Token({self.kind}, {self.value!r})"


def tokenize(src: str) -> List[Token]:
    tokens: List[Token] = []
    i, n = 0, len(src)
    line, col = 1, 1
    while i < n:
        c = src[i]
        if c in " \t\r":
            i += 1; col += 1; continue
        if c == "\n":
            i += 1; line += 1; col = 1; continue
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            while i < n and src[i] != "\n":   # line comment
                i += 1; col += 1
            continue
        if c.isdigit():
            j = i
            while j < n and src[j].isdigit():
                j += 1
            tokens.append(Token("INT", src[i:j], line, col))
            col += j - i; i = j; continue
        if c.isalpha() or c == "_":
            j = i
            while j < n and (src[j].isalnum() or src[j] == "_"):
                j += 1
            word = src[i:j]
            kind = word.upper() if word in KEYWORDS else "IDENT"
            tokens.append(Token(kind, word, line, col))
            col += j - i; i = j; continue
        two = src[i:i + 2]
        if two in _OPS2:
            tokens.append(Token(_OPS2[two], two, line, col))
            i += 2; col += 2; continue
        if c in _OPS1:
            tokens.append(Token(_OPS1[c], c, line, col))
            i += 1; col += 1; continue
        if c in _PUNCT:
            tokens.append(Token(_PUNCT[c], c, line, col))
            i += 1; col += 1; continue
        raise CompileError(f"unexpected character {c!r}", line, col)
    tokens.append(Token("EOF", "", line, col))
    return tokens
