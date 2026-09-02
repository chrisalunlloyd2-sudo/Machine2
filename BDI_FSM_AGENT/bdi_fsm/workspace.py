"""workspace.py — workspace heuristics + auto-repair of broken AST/type nodes.

Scans a workspace (repo dir) for source files with broken ASTs (parse
errors) or broken type nodes (semantic errors), reports them precisely
(file, line, col, message) and applies DETERMINISTIC, VERIFIED repairs:

    python      ast.parse -> SyntaxError report; bracket-balance repair
                (append missing closers) verified by re-parse.
    compiler    the BDI compiler grammar -> CompileError report; SEMI /
                paren / brace repairs verified by re-compile. Type errors
                (undeclared vars) are REPORTED as hints, never auto-injected
                (that would change semantics).
    html        tag-balance repair (close unclosed tags), same idea as
                rotor_codec_html.

Safety doctrine: repairs are applied ONLY when the result re-validates;
the original is always preserved as a .orig file (never overwrite the only
good state); every repair is appended to an ADD-only repair log so each run
can be checked ("we will check logs each run").

Chris 2026-08-15: v0.5.0 workspace heuristics + auto-repair. Zero LLM.
"""

from __future__ import annotations

import ast
import os
import re
from typing import Any, Dict, List, Optional

from .compiler import compile as _compile, CompileError

__all__ = ["scan_python", "scan_compiler", "scan_html", "repair_python_source",
           "repair_compiler_source", "repair_html_tags", "auto_repair_workspace",
           "WorkspaceError"]


class WorkspaceError(Exception):
    pass


# ---- scanning --------------------------------------------------------------

def scan_python(root: str) -> List[Dict[str, Any]]:
    """Every *.py under root that fails ast.parse -> precise broken-AST report."""
    broken = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in (".git", "__pycache__", "dist", "build", ".venv")]
        for fn in sorted(filenames):
            if not fn.endswith(".py"):
                continue
            path = os.path.join(dirpath, fn)
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    src = fh.read()
                ast.parse(src)
            except SyntaxError as e:
                broken.append({"file": path, "kind": "python-ast",
                               "line": e.lineno, "col": e.offset,
                               "msg": e.msg, "text": (e.text or "").strip()})
            except Exception as e:  # noqa: BLE001
                broken.append({"file": path, "kind": "python-ast",
                               "line": None, "col": None, "msg": f"read/parse: {e}"})
    return broken


def scan_compiler(root: str, extensions=(".basm", ".agent")) -> List[Dict[str, Any]]:
    """Every compiler-grammar source under root that fails compile -> report."""
    broken = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in (".git", "__pycache__", "dist", "build", ".venv")]
        for fn in sorted(filenames):
            if not fn.endswith(extensions):
                continue
            path = os.path.join(dirpath, fn)
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    src = fh.read()
                _compile(src)
            except CompileError as e:
                broken.append({"file": path, "kind": "compiler-ast",
                               "line": getattr(e, "line", None),
                               "col": getattr(e, "col", None),
                               "msg": str(e)})
            except Exception as e:  # noqa: BLE001
                broken.append({"file": path, "kind": "compiler-ast",
                               "line": None, "col": None, "msg": f"compile: {e}"})
    return broken


def scan_html(root: str) -> List[Dict[str, Any]]:
    """Every *.html under root with unbalanced tags -> report."""
    broken = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in (".git", "__pycache__", "dist", "build", ".venv")]
        for fn in sorted(filenames):
            if not fn.endswith((".html", ".htm")):
                continue
            path = os.path.join(dirpath, fn)
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    src = fh.read()
                open_tags = _open_html_tags(src)
                if open_tags:
                    broken.append({"file": path, "kind": "html-balance",
                                   "line": None, "col": None,
                                   "msg": f"unclosed tags: {open_tags}"})
            except Exception as e:  # noqa: BLE001
                broken.append({"file": path, "kind": "html-balance",
                               "line": None, "col": None, "msg": f"scan: {e}"})
    return broken


# ---- repairs ---------------------------------------------------------------

def _balance_repair(src: str, open_ch: str, close_ch: str) -> str:
    """Append missing closers for one bracket kind, ignoring brackets inside
    string literals (single/double/triple quotes handled crudely)."""
    depth = 0
    in_s = None
    i = 0
    while i < len(src):
        c = src[i]
        if in_s:
            if c == "\\":
                i += 2
                continue
            if src.startswith(in_s * 3, i):
                in_s = None
                i += 3
                continue
            if c == in_s:
                in_s = None
            i += 1
            continue
        if c in ("'", '"'):
            in_s = c
            i += 1
            continue
        if c == open_ch:
            depth += 1
        elif c == close_ch:
            depth = max(0, depth - 1)
        i += 1
    return src + close_ch * depth if depth > 0 else src


def repair_python_source(src: str) -> Dict[str, Any]:
    """Bracket-balance repair for Python source. Returns fixed source only if
    ast.parse succeeds on the repaired text and the repair actually changed
    something. Otherwise reports the reason honestly."""
    try:
        ast.parse(src)
        return {"fixed": False, "source": src, "repairs": [], "reason": "already valid"}
    except SyntaxError:
        pass
    for open_ch, close_ch in (("(", ")"), ("[", "]"), ("{", "}")):
        cand = _balance_repair(src, open_ch, close_ch)
        if cand == src:
            continue
        try:
            ast.parse(cand)
            return {"fixed": True, "source": cand,
                    "repairs": [f"closed {open_ch}{close_ch} balance"],
                    "reason": None}
        except SyntaxError:
            continue
    return {"fixed": False, "source": src, "repairs": [],
            "reason": "no safe bracket-balance repair; needs manual fix (see scan report)"}


def repair_compiler_source(src: str) -> Dict[str, Any]:
    """Deterministic repairs for the BDI compiler grammar, verified by
    re-compile: missing SEMI, missing parens/braces. Type errors reported only."""
    try:
        _compile(src)
        return {"fixed": False, "source": src, "repairs": [], "reason": "already valid"}
    except CompileError as e:
        first_err = str(e)
    # 1. missing SEMI (grammar requires per-statement SEMI)
    if not src.rstrip().endswith((";", "}")):
        cand = src.rstrip() + ";"
        try:
            _compile(cand)
            return {"fixed": True, "source": cand, "repairs": ["append ';'"],
                    "reason": None}
        except CompileError:
            pass
    # 2. bracket balance (parens + braces)
    for open_ch, close_ch in (("(", ")"), ("{", "}")):
        cand = _balance_repair(src, open_ch, close_ch)
        if cand == src:
            continue
        try:
            _compile(cand)
            return {"fixed": True, "source": cand,
                    "repairs": [f"closed {open_ch}{close_ch} balance"],
                    "reason": None}
        except CompileError:
            continue
    return {"fixed": False, "source": src, "repairs": [],
            "reason": f"no safe syntactic repair; first error: {first_err}"}


_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
         "link", "meta", "param", "source", "track", "wbr"}
_RAW = {"script", "style", "textarea"}
_TAG = re.compile(r"<(/)?([a-zA-Z][a-zA-Z0-9-]*)((?:\"[^\"]*\"|'[^']*'|[^'\">])*?)(/)?>")


def _open_html_tags(src: str) -> List[str]:
    """Tag-balance scanner. Script/style/textarea content is SKIPPED (raw text
    can contain '<' that is not a tag); self-closing '.../>' tags are void for
    balance purposes. Returns the still-open tags in document order."""
    stack = []
    i = 0
    n = len(src)
    while i < n:
        m = _TAG.match(src, i)
        if not m:
            i += 1
            continue
        closing, name, _attrs, selfclose = (m.group(1), m.group(2).lower(),
                                            m.group(3), m.group(4))
        if name in _RAW and not closing:
            end = src.find(f"</{name}", m.end())
            if end == -1:
                stack.append(name)  # genuinely unclosed raw element
            i = n if end == -1 else end + len(f"</{name}")
            continue
        if closing:
            if stack and stack[-1] == name:
                stack.pop()
        elif name not in _VOID and not selfclose:
            stack.append(name)
        i = m.end()
    return stack


def repair_html_tags(src: str) -> Dict[str, Any]:
    """Close unclosed HTML tags in reverse order (document-order correct)."""
    open_tags = _open_html_tags(src)
    if not open_tags:
        return {"fixed": False, "source": src, "repairs": [], "reason": "already balanced"}
    fixed = src + "".join(f"</{t}>" for t in reversed(open_tags))
    if not _open_html_tags(fixed):
        return {"fixed": True, "source": fixed,
                "repairs": [f"closed {t}" for t in reversed(open_tags)],
                "reason": None}
    return {"fixed": False, "source": src, "repairs": [],
            "reason": "could not balance (possibly malformed nesting)"}


# ---- workspace auto-repair -------------------------------------------------

def auto_repair_workspace(root: str, dry_run: bool = True,
                          repair_log: Optional[str] = None) -> Dict[str, Any]:
    """Scan + repair + log. ADD-only: writes .orig backup before any fix;
    never overwrites good state; every repair logged to repair_log (append)."""
    import json
    import time

    report: Dict[str, Any] = {"scanned": root, "broken": [], "repaired": [],
                              "unfixable": [], "dry_run": dry_run}
    candidates = []
    for b in scan_python(root):
        candidates.append(("python", b))
    for b in scan_compiler(root):
        candidates.append(("compiler", b))
    for b in scan_html(root):
        candidates.append(("html", b))
    seen_files = set()
    for kind, b in candidates:
        if b["file"] in seen_files:
            continue
        seen_files.add(b["file"])
        report["broken"].append({**b, "kind": kind})
        path = b["file"]
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                src = fh.read()
        except Exception as e:  # noqa: BLE001
            report["unfixable"].append({"file": path, "reason": f"read: {e}"})
            continue
        if kind == "python":
            res = repair_python_source(src)
        elif kind == "compiler":
            res = repair_compiler_source(src)
        else:
            res = repair_html_tags(src)
        if res["fixed"]:
            if not dry_run:
                with open(path + ".orig", "w", encoding="utf-8") as fh:
                    fh.write(src)
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(res["source"])
            entry = {"file": path, "repairs": res["repairs"], "dry_run": dry_run,
                     "ts": int(time.time())}
            report["repaired"].append(entry)
            if repair_log:
                with open(repair_log, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(entry) + "\n")
        else:
            report["unfixable"].append({"file": path, "reason": res["reason"]})
    return report
