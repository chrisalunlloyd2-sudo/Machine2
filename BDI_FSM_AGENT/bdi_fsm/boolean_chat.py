"""BOOLEAN CHAT — English-only conversational bot, ≥5k tokenized lexicon,
toolcalling by lexicon. Zero LLM, zero cloud.

The boolean bot answers chat in English but its decisions are BOOLEAN:
yes/no / true/false / approve/deny / on/off. It dispatches tools by
LEXICON: a bound token in the user's message maps deterministically to
a registered tool. This is the "if I ever want to chat, the boolean bot
is there too" layer.
"""

import re
from typing import Any, Callable, Dict, List, Optional

from .lexicon import Lexicon


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
