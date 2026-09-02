"""FOUNDRY KERNEL — the Deterministic Formal Kernel.

Implements the binding doctrine: 1990s BDI agents that never make code
twice, never make mistakes twice, operate over a pre-generated syntax
foundry, and behave as an infinite math dictionary.

1. UNIVERSAL OPERATOR DICTIONARY (Ω)
   Every programming construct maps to an invariant Gödel-style operator
   code (primes). A program is a graph G = (V, E) over Ω — vertices are
   operators + operands, edges are flow/scoping. Language is a rendering
   surface: the logic is invariant, the syntax is a 1-to-1 transform.

2. CANONICAL NORMALIZATION + GLOBAL HASH INDEX
   Every synthesized graph is normalized (alpha-renaming of variables by
   first-appearance order + recursive topological ordering of children),
   then hashed: H = sha256(Normalize(G)). Before any plan is constructed,
   the BDI option generator queries the global foundry index; an existing
   H binds the pre-verified node instantly. ZERO-REDUNDANCY GUARANTEE.

3. WEAKEST-PRECONDITION FAILURE GUARDS
   On failure at node N under belief state B_fail, extract the failing
   condition and permanently mutate the plan node's precondition:
       Plan.Precondition := Plan.Precondition ∧ ¬(fail-condition)
   Unification under B_fail then evaluates to FALSE forever. The system
   is MATHEMATICALLY INCAPABLE of re-picking that plan in that context.

Pure stdlib, deterministic, zero LLM. The transpiler is the only
"code generation" — and it is a pure function of the invariant graph.
"""

import hashlib
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

# ---- 1. Universal Operator Dictionary (Ω) ------------------------------
# Gödel-style prime codes: invariant across languages.
OMEGA = {
    "LOAD_CONST": 2, "LOAD_VAR": 3, "STORE": 5, "ASSIGN": 7,
    "ADD": 11, "SUB": 13, "MUL": 17, "DIV": 19, "MOD": 23,
    "COMPARE": 29, "AND": 31, "OR": 37, "NOT": 41,
    "CALL": 43, "IF": 47, "LOOP": 53, "RETURN": 59, "SEQ": 61,
    "NOP": 67,
}
CODE_TO_OP = {v: k for k, v in OMEGA.items()}

# language rendering tables (pure 1-to-1 syntax maps)
_LANG_SYNTAX = {
    "python": {"and": "and", "or": "or", "not": "not",
               "if": "if", "else": "else", "loop": "while", "true": "True",
               "false": "False", "nil": "None"},
    "pseudo": {"and": "AND", "or": "OR", "not": "NOT",
               "if": "IF", "else": "ELSE", "loop": "WHILE", "true": "TRUE",
               "false": "FALSE", "nil": "NULL"},
    "json": {"and": "and", "or": "or", "not": "not",
             "if": "if", "else": "else", "loop": "loop", "true": "true",
             "false": "false", "nil": "null"},
}


class GraphNode:
    """One vertex in the program graph: operator + operands/children."""

    def __init__(self, op: str, children: Optional[List["GraphNode"]] = None,
                 value: Any = None, name: Optional[str] = None):
        assert op in OMEGA, f"unknown operator {op}"
        self.op = op
        self.children = list(children or [])
        self.value = value          # literal for LOAD_CONST
        self.name = name            # identifier for LOAD_VAR/CALL/STORE

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"op": self.op, "godel": OMEGA[self.op]}
        if self.children:
            d["children"] = [c.to_dict() for c in self.children]
        if self.value is not None:
            d["value"] = self.value
        if self.name is not None:
            d["name"] = self.name
        return d

    def __repr__(self) -> str:
        return f"<{self.op} {self.name or ''}>"


# ---- 2. Canonical normalization + hashing ------------------------------
def normalize(node: Dict[str, Any]) -> Dict[str, Any]:
    """Canonical form: alpha-rename variables by first-appearance order,
    recursively topologically order children by their canonical hash."""
    renaming: Dict[str, str] = {}
    counter = [0]

    def _rename(ident: str) -> str:
        if ident not in renaming:
            renaming[ident] = f"v{counter[0]}"
            counter[0] += 1
        return renaming[ident]

    def _norm(n: Dict[str, Any]) -> Dict[str, Any]:
        out: Dict[str, Any] = {"op": n["op"]}
        if n.get("value") is not None:
            out["value"] = n["value"]
        if n.get("name") is not None and n["op"] in ("LOAD_VAR", "STORE", "ASSIGN"):
            out["name"] = _rename(n["name"])       # alpha-rename variables
        elif n.get("name") is not None:
            out["name"] = n["name"]                 # function names semantic
        ch = [_norm(c) for c in n.get("children", [])]
        if ch:
            out["children"] = sorted(ch, key=lambda c: json.dumps(
                c, sort_keys=True, separators=(",", ":")))
        return out

    return _norm(node)


def graph_hash(node: Dict[str, Any]) -> str:
    """H = sha256(Normalize(G)) — the canonical fingerprint."""
    canon = normalize(node)
    blob = json.dumps(canon, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


# ---- 3. The Foundry Registry -------------------------------------------
class FoundryRegistry:
    """Global dedup index: H -> pre-verified execution node."""

    def __init__(self, path: Optional[str] = None):
        self.path = path or "foundry_index.json"
        self.index: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.path):
            try:
                self.index = json.load(open(self.path))
            except (json.JSONDecodeError, OSError):
                self.index = {}

    def save(self) -> None:
        with open(self.path, "w") as f:
            json.dump(self.index, f, indent=1)

    def lookup(self, h: str) -> Optional[Dict[str, Any]]:
        return self.index.get(h)

    def register(self, node: Dict[str, Any], source: str = "synthesis",
                 verified: bool = False) -> Dict[str, Any]:
        """Query-then-insert: if H exists, bind the pre-verified node
        (ZERO-REDUNDANCY). Else add with the operator graph attached."""
        h = graph_hash(node)
        existing = self.index.get(h)
        if existing:
            existing["hits"] = existing.get("hits", 0) + 1
            existing["verified"] = existing.get("verified", False) or verified
            self.save()
            return {"hash": h, "existing": True, "record": existing}
        rec = {"hash": h, "first_seen": time.time(), "source": source,
               "verified": verified, "hits": 1, "graph": node}
        self.index[h] = rec
        self.save()
        return {"hash": h, "existing": False, "record": rec}

    def dedup_count(self) -> int:
        return sum(1 for r in self.index.values() if r.get("hits", 1) > 1)

    # ---- failure guard mutation (never mistake twice) ------------------
    def apply_failure_guard(self, h: str, fail_condition: str) -> Optional[Dict[str, Any]]:
        """Plan.Precondition := Plan.Precondition ∧ ¬(fail-condition).
        Persistent: unification under the failing state is FALSE forever."""
        rec = self.index.get(h)
        if not rec:
            return None
        guards = rec.setdefault("guards", [])
        if fail_condition not in guards:
            guards.append(fail_condition)
            rec["guards_updated"] = time.time()
            self.save()
        return rec

    def is_blocked(self, h: str, state: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Unification check: FALSE under B_fail if any guard's condition
        holds in the current belief state. Deterministic predicate eval:
        guard 'X' blocks iff state.get(X) is truthy."""
        rec = self.index.get(h)
        if not rec:
            return False, None
        for g in rec.get("guards", []):
            if state.get(g):
                return True, g
        return False, None


# ---- 4. Deterministic Transpiler T(G, lang) ----------------------------
def transpile(node: Dict[str, Any], lang: str = "python", indent: int = 0) -> str:
    """Pure function: invariant graph -> target-language source."""
    pad = "    " * indent
    s = _LANG_SYNTAX.get(lang, _LANG_SYNTAX["pseudo"])
    op = node["op"]

    if op == "LOAD_CONST":
        v = node.get("value")
        if isinstance(v, str):
            return f'"{v}"'
        if isinstance(v, bool):
            return s["true"] if v else s["false"]
        return str(v)
    if op == "LOAD_VAR":
        return node.get("name", "?")
    if op in ("ADD", "SUB", "MUL", "DIV", "MOD", "COMPARE", "AND", "OR"):
        a, b = node["children"]
        sym = {"ADD": "+", "SUB": "-", "MUL": "*", "DIV": "/", "MOD": "%",
               "COMPARE": "==", "AND": s["and"], "OR": s["or"]}[op]
        return f"{transpile(a, lang)} {sym} {transpile(b, lang)}"
    if op == "NOT":
        return f"{s['not']} {transpile(node['children'][0], lang)}"
    if op == "CALL":
        args = ", ".join(transpile(c, lang) for c in node.get("children", []))
        return f"{node.get('name', 'f')}({args})"
    if op == "ASSIGN":
        tgt, val = node["children"]
        return f"{transpile(tgt, lang)} = {transpile(val, lang)}"
    if op == "STORE":
        return f"{s['nil']}  # store {node.get('name')}"
    if op == "RETURN":
        c = node["children"][0] if node.get("children") else ""
        return f"{pad}return {transpile(c, lang)}" if c else f"{pad}return"
    if op == "IF":
        cond, then, els = node["children"]
        out = [f"{pad}{s['if']} {transpile(cond, lang)}:",
               transpile(then, lang, indent + 1)]
        if els and els.get("op") != "NOP":
            out.append(f"{pad}{s['else']}:")
            out.append(transpile(els, lang, indent + 1))
        return "\n".join(out)
    if op == "LOOP":
        cond, body = node["children"]
        return (f"{pad}{s['loop']} {transpile(cond, lang)}:\n"
                + transpile(body, lang, indent + 1))
    if op == "SEQ":
        return "\n".join(transpile(c, lang, indent) for c in node["children"])
    return f"{pad}pass  # {op}"


# ---- convenience builders ----------------------------------------------
def build_expr(kind: str, *args: Any) -> GraphNode:
    """Builder helpers for common expression shapes."""
    if kind == "add":
        return GraphNode("ADD", [GraphNode("LOAD_CONST", value=args[0]),
                                 GraphNode("LOAD_CONST", value=args[1])])
    if kind == "var_add":
        a, b = args
        return GraphNode("ADD", [GraphNode("LOAD_VAR", name=a),
                                 GraphNode("LOAD_VAR", name=b)])
    if kind == "call":
        name, arg_nodes = args[0], args[1]
        return GraphNode("CALL", children=arg_nodes, name=name)
    if kind == "assign_var":
        name, expr = args
        return GraphNode("ASSIGN", [GraphNode("STORE", name=name), expr])
    raise ValueError(kind)
