"""INTENT — deterministic want -> intent parsing (zero LLM).

An "intent ask" is a want expressed in words, translated to a machine
INTENT: (verb, object, params). The parser is pure keyword/pattern matching
against a verb lexicon — no model call. Confidence = fraction of matched
lexical units, so the mesh can route by strength and fall back to SEARCH
when confidence is low (the anti-loop mechanism).

Pure stdlib. Deterministic: same want string -> same Intent every time.
"""
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# verb -> canonical slot names. A token is a verb iff it appears here.
VERB_LEXICON: Dict[str, List[str]] = {
    "build": ["what"], "write": ["what"], "make": ["what"], "create": ["what"],
    "fix": ["what"], "debug": ["what"], "repair": ["what"], "patch": ["what"],
    "test": ["what"], "verify": ["what"], "check": ["what"],
    "run": ["what"], "execute": ["what"], "deploy": ["what"], "install": ["what"],
    "search": ["topic"], "find": ["what"], "locate": ["what"],
    "learn": ["topic"], "explain": ["topic"], "understand": ["topic"],
    "refactor": ["what"], "optimize": ["what"], "improve": ["what"],
    "document": ["what"], "integrate": ["what"], "port": ["what"],
    "analyze": ["what"], "monitor": ["what"], "schedule": ["what"],
    "seed": ["what"], "harden": ["what"], "populate": ["what"],
    # query/list family (Chris 2026-08-14: "list all details" must register)
    "list": ["what"], "show": ["what"], "display": ["what"],
    "enumerate": ["what"], "get": ["what"], "print": ["what"],
    "describe": ["what"], "report": ["what"], "detail": ["what"],
    "summarize": ["what"], "status": ["what"], "read": ["what"],
}

# prepositions that terminate the object phrase (everything after is a param)
STOP_WORDS = {"with", "into", "to", "for", "using", "from", "on", "of", "in", "as"}


@dataclass
class Intent:
    verb: str
    object: str = ""
    params: Dict[str, str] = field(default_factory=dict)
    confidence: float = 0.0
    raw: str = ""

    @property
    def key(self) -> str:
        return f"{self.verb}:{self.object}" if self.object else self.verb

    def __repr__(self) -> str:
        return (f"<Intent {self.verb} obj={self.object!r} "
                f"params={self.params} conf={self.confidence:.2f}>")


def parse_intent(want: str, lexicon: Optional[Dict[str, List[str]]] = None) -> Intent:
    """Parse a want string into an Intent. Deterministic keyword match.

    Returns an Intent with confidence in [0,1]. If no verb is recognised the
    verb is the first token and confidence is 0.0 (so the mesh knows to SEARCH
    rather than act blindly).
    """
    lexicon = lexicon or VERB_LEXICON
    tokens = re.findall(r"[a-z0-9_]+", want.lower())
    if not tokens:
        return Intent(verb="", object="", confidence=0.0, raw=want)

    verb = ""
    for tok in tokens:
        if tok in lexicon:
            verb = tok
            break

    if not verb:
        # no recognised verb: fall back to the first token as a "topic", conf 0
        return Intent(verb=tokens[0], object=" ".join(tokens[1:]),
                      confidence=0.0, raw=want)

    # everything after the verb is the object phrase, split on stop words
    idx = tokens.index(verb)
    rest = tokens[idx + 1:]
    obj_parts: List[str] = []
    params: Dict[str, str] = {}
    cur = obj_parts
    for tok in rest:
        if tok in STOP_WORDS and cur is obj_parts:
            cur = []  # subsequent tokens are param values
        else:
            cur.append(tok)
    obj = " ".join(obj_parts)

    # confidence = fraction of tokens that are lexicon verbs or object words
    matched = 1  # the verb itself
    for tok in obj_parts:
        if tok in lexicon or len(tok) > 2:
            matched += 1
    total = 1 + len(rest)
    confidence = matched / max(1, total)

    return Intent(verb=verb, object=obj, params=params, confidence=confidence, raw=want)


def decompose(intent: Intent) -> List[Dict[str, object]]:
    """Split an intent into ordered sub-goals for the mesh to distribute.

    Primary sub-goal = (verb, object). Each named param becomes an extra
    sub-goal (verb, param-value). Deterministic order.
    """
    goals: List[Dict[str, object]] = [{"verb": intent.verb, "object": intent.object,
                                       "confidence": intent.confidence, "params": {}}]
    for k, v in intent.params.items():
        goals.append({"verb": intent.verb, "object": v,
                      "confidence": intent.confidence, "params": {k: v}})
    return goals

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
