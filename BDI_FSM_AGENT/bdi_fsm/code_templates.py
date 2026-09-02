"""CODE TEMPLATES — the bimodal half that learns the operator's *code* patterns.

This is NOT prose chat. This is the Turing-tape / brute-force-AST-coding side.

Model (Chris directive 2026-08-12):
  "the turing tape is used in a brute force ast coding method and advances
   on tape set every success. the bdi bot should learn my code patterns as
   well. it's more of a template system really."

So the bot keeps TWO memories:

  1. chat_corpus.jsonl   -> prose (READMEs / docstrings / comments) -> MarkovChat
  2. code_corpus.jsonl   -> code templates (AST signatures + bodies) -> CodeTape

The CodeTape is a physical ordered list of code templates ("cells"). A brute-
force generator produces candidate code from the templates at/near the tape
head, validates each (compile / lint / test), and on SUCCESS calls
`tape.reward()` — which bumps that template's success counter and bubbles it
toward the head. In other words, the tape ADVANCES ON EVERY SUCCESS: proven
patterns float forward so the next brute-force attempt starts from winners.

Pure stdlib (ast + json). Zero LLM.
"""
from __future__ import annotations

import ast
import json
import os
import re
import time
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------- extraction

# languages with a native ast; everything else falls back to regex signatures
AST_LANGS = {"python", "py"}

_FN_RE = {
    "javascript": re.compile(
        r"(?:async\s+)?(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*=>)"
    ),
    "typescript": re.compile(
        r"(?:async\s+)?(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*\(([^)]*)\)\s*=>)"
    ),
    "java": re.compile(
        r"(?:public|private|protected|static|final|abstract|synchronized|\s)+\s*"
        r"[\w<>\[\],\s?]+\s+(\w+)\s*\(([^)]*)\)\s*\{"
    ),
    "c": re.compile(r"[\w\s\*]+\s+(\w+)\s*\(([^)]*)\)\s*\{"),
    "cpp": re.compile(r"[\w\s\*&:<>,]+\s+(\w+)\s*\(([^)]*)\)\s*\{"),
    "go": re.compile(r"func\s+(?:\([^)]*\)\s+)?(\w+)\s*\(([^)]*)\)"),
    "rust": re.compile(r"(?:pub\s+)?fn\s+(\w+)\s*\(([^)]*)\)"),
}


def _py_signature(node: ast.AST) -> str:
    """Render a Python callable/class signature as canonical text."""
    try:
        return ast.unparse(node)
    except Exception:
        return "?"


def _py_body(node: ast.AST) -> str:
    """Normalized body text: strip decorators/docstring for the template."""
    try:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            n = ast.FunctionDef(
                name=node.name, args=node.args, body=node.body,
                decorator_list=[], returns=node.returns,
                type_comment=getattr(node, "type_comment", None),
                type_params=getattr(node, "type_params", []))
            return ast.unparse(n)
        if isinstance(node, ast.ClassDef):
            n = ast.ClassDef(name=node.name, bases=node.bases,
                             keywords=node.keywords, body=node.body,
                             decorator_list=[])
            return ast.unparse(n)
    except Exception:
        pass
    return _py_signature(node)


def extract_python(source: str, repo: str = "", path: str = "") -> List[Dict[str, Any]]:
    """AST-extract function / class / method templates from Python source."""
    out: List[Dict[str, Any]] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return out

    for node in ast.walk(tree):
        kind = None
        name = None
        sig = None
        body = None
        doc = None
        decos: List[str] = []

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            kind = "function"
            name = node.name
            sig = ast.unparse(node.args) if hasattr(node, "args") else _py_signature(node)
            body = _py_body(node)
            doc = ast.get_docstring(node) or ""
            decos = [ast.unparse(d) for d in node.decorator_list]
        elif isinstance(node, ast.ClassDef):
            kind = "class"
            name = node.name
            sig = ", ".join(ast.unparse(b) for b in node.bases) or "(object)"
            body = _py_body(node)
            doc = ast.get_docstring(node) or ""
            decos = [ast.unparse(d) for d in node.decorator_list]

        if not kind or not name:
            continue

        out.append({
            "lang": "python",
            "kind": kind,
            "name": name,
            "signature": sig or "",
            "decorators": decos,
            "docstring": (doc or "")[:600],
            "body": (body or "")[:2000],
            "repo": repo,
            "path": path,
        })
    return out


def extract_regex(source: str, lang: str, repo: str = "", path: str = "") -> List[Dict[str, Any]]:
    """Regex fallback: pull function signatures for non-Python languages."""
    rx = _FN_RE.get(lang)
    if not rx:
        return []
    out: List[Dict[str, Any]] = []
    for m in rx.finditer(source):
        name = m.group(1) or m.group(2)
        args = m.group(3) if m.lastindex and m.lastindex >= 3 else ""
        if not name:
            continue
        # grab a small body window after the match for context
        start = m.end()
        body = source[start:start + 300].strip()
        out.append({
            "lang": lang, "kind": "function", "name": name,
            "signature": args.strip(), "decorators": [],
            "docstring": "", "body": body[:800],
            "repo": repo, "path": path,
        })
    return out


def extract_templates(source: str, lang: str, repo: str = "", path: str = "") -> List[Dict[str, Any]]:
    """Dispatch to AST (Python) or regex (others)."""
    l = (lang or "").lower()
    if l in AST_LANGS:
        return extract_python(source, repo, path)
    return extract_regex(source, l, repo, path)


# ------------------------------------------------------------------- the tape

class CodeTape:
    """Ordered tape of code templates that advances on success.

    `reward()` bumps a template's success count and re-sorts so winners float
    toward the head. `head` is the current tape cell; `advance()` / `rewind()`
    move it. The brute-force coder reads `candidates()` from the head outward.
    """

    def __init__(self, path: str = "code_tape.json"):
        self.path = path
        self.cells: List[Dict[str, Any]] = []
        self.head: int = 0
        self._load()

    # ---- persistence
    def _load(self) -> None:
        if os.path.exists(self.path):
            try:
                d = json.load(open(self.path, encoding="utf-8"))
                self.cells = d.get("cells", [])
                self.head = d.get("head", 0)
            except Exception:
                self.cells, self.head = [], 0

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as fh:
            # utf-8: templates carry real source, and source on this box carries
            # box-drawing characters and em dashes that cp1252 cannot encode.
            json.dump({"head": self.head, "cells": self.cells}, fh, indent=1,
                      default=str, ensure_ascii=False)

    # ---- keys
    @staticmethod
    def _key(t: Dict[str, Any]) -> str:
        return f"{t.get('lang')}::{t.get('kind')}::{t.get('name')}::{t.get('signature','')[:40]}"

    # ---- learn
    def learn(self, templates: List[Dict[str, Any]]) -> int:
        """Add templates (deduped). Returns number newly added."""
        seen = {self._key(t) for t in self.cells}
        added = 0
        for t in templates:
            k = self._key(t)
            if k in seen or not t.get("name"):
                continue
            t["success"] = 0
            t["last_success"] = 0
            t["key"] = k
            seen.add(k)
            self.cells.append(t)
            added += 1
        return added

    # ---- tape motion
    def advance(self, n: int = 1) -> None:
        """Move the head forward (on success)."""
        if not self.cells:
            return
        self.head = (self.head + n) % len(self.cells)

    def rewind(self, n: int = 1) -> None:
        """Move the head back (on failure / backtrack)."""
        if not self.cells:
            return
        self.head = (self.head - n) % len(self.cells)

    def seek(self, pos: int) -> None:
        if self.cells:
            self.head = pos % len(self.cells)

    def current(self) -> Optional[Dict[str, Any]]:
        return self.cells[self.head] if self.cells else None

    # ---- success
    def reward(self, key: Optional[str] = None, name: Optional[str] = None) -> bool:
        """Record a success: bump the template and float it toward the head.

        Accepts an exact `key` or a `name` (matches first template with that
        name). On success the head advances past it. Returns True if found.
        """
        idx = None
        for i, t in enumerate(self.cells):
            if key and t.get("key") == key:
                idx = i
                break
            if name and t.get("name") == name and idx is None:
                idx = i
        if idx is None:
            return False
        self.cells[idx]["success"] = self.cells[idx].get("success", 0) + 1
        self.cells[idx]["last_success"] = time.time()
        # bubble toward the head by success count (stable, descending)
        t = self.cells.pop(idx)
        rank = 0
        while rank < len(self.cells) and self.cells[rank].get("success", 0) >= t["success"]:
            rank += 1
        self.cells.insert(rank, t)
        self.advance()
        return True

    # ---- brute-force seeds
    def candidates(self, lang: Optional[str] = None, kind: Optional[str] = None,
                   name: Optional[str] = None, limit: int = 8) -> List[Dict[str, Any]]:
        """Templates ranked by success, filtered, starting from the head."""
        rows = self.cells
        if lang:
            rows = [t for t in rows if t.get("lang") == lang]
        if kind:
            rows = [t for t in rows if t.get("kind") == kind]
        if name:
            rows = [t for t in rows if name.lower() in t.get("name", "").lower()]
        rows = sorted(rows, key=lambda t: (-t.get("success", 0), t.get("name", "")))
        return rows[:limit]

    # ---- stats
    def stats(self) -> Dict[str, Any]:
        return {
            "cells": len(self.cells),
            "head": self.head,
            "successes": sum(t.get("success", 0) for t in self.cells),
            "langs": sorted({t.get("lang", "?") for t in self.cells}),
            "kinds": sorted({t.get("kind", "?") for t in self.cells}),
            "top": [f"{t.get('name')} x{t.get('success',0)}"
                    for t in sorted(self.cells, key=lambda x: -x.get("success", 0))[:5]],
        }


if __name__ == "__main__":
    # quick self-test
    src = '''
import os
@dataclass
class Point:
    """A 2D point."""
    x: float
    y: float

def dist(a: Point, b: Point) -> float:
    """Euclidean distance."""
    return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5
'''
    tpls = extract_python(src)
    print(f"extracted {len(tpls)} templates")
    tape = CodeTape(path="/tmp/tape.json")
    tape.learn(tpls)
    print("tape stats:", tape.stats())
    tape.reward(name="dist")
    tape.reward(name="dist")
    print("after 2 rewards on dist ->", tape.stats()["top"])

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
