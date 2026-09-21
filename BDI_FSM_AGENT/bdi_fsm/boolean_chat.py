"""BOOLEAN CHAT — English-only conversational bot, ≥5k tokenized lexicon,
toolcalling by lexicon. Zero LLM, zero cloud.

The boolean bot answers chat in English but its decisions are BOOLEAN:
yes/no / true/false / approve/deny / on/off. It dispatches tools by
LEXICON: a bound token in the user's message maps deterministically to
a registered tool. This is the "if I ever want to chat, the boolean bot
is there too" layer.
"""

import os
import re
import sys
from typing import Any, Callable, Dict, List, Optional

from .lexicon import Lexicon

_VIPERCLI_SRC = r"C:\Users\viper\gan-otg-db\ViperCli\src"


def _tool_show() -> str:
    """Real, live board status -- what 'show' now actually routes to.

    Added 2026-09-21: 'show' was recognized by kqml.classify() as ask-one
    (see kqml.py the same session) but had no lexicon binding at all here,
    so a real BooleanChat instance still answered 'show' by falling
    through to the boolean yes/no guesser (pos=0, neg=0 -> 'NO' -- a
    QUERY answered as if it were a decision, confirmed live before this
    fix). Composed with menu_system.menu() (ViperCli, same session,
    3ad333e) rather than reimplementing a second board reader.

    Bound to ONE tool rather than dispatched by content: Lexicon.lookup_tool()
    returns on the FIRST bound token found in the message, so 'show tasks'
    and 'show cron' would both hit 'show' before reaching 'tasks'/'cron' as
    separate tokens -- genuine per-section routing ('show cron' specifically
    -> CronMenu) needs either content-aware tool calling or token-priority
    in lookup_tool() itself, a change to shared Lexicon behaviour outside
    this scope. This binds 'show' to the single most broadly useful real
    answer (live task board) rather than guessing at disambiguation.
    """
    try:
        if _VIPERCLI_SRC not in sys.path:
            sys.path.insert(0, _VIPERCLI_SRC)
        import menu_system
        r = menu_system.menu("tasks", "status")
        if not r.get("available"):
            return f"board unavailable: {r.get('error')}"
        return (f"board: {r.get('done', 0)} done, {r.get('open', 0)} open, "
                f"{r.get('parked', 0)} parked, {r.get('total', 0)} total")
    except Exception as e:
        return f"show failed: {e}"


class BooleanChat:
    def __init__(self, lexicon: Optional[Lexicon] = None):
        self.lexicon = lexicon or Lexicon()
        self.lexicon.ensure_min()
        self._tools: Dict[str, Callable] = {}
        self._bindings: Dict[str, str] = {}
        self.history: List[Dict[str, Any]] = []
        self._bind_defaults()

    def _bind_defaults(self) -> None:
        """Bind core boolean decisions + a few deterministic tools."""
        for word in ["yes", "yep", "yeah", "true", "approve", "ok", "go", "run"]:
            self.lexicon.bind(word, "bool_yes")
        for word in ["no", "nope", "false", "deny", "stop", "halt", "block"]:
            self.lexicon.bind(word, "bool_no")
        for word in ["help", "status", "state", "info"]:
            self.lexicon.bind(word, "tool_status")
        for word in ["test", "check", "verify"]:
            self.lexicon.bind(word, "tool_test")
        for word in ["needs", "maslow"]:
            self.lexicon.bind(word, "tool_needs")
        # Real, not just bound: register_tool() both binds the lexicon
        # token AND populates self._tools, so reply() actually calls it --
        # unlike tool_status/tool_test/tool_needs above, which are bound in
        # the lexicon but were never registered here, so lookup_tool()
        # finds them while reply()'s `tool in self._tools` check is False
        # and every one silently falls through to the boolean guesser
        # instead (confirmed live: reply("status") -> "NO"). Left as a
        # known, separate, adjacent gap -- not fixed in this pass, which
        # is scoped to 'show'.
        self.register_tool("tool_show", _tool_show, ["show"])

    def register_tool(self, name: str, fn: Callable,
                      tokens: Optional[List[str]] = None) -> None:
        self._tools[name] = fn
        for t in (tokens or [name]):
            self.lexicon.bind(t, name)

    # ---- core boolean decision -------------------------------------------
    def decide(self, text: str) -> Dict[str, Any]:
        """Deterministic boolean decision: check for yes/no lexicon hits."""
        tokens = self.lexicon.tokenize(text)
        for t in tokens:
            tool = self.lexicon.lookup_tool(t)
            if tool in ("bool_yes", "bool_no"):
                return {"decision": tool == "bool_yes",
                        "bool": True, "word": t}
        # default: count positive vs negative valence words (tiny heuristic)
        pos = sum(1 for t in tokens if t in _POSITIVE)
        neg = sum(1 for t in tokens if t in _NEGATIVE)
        return {"decision": pos > neg, "bool": True,
                "pos": pos, "neg": neg}

    # ---- chat reply (English only) ------------------------------------------
    def reply(self, text: str) -> str:
        """English-only reply + optional tool dispatch via lexicon."""
        tool = self.lexicon.lookup_tool(text)
        result = None
        if tool and tool in self._tools and not tool.startswith("bool_"):
            try:
                result = self._tools[tool]()
            except Exception as e:
                result = f"tool error: {e}"
        d = self.decide(text)
        if result is not None:
            out = f"Tool [{tool}] -> {result}"
        elif d["bool"]:
            out = "YES" if d["decision"] else "NO"
        else:
            out = "I am the boolean bot. Ask yes/no, or use a bound tool."
        self.history.append({"in": text, "out": out})
        self.lexicon.mirror(text)          # recursive lexical learning
        return out

    def chat(self, text: str) -> str:
        return self.reply(text)


# tiny valence lists for the boolean heuristic (deterministic, offline)
_POSITIVE = {"good", "yes", "true", "ok", "approve", "run", "go", "love", "great", "works", "pass", "win", "success", "accept", "allow", "on", "start", "continue", "better", "best", "agree"}
_NEGATIVE = {"no", "false", "deny", "stop", "halt", "block", "bad", "fail", "error", "broken", "wrong", "off", "end", "stop", "reject", "never", "nope", "down", "crash", "die", "worse", "worst", "disagree"}

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
