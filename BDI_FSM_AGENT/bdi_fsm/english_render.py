"""ENGLISH-WORD DECISION-TREE RENDERING — sentences, not codes.

Chris roadmap item: "English-word decision-tree rendering (sentences,
not codes)".

Turns any decision tree (AiceptionTree, exhaustive TaskTree, Metaplan
macro chain) into plain-English sentences a human can read at a glance.

Examples:
  tree   ->  "Given 'verify system', I considered 4 options. Because
              run_tests has the best record (3 wins, 0 losses) and the ask
              was 'run', I chose run_tests."
  macro  ->  "To reach 'deployed', I would: save the code, then run the
              tests, then deploy — because deploy applies once tests pass."

Pure stdlib. Zero LLM (the sentences are templated from real structure —
deterministic, never invented).
"""

from typing import Any, Dict, List, Optional


def _num(n: float) -> str:
    return f"{n:.2f}".rstrip("0").rstrip(".") if n % 1 else str(int(n))


def render_task_tree(tree: Any, chosen_action: Optional[str] = None) -> str:
    """Render an exhaustive TaskTree as English sentences."""
    task = getattr(tree, "task", "this task")
    step = getattr(tree, "step", 1)
    ask = getattr(tree, "ask", None)
    leaves = getattr(tree, "leaves", []) or []
    sig = getattr(tree, "_sig", lambda: "")() if hasattr(tree, "_sig") else ""

    if not leaves:
        return f"For '{task}' at step {step}, I found no candidate actions."

    parts = [f"To handle '{task}' (step {step}"
             + (f", asked for '{ask}'" if ask else "")
             + "), I weighed these options:"]
    ranked = sorted(
        leaves, key=lambda c: (-(c.stats.get("w", 0) + 1) / (c.stats.get("n", 0) + 2),
                               c.action or ""))
    for c in ranked[:8]:
        n = c.stats.get("n", 0)
        w, f = c.stats.get("w", 0), c.stats.get("f", 0)
        if n == 0:
            hist = "never tried before"
        elif f == 0:
            hist = f"won all {n} tries"
        else:
            hist = f"{w} wins, {f} losses in {n} tries"
        parts.append(f"- {c.action} ({hist})")
    if chosen_action:
        parts.append(f"I chose {chosen_action} because it is the most "
                     f"statistically promising of the candidates.")
    return "\n".join(parts)


def _chosen_name(chosen: Any) -> str:
    """Pull a readable action name out of chosen (str or dict)."""
    if isinstance(chosen, dict):
        return str(chosen.get("action") or chosen.get("name") or chosen)
    return str(chosen) if chosen else ""


def render_aiception(tree: Any) -> str:
    """Render an AiceptionTree as English sentences.

    Handles BOTH the test-mock shape (focus_ratings dict + chosen str)
    and the real AiceptionTree (foci list of dicts + chosen dict with
    'action'/'name'). Deterministic, templated — never invented.
    """
    t = getattr(tree, "_tree", tree)
    chosen = None
    if hasattr(tree, "chosen"):
        chosen = tree.chosen
    elif isinstance(t, dict):
        chosen = t.get("chosen_action")
    focus_lines = []
    if hasattr(tree, "focus_ratings") and tree.focus_ratings:
        for k, v in list(tree.focus_ratings.items())[:5]:
            focus_lines.append(f"{k} scored {_num(v)}")
    elif isinstance(t, dict):
        for k, v in list(t.get("focus_ratings", {}).items())[:5]:
            focus_lines.append(f"{k} scored {_num(v)}")
    elif hasattr(tree, "foci") and tree.foci:
        for f in list(tree.foci)[:5]:
            label = f.get("label") or f.get("attr") or "criterion"
            focus_lines.append(f"{label} ({_num(f.get('weight', 0.0))})")
    parts = ["Here is my reasoning:"]
    if focus_lines:
        parts.append("Considering " + "; ".join(focus_lines) + ".")
    cn = _chosen_name(chosen)
    if cn:
        parts.append(f"I decided to {cn}.")
    else:
        parts.append("I found no acceptable action.")
    return "\n".join(parts)


def render_macro(macro: Dict[str, Any]) -> str:
    """Render a MetaplanAbductor result as an English plan."""
    goal = macro.get("goal", "the goal")
    steps = macro.get("steps", [])
    expl = macro.get("explanation", "")
    if not steps:
        return f"I could not find a way to reach '{goal}' from here."
    seq = ", then ".join(f"'{s}'" for s in steps)
    return (f"To reach '{goal}', I would {seq}. "
            f"Reasoning: {expl}" if expl else
            f"To reach '{goal}', I would {seq}.")


def render_dag(dag: Any, limit: int = 12) -> str:
    """Render a TaskDAG's most-used edges as English."""
    nodes = getattr(dag, "nodes", {}) if not isinstance(dag, dict) else dag
    if not nodes:
        return "The decision DAG is still empty — nothing learned yet."
    lines = ["What I have learned so far:"]
    items = []
    for fp, node in nodes.items():
        sig = (node.get("sig") or fp)[:60] if isinstance(node, dict) else fp[:60]
        for action, st in (node.get("actions", {}) if isinstance(node, dict) else {}).items():
            n = st.get("n", 0)
            if n == 0:
                continue
            w, f = st.get("w", 0), st.get("f", 0)
            pct = 100.0 * w / n
            items.append((pct, n, f"After state '{sig}', {action} succeeded "
                          f"{_num(pct)}% of the time ({w}/{n})"))
    items.sort(reverse=True)
    for _, n, line in items[:limit]:
        lines.append(f"- {line}")
    return "\n".join(lines)
