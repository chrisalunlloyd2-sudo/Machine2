"""ast.py — Abstract Syntax Tree node definitions (Syntax Analysis output).

The parser builds these; semantic analysis decorates them; IR lowering walks
them. Deterministic, stdlib-only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class Num:
    value: int


@dataclass
class Bool:
    value: bool


@dataclass
class Var:
    name: str


@dataclass
class BinOp:
    op: str   # + - * / % < > <= >= == != && ||
    left: object
    right: object


@dataclass
class UnOp:
    op: str   # - !
    operand: object


@dataclass
class Assign:
    name: str
    expr: object


@dataclass
class If:
    cond: object
    then: "Block"
    otherwise: "Block"


@dataclass
class While:
    cond: object
    body: "Block"


@dataclass
class Print:
    expr: object


@dataclass
class Block:
    statements: List[object] = field(default_factory=list)

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
