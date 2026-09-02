"""
CAPABILITY ROUTER — the FSM agent handles ALL LLM tasks EXCEPT English language
creation.

Chris directive 2026-08-11: "we should be making bdi fsm capable of all llm
tasks except English language creation."

- classify(task) -> capability name | 'english' | None
- The FSM agent deterministically handles: code transpile/render, normalize+dedup,
  failure guards, decisions, goal planning, task routing, verification, search,
  math, self-heal (telemetry), learning, memory/journal.
- ENGLISH CREATION (chat replies, emails, essays, poems, stories, summaries in
  prose) is the ONLY task class that defers to the local LLM (:5001) or a human.
  Per the no-cloud rule, it never touches a cloud LLM.

handle(task) returns:
    {"handled": True,  "capability": ..., "result": ...}
    {"handled": False, "reason": "english", "defer": "llm"}
    {"handled": False, "reason": "unknown", "defer": "ask"}
"""

import ast
import operator
import os
import re

# --- English-creation patterns (the ONLY deferred class) -----------------
ENGLISH_PATTERNS = [
    r"write\s+(an?\s+)?(email|letter|essay|poem|story|blog|post|article|note|reply|message)",
    r"compose\s+(a\s+)?(message|email|letter|poem)",
    r"(chat|converse|small[- ]talk)",
    r"reply\s+to\s+(him|her|them|the\s+email)",
    r"summarize\s+.*\b(paragraph|english|prose|in\s+words)\b",
    r"(creative|fiction|lyrics|headline|tagline|slogan|caption)",
    r"draft\s+(a\s+)?(email|letter|memo|notice)",
]

# --- task type -> capability keyword map ---------------------------------
CAPABILITY_KEYWORDS = {
    "transpile": ["transpile", "translate code", "render to", "generate code",
                  "emit code", "spec to", "output code for"],
    "normalize": ["normalize", "canonical", "dedup", "hash", "deduplicate"],
    "guard": ["guard", "precondition", "never mistake", "block failure",
              "failure guard", "weakest"],
    "decide": ["decide", "choose", "which option", "pick one", "select the"],
    "plan": ["plan", "achieve", "execute goal", "run goal", "decompose"],
    "route": ["route", "next task", "which task", "schedule", "assign"],
    "verify": ["verify", "check", "compile", "test", "lint", "validate", "audit"],
    "search": ["find", "search", "grep", "locate", "where is", "list files"],
    "math": ["math", "calculate", "compute", "sum ", "multiply", "divide"],
    "heal": ["heal", "restart", "stabilize", "fix server", "memory pressure",
             "disk low", "telemetry", "server down"],
    "learn": ["learn", "train", "improve", "adapt", "update lexicon"],
    "remember": ["remember", "store", "save this", "journal", "record"],
    "summarize_log": ["summarize log", "log stats", "count spans", "trace stats"],
    "english_render": ["render decision tree", "english tree", "sentence tree"],
    "list": ["list all", "list", "show all", "show me", "display", "enumerate",
             "get all", "print all", "all details", "describe", "what do you know"],
}

_SAFE_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
    ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos,
}


def safe_math(expr: str) -> float:
    """Deterministic safe arithmetic (AST whitelist, no eval of raw strings)."""
    tree = ast.parse(expr, mode="eval")

    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError(f"bad const {node.value!r}")
        if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_OPS:
            return _SAFE_OPS[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_OPS:
            return _SAFE_OPS[type(node.op)](_eval(node.operand))
        raise ValueError(f"unsupported node {type(node).__name__}")

    return _eval(tree)


def safe_math_strip(expr: str) -> float:
    """safe_math with leading/trailing whitespace stripped (ast.parse in eval
    mode rejects leading indentation)."""
    return safe_math(expr.strip())


def classify(task: str) -> str | None:
    t = (task or "").lower()
    for pat in ENGLISH_PATTERNS:
        if re.search(pat, t):
            return "english"
    for cap, kws in CAPABILITY_KEYWORDS.items():
        if any(k in t for k in kws):
            return cap
    return None


class CapabilityRouter:
    def __init__(self, agent=None):
        self.agent = agent
    def classify(self, task: str) -> str | None:
        return classify(task)


    def can_handle(self, task: str) -> bool:
        c = classify(task)
        return c is not None and c != "english"

    def handle(self, task: str) -> dict:
        cap = classify(task)
        if cap is None:
            return {"handled": False, "reason": "unknown", "defer": "ask",
                    "hint": "state the task with a capability keyword "
                            "(transpile/decide/verify/search/math/heal/...) or ask for English"}
        if cap == "english":
            return {"handled": False, "reason": "english", "defer": "llm",
                    "hint": "English prose creation is the one class deferred to "
                            "the local LLM (:5001) or a human — never cloud."}
        try:
            return {"handled": True, "capability": cap,
                    "result": self._dispatch(cap, task)}
        except Exception as e:  # noqa: BLE001 — report, defer
            return {"handled": False, "reason": f"{cap}: {type(e).__name__}: {e}",
                    "defer": "llm"}

    def _dispatch(self, cap: str, task: str):
        a = self.agent
        if cap == "math":
            m = re.search(r"[-+*/()\d\s.]+", task)
            if not m:
                raise ValueError("no arithmetic expression found")
            return {"expr": m.group(0).strip(), "value": safe_math_strip(m.group(0))}
        if cap == "search":
            m = re.search(r"(?:find|search|locate|grep)\s+[\"']?([\w.\-/_]+)", task)
            if not m:
                raise ValueError("no search term found")
            term = m.group(1)
            if term.lower() in ("where", "the", "a", "an", "for", "of", "in", "on", "all", "any"):
                m2 = re.search(r"(?:find|search|locate|grep)\s+(?:where|the|a|an|for|of|in|on|all|any)?\s*[\"']?([\w.\-/_]+)", task)
                if m2 and m2.group(1) != term:
                    term = m2.group(1)
            return self._grep(term)
        if cap == "verify":
            return self._verify(task)
        if cap == "heal":
            return a.telemetry.stabilize()
        if cap == "decide":
            return a.decide({"task": task})
        if cap == "plan":
            return a.hap.run_goal(task, a) if hasattr(a, "hap") else {"note": "hap unavailable"}
        if cap == "remember":
            a.journal.record("capability", task, "ok")
            return {"journaled": True, "task": task}
        if cap == "normalize" and hasattr(a, "kernel"):
            from bdi_fsm.foundry_kernel import normalize, hash_index
            return {"normal": normalize(task), "sha256": hash_index(normalize(task))}
        if cap == "transpile" and hasattr(a, "kernel"):
            from bdi_fsm.foundry_kernel import transpile
            return {"language": "python", "code": transpile(task, "python")}
        if cap == "english_render" and hasattr(a, "render_english"):
            return a.render_english(a.last_decision if hasattr(a, "last_decision") else {})
        if cap == "summarize_log":
            return self._log_stats()
        if cap == "list":
            if hasattr(a, "list_details"):
                return a.list_details()
            return {"note": "list_details unavailable"}
        if cap == "learn":
            return a.learner.expand()
        return {"note": f"capability {cap} dispatched"}

    def _grep(self, term: str) -> dict:
        roots = ("/root/scan_tmp/BDI_FSM_AGENT", "/root/hexgame", "/root/pipe_ops")
        hits = []
        for root in roots:
            if not os.path.isdir(root):
                continue
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames
                               if d not in (".git", "__pycache__", "node_modules")]
                for fn in filenames:
                    if not fn.endswith((".py", ".md", ".json", ".sh")):
                        continue
                    p = os.path.join(dirpath, fn)
                    try:
                        with open(p, errors="ignore") as f:
                            for i, line in enumerate(f, 1):
                                if term in line:
                                    hits.append(f"{p}:{i}")
                                    break
                    except Exception:
                        pass
                    if len(hits) >= 8:
                        return {"term": term, "hits": hits, "truncated": True}
        return {"term": term, "hits": hits}

    def _verify(self, task: str) -> dict:
        m = re.search(r"[\w./\-]+\.py", task)
        if not m:
            return {"note": "no .py file named in task"}
        path = m.group(0)
        if not os.path.exists(path):
            # try common roots
            for root in ("/root/scan_tmp/BDI_FSM_AGENT", "/root/hexgame"):
                cand = os.path.join(root, path)
                if os.path.exists(cand):
                    path = cand
                    break
            else:
                return {"error": f"file not found: {path}"}
        import py_compile
        try:
            py_compile.compile(path, doraise=True)
            return {"file": path, "compiles": True}
        except py_compile.PyCompileError as e:
            return {"file": path, "compiles": False, "error": str(e)}

    def _log_stats(self) -> dict:
        stats = {}
        for name, path in (
            ("journal", os.path.join(self.agent.state_dir, "journal.jsonl")),
            ("trace", "/root/hexgame/telemetry/trace.jsonl"),
            ("game_log", "/root/hexgame/game_log.jsonl"),
        ):
            try:
                with open(path) as f:
                    stats[name] = sum(1 for _ in f)
            except Exception:
                stats[name] = 0
        return stats
