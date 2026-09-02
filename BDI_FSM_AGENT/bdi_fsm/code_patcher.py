"""CODE PATCHER — AST-guided, validated, incremental code synthesis.

Chris's architectural directive (2026-08-12): never generate code via raw
`cat << 'EOF' > file` dumps or stream-and-run loops. Raw string dumps are the
biggest structural failure point in standard agent architectures:

  * Syntax / escaping drift  — shell escaping, quote nesting, and indentation
    break generated code before it ever executes.
  * No state visibility      — overwriting a whole file in one block prevents
    the FSM from knowing WHICH line/function caused a failure.
  * Token waste              — fixing one line in a 300-line class should not
    re-emit the whole file.

The alternative is structured AST mutation + targeted unified diffs, governed
by a strict execution pipeline:

      LLM generates intent
              |
              v
      AST structural patch         <- targeted diff/AST node, NOT a raw file
              |
              v
      Logic DAG validation         <- ast.parse + compile() BEFORE any disk write
              |
              v
      Tool observer / gate         <- apply diff + in-memory compile; the
                                      BanLedger scores the result (+30 dBan pass)

This module implements steps 2-4 for Python using ONLY the stdlib `ast` module
(no external tree-sitter dependency). The BanLedger integration lives in
`CodeSynthesisGate` and reuses `bayes_engine.BanLedger`, so compiler output
becomes Bayesian evidence in decibans.

Design notes (why this beats heredoc dumps):

  * AST-guided location — we locate the target node's line span via `ast`, then
    splice LINES. This preserves all original formatting (no lossy round-trip)
    while remaining structured and granular. We never regenerate a file from a
    template string.

  * Validate-before-write — the patched source is parsed AND compiled in memory
    (no shell, no file) before a single byte touches disk. A bad edit is
    rejected at the crib filter, not discovered at runtime.

  * Atomic write + rollback — a `.bak` snapshot is kept so a failed apply can
    roll back without dirtying the workspace.

  * Unified diff output — the result exposes the exact hunk changed, so the FSM
    can track edits per method/class, not per file. This is the "granular state
    visibility" a raw dump destroys.
"""

from __future__ import annotations

import ast
import difflib
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

try:
    from .bayes_engine import BanLedger, DECIBANS_PER_BAN
except ImportError:  # pragma: no cover - standalone invocation
    from bayes_engine import BanLedger, DECIBANS_PER_BAN


# ---------------------------------------------------------------------------
# Structured patch operation
# ---------------------------------------------------------------------------

VALID_ACTIONS = (
    "insert_before",          # insert payload before the node (same indent)
    "insert_after",           # insert payload after the node (same indent)
    "insert_in_method_start", # insert payload at the top of the node's body
    "replace_body",           # keep the signature, replace the whole body
    "delete",                 # remove the node (and its decorators)
)


@dataclass
class PatchOp:
    """One structured edit — an anchor-targeted diff, not a file dump.

    Example (Chris's Java field example, adapted to Python):
        PatchOp(
            target_file="app/main.py",
            action="insert_before",
            target_node="on_create",
            payload="m_bluetooth_adapter = None\n",
        )
    """
    target_file: str
    action: str
    target_node: str
    payload: str = ""

    def __post_init__(self):
        if self.action not in VALID_ACTIONS:
            raise ValueError(f"action {self.action!r} not in {VALID_ACTIONS}")
        if self.action != "delete" and not self.payload.strip():
            raise ValueError(f"{self.action} requires a non-empty payload")


# ---------------------------------------------------------------------------
# AST location (line-span lookup)
# ---------------------------------------------------------------------------

@dataclass
class NodeSpan:
    """Line span + indentation of a located AST node."""
    name: str
    kind: str                 # 'FunctionDef' | 'AsyncFunctionDef' | 'ClassDef'
    start_line: int           # 1-based, first line (including decorators)
    node_line: int            # 1-based, the def/class line itself
    end_line: int             # 1-based, last line of the node
    indent: int               # leading-space columns of the def/class line
    body_indent: int          # indentation of the first body statement
    first_stmt_line: int      # 1-based, first body statement (after docstring)
    decorator_lines: List[int] = field(default_factory=list)


def locate_node(source: str, name: str) -> Optional[NodeSpan]:
    """Find a function/method/class by name; return its line span, or None.

    None is the crib-filter signal: a patch targeting a missing node has no
    anchor, so it is eliminated before any work is attempted.
    """
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == name:
                return _span(node, source)
    return None


def _span(node, source: str) -> NodeSpan:
    lines = source.splitlines()
    decorators = [d for d in getattr(node, "decorator_list", [])
                  if hasattr(d, "lineno")]
    deco_lines = [d.lineno for d in decorators]
    start_line = min(deco_lines + [node.lineno])
    node_line = node.lineno
    end_line = getattr(node, "end_lineno", node.lineno)

    own = lines[node_line - 1] if node_line <= len(lines) else ""
    indent = len(own) - len(own.lstrip(" "))

    body = getattr(node, "body", [])
    body_indent = indent + 4
    first_stmt_line = node_line + 1
    if body:
        first = body[0]
        # skip a leading docstring when locating the first *code* statement
        if (isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)):
            first = body[1] if len(body) > 1 else None
        if first is not None and hasattr(first, "lineno"):
            fl = lines[first.lineno - 1]
            body_indent = len(fl) - len(fl.lstrip(" "))
            first_stmt_line = first.lineno

    return NodeSpan(
        name=node.name,
        kind=type(node).__name__,
        start_line=start_line,
        node_line=node_line,
        end_line=end_line,
        indent=indent,
        body_indent=body_indent,
        first_stmt_line=first_stmt_line,
        decorator_lines=deco_lines,
    )


# ---------------------------------------------------------------------------
# Patch result
# ---------------------------------------------------------------------------

@dataclass
class PatchResult:
    success: bool
    op: PatchOp
    node: Optional[NodeSpan] = None
    diff: str = ""
    error: str = ""
    touched_lines: Tuple[int, int] = (0, 0)
    backup_path: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.success


# ---------------------------------------------------------------------------
# The patcher
# ---------------------------------------------------------------------------

class CodePatcher:
    """Applies structured patch ops as validated, targeted diffs."""

    def __init__(self, root_dir: str = "."):
        self.root_dir = Path(root_dir).resolve()

    # -- public API --------------------------------------------------------

    def dry_run(self, op: PatchOp) -> Tuple[bool, str]:
        """Validate a patch entirely in memory. Returns (ok, error).

        This is the CRIB FILTER: the target file and node are located, the
        edit is built, and the result is parsed + compiled — all without a
        single disk write. The FSM can use this to score a candidate patch
        before committing to it.
        """
        path = self._resolve(op.target_file)
        if path is None:
            return False, f"file not found: {op.target_file}"
        try:
            source = path.read_text(encoding="utf-8")
        except OSError as e:
            return False, f"read failed: {e}"
        span = locate_node(source, op.target_node)
        if span is None:
            return False, f"node not found: {op.target_node}"
        new_source = self._build(source, op, span)
        if new_source is None:
            return False, "build failed"
        return self._validate(new_source, str(path))

    def apply(self, op: PatchOp) -> PatchResult:
        """Validate then write. A bad edit never touches disk."""
        path = self._resolve(op.target_file)
        if path is None:
            return PatchResult(False, op, error=f"file not found: {op.target_file}")
        try:
            source = path.read_text(encoding="utf-8")
        except OSError as e:
            return PatchResult(False, op, error=f"read failed: {e}")

        span = locate_node(source, op.target_node)
        if span is None:
            return PatchResult(False, op, error=f"node not found: {op.target_node}")

        new_source = self._build(source, op, span)
        if new_source is None:
            return PatchResult(False, op, node=span, error="build failed")

        # CRIB FILTER: validate BEFORE any disk write (in-memory, no shell)
        ok, err = self._validate(new_source, str(path))
        if not ok:
            return PatchResult(False, op, node=span,
                               error=f"validation failed: {err}")

        backup = self._backup(path)
        try:
            path.write_text(new_source, encoding="utf-8")
        except OSError as e:
            if backup:
                try:
                    backup.replace(path)  # rollback, keep workspace clean
                except OSError:
                    pass
            return PatchResult(False, op, node=span, error=f"write failed: {e}")

        diff = self._diff(source, new_source, str(path))
        return PatchResult(
            True, op, node=span, diff=diff,
            touched_lines=(span.start_line, span.end_line),
            backup_path=str(backup) if backup else None,
        )

    # -- internals ---------------------------------------------------------

    def _resolve(self, rel: str) -> Optional[Path]:
        p = (self.root_dir / rel).resolve()
        try:
            p.relative_to(self.root_dir)
        except ValueError:
            return None  # path traversal escape attempt
        return p if p.exists() else None

    def _build(self, source: str, op: PatchOp, span: NodeSpan) -> Optional[str]:
        lines = source.splitlines()
        pad = " " * span.indent
        body_pad = " " * span.body_indent

        if op.action == "insert_before":
            at = span.start_line - 1
            block = self._reindent(op.payload, pad).rstrip("\n").split("\n")
            new = lines[:at] + block + lines[at:]
        elif op.action == "insert_after":
            at = span.end_line  # 0-based index just past the node's last line
            block = self._reindent(op.payload, pad).rstrip("\n").split("\n")
            new = lines[:at] + block + lines[at:]
        elif op.action == "insert_in_method_start":
            at = span.first_stmt_line - 1
            block = self._reindent(op.payload, body_pad).rstrip("\n").split("\n")
            new = lines[:at] + block + lines[at:]
        elif op.action == "replace_body":
            at = span.node_line  # keep decorators + signature line
            block = self._reindent(op.payload, body_pad).rstrip("\n").split("\n")
            new = lines[:at] + block + lines[span.end_line:]
        elif op.action == "delete":
            new = lines[:span.start_line - 1] + lines[span.end_line:]
        else:
            return None

        trailing = "\n" if source.endswith("\n") else ""
        return "\n".join(new) + trailing

    @staticmethod
    def _reindent(text: str, pad: str) -> str:
        """Dedent payload to its common indent, then prefix `pad` (preserves
        internal relative indentation, like textwrap.dedent)."""
        lines = text.rstrip("\n").split("\n")
        indents = [len(ln) - len(ln.lstrip(" ")) for ln in lines if ln.strip()]
        common = min(indents) if indents else 0
        out = []
        for ln in lines:
            out.append("" if not ln.strip() else pad + ln[common:])
        return "\n".join(out)

    @staticmethod
    def _validate(source: str, filename: str) -> Tuple[bool, str]:
        """In-memory syntax + compile gate. No shell, no file."""
        try:
            ast.parse(source, filename=filename)
        except SyntaxError as e:
            return False, f"SyntaxError: {e.msg} (line {e.lineno})"
        try:
            compile(source, filename, "exec")
        except Exception as e:
            return False, f"compile {type(e).__name__}: {e}"
        return True, ""

    @staticmethod
    def _backup(path: Path) -> Optional[Path]:
        bak = path.with_suffix(path.suffix + ".bak")
        try:
            bak.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            return bak
        except OSError:
            return None

    @staticmethod
    def _diff(old: str, new: str, filename: str) -> str:
        d = difflib.unified_diff(
            old.splitlines(), new.splitlines(),
            fromfile=filename, tofile=filename, lineterm="",
        )
        return "\n".join(d)


# ---------------------------------------------------------------------------
# The gate: compiler output as Bayesian evidence (Banburismus)
# ---------------------------------------------------------------------------

@dataclass
class GateDecision:
    fired: bool
    result: Optional[PatchResult] = None
    hypothesis: str = ""
    dban: float = 0.0
    reason: str = ""


class CodeSynthesisGate:
    """Routes compiler output through the Bayesian BanLedger.

    Each candidate patch is a hypothesis. The crib filter (preconditions)
    eliminates impossible patches; the in-memory compiler supplies evidence;
    the gate fires when one patch clears the deciban threshold.

      compiler pass  -> +30 dBan evidence (LR = 999)  -> hypothesis locks
      compiler fail  -> contradiction (eliminate)     -> rollback, no write
    """

    def __init__(self, root_dir: str = ".", threshold_dban: Optional[float] = None,
                 pass_dban: float = 30.0, c_miss: Optional[float] = None,
                 c_false: Optional[float] = None):
        self.patcher = CodePatcher(root_dir)
        # No magic constant: when no explicit threshold is given, the stop is
        # the decision-theoretic optimum theta* = 10 * log10(C_miss/C_false),
        # with omitted costs defaulting to 100/1 (the classic 20 dBan).
        if threshold_dban is None:
            from .bayes_engine import nash_threshold_dban
            threshold_dban = nash_threshold_dban(
                100.0 if c_miss is None else c_miss,
                1.0 if c_false is None else c_false)
        self.threshold_dban = threshold_dban
        self.pass_dban = pass_dban
        self.c_miss = c_miss
        self.c_false = c_false
        lr = 10 ** (pass_dban / DECIBANS_PER_BAN)  # 10 ** 3 = 1000
        self.pass_p_h = lr / (lr + 1.0)            # ~0.999
        self.pass_p_not_h = 1.0 - self.pass_p_h    # ~0.001

    def validate_and_apply(self, op: PatchOp) -> GateDecision:
        """Single-op path: crib-filter + in-memory compile + evidence + fire."""
        ledger = BanLedger(threshold_dban=self.threshold_dban)
        ledger.register("apply_patch", prior_prob=0.5)

        result = self.patcher.apply(op)
        if result.success:
            # compiler output => high positive evidence
            ledger.observe("apply_patch", self.pass_p_h, self.pass_p_not_h)
            gate = ledger.evaluate_gate()
            score = gate[1] if gate else self.pass_dban
            return GateDecision(True, result=result, hypothesis="apply_patch",
                                dban=score, reason="validated + applied")
        # contradiction: bad code. Eliminate + rollback (already rolled back).
        ledger.eliminate("apply_patch")
        return GateDecision(False, result=result, hypothesis="apply_patch",
                            dban=float("-inf"), reason=result.error)

    def select(self, candidates: List[PatchOp]) -> GateDecision:
        """Multi-op path: score each candidate, apply the one that wins.

        This is the true Banburismus decision loop — multiple hypotheses in
        the realm, evidence concentrates the posterior, and the gate fires on
        the single dominant patch (or none if below threshold).
        """
        ledger = BanLedger(threshold_dban=self.threshold_dban)
        ids: dict = {}
        for i, op in enumerate(candidates):
            hid = f"{i}:{op.action}:{op.target_node}"
            ids[hid] = op
            ledger.register(hid, prior_prob=0.5)
            ok, err = self.patcher.dry_run(op)  # crib filter, no write
            if not ok:
                ledger.eliminate(hid)
            else:
                ledger.observe(hid, self.pass_p_h, self.pass_p_not_h)

        gate = ledger.evaluate_gate()
        if gate is None:
            return GateDecision(False, hypothesis="<none>",
                                dban=0.0, reason="no candidate cleared threshold")
        hid, score = gate
        winner = ids[hid]
        result = self.patcher.apply(winner)
        return GateDecision(result.success, result=result, hypothesis=hid,
                            dban=score,
                            reason="applied" if result.success else result.error)
