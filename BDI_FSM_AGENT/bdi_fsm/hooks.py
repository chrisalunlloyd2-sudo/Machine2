"""hooks.py — the batch terminal shell (hook dispatcher).

Chris 2026-08-15: a choice-tree node carries a "hook and direction" that "works
in the batch terminal shell that reads the direction, does the computation,
based on the results does the next choice from a list of computations."

This module is that terminal: a registry mapping direction strings to real
computations. It reads a direction, runs the bound callable, and returns a
uniform {ok, result, quality} envelope so a ChoiceTree can feed `quality` back
as a reward. Pure stdlib, deterministic, zero-LLM.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional


def normalize_direction(direction: str) -> str:
    """Reduce a direction string to a bare command token.

    Accepts: "ask_github", "run ask_github", "terminal: run ask_github",
    "run:ask_github", etc. Returns the command name (last word).
    """
    d = (direction or "").strip().lower()
    for pre in ("terminal:", "hook:", "direction:"):
        if d.startswith(pre):
            d = d[len(pre):].strip()
    tokens = d.replace(":", " ").split()
    # drop leading verbs like "run" / "do" / "exec" / "execute"
    while tokens and tokens[0] in ("run", "do", "exec", "execute", "call"):
        tokens.pop(0)
    return tokens[-1] if tokens else ""


class HookDispatcher:
    """Reads a direction, runs the bound computation, returns an envelope."""

    def __init__(self):
        self.hooks: Dict[str, Callable[..., Dict[str, Any]]] = {}

    def bind(self, name: str, fn: Optional[Callable[..., Dict[str, Any]]] = None):
        """Register a direction -> computation. Usable as a decorator."""
        def _wrap(f):
            self.hooks[name] = f
            return f
        return _wrap(fn) if fn is not None else _wrap

    def names(self) -> List[str]:
        return sorted(self.hooks)

    def run(self, direction: str, **ctx) -> Dict[str, Any]:
        """Read direction, compute, return {ok, result, quality}."""
        name = normalize_direction(direction)
        if not name or name not in self.hooks:
            return {"ok": False, "result": f"unknown hook: {direction!r}",
                    "quality": 0.0}
        try:
            r = self.hooks[name](**ctx)
            if not isinstance(r, dict):
                r = {"result": str(r)}
            r.setdefault("ok", True)
            r.setdefault("result", "")
            r.setdefault("quality", 0.5)
            return r
        except Exception as e:  # a failed computation is a low-quality result
            return {"ok": False, "result": f"{name}: {type(e).__name__}: {e}",
                    "quality": 0.0}

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
