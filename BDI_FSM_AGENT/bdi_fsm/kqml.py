"""KQML — Knowledge Query and Manipulation Language ACL for the agent.

The 90s agent-communication standard (Finin et al., ARPA KQML spec),
mapped onto the lexicon so a human can TALK to the agent in English and
the agent replies in English, while the internal routing is pure KQML:

    "what is the pool status"  ->  (ask-one :content (pool status))
    "please build the bridge"  ->  (achieve :content (build bridge))
    "i think x is broken"      ->  (insert :content (x broken))
    "no, never do that"        ->  (deny :content (never do that))
    "thank you"                ->  (tell :content (you are welcome))

Deterministic classifier: lexical patterns over the token stream (the
lexicon IS the subjective-English map — morphology-derived 45k+ tokens).
Zero LLM. The performative set is the KQML core (ask-one/ask-all/achieve/
tell/insert/deny/reply/error/sorry).
"""

import re
from typing import Any, Dict, List, Optional, Tuple

PERFORMATIVES = [
    "ask-one", "ask-all", "ask-if", "achieve", "tell", "insert",
    "deny", "reply", "error", "sorry", "stream-all", "advertise",
]

# English -> performative pattern table (ordered; first match wins)
_PATTERNS: List[Tuple[re.Pattern, str, str]] = [
    # (regex, performative, content-extractor group or None=whole)
    (re.compile(r"^please\s+(.*)$"), "achieve", 1),
    (re.compile(r"^(?:please\s+)?(?:can|could|would|will)\s+(?:you\s+)?(.*)$"), "achieve", 1),
    (re.compile(r"^(?:go|run|do|make|build|fix|create|update|start|stop|call|execute)\s+(.*)$"), "achieve", 1),
    (re.compile(r"^(?:i\s+)?(?:want|need|wish)\s+(?:you\s+)?(?:to\s+)?(.*)$"), "achieve", 1),
    (re.compile(r"^(?:what|who|where|when|why|how)\b(.*)$"), "ask-one", 1),
    (re.compile(r"^(?:is|are|does|do|can|will|should)\b(.*)$"), "ask-if", 1),
    (re.compile(r"^(?:tell\s+me|show\s+me|give\s+me|list)\s+(.*)$"), "ask-one", 1),
    (re.compile(r"^(?:i\s+(?:think|believe|guess|note|remember|set|record|know)\b)(.*)$"), "insert", 1),
    (re.compile(r"^(?:remember\s+that|note\s+that|set\s+that)\s+(.*)$"), "insert", 1),
    (re.compile(r"^(?:no|never|don'?t|stop|halt|cancel|reject)\b(.*)$"), "deny", 1),
    (re.compile(r"^(?:thanks|thank you|thx|ty)\b.*$"), "tell", None),
    (re.compile(r"^(?:yes|ok|okay|approved|go ahead|sure)\b(.*)$"), "reply", 1),
    (re.compile(r"^(?:help|what can you do)\b.*$"), "advertise", None),
]

# KQML -> English templates
_ENGLISH = {
    "ask-one": "You asked about: {c}",
    "ask-if": "Checking whether: {c}",
    "ask-all": "Querying all: {c}",
    "achieve": "I will attempt to: {c}",
    "tell": "Noted — {c}",
    "insert": "I have recorded that {c}.",
    "deny": "Declined: {c}",
    "reply": "{c}",
    "error": "Error: {c}",
    "sorry": "Sorry, I could not: {c}",
    "stream-all": "Streaming all: {c}",
    "advertise": "I can: ask, achieve, tell, insert, deny, reply.",
}

_REPLIES = {
    "ask-one": "I searched and found: {c}",
    "ask-if": "Answer: {c}",
    "achieve": "Done — {c}",
    "insert": "Stored: {c}",
    "deny": "Understood — I will not: {c}",
    "tell": "Acknowledged: {c}",
}


def classify(text: str) -> Tuple[str, str]:
    """Map English text -> (performative, content). Deterministic."""
    t = re.sub(r"\s+", " ", text.strip().lower().rstrip("?.,!;"))
    for pat, perf, grp in _PATTERNS:
        m = pat.match(t)
        if m:
            c = (m.group(grp) if grp else "").strip()
            c = re.sub(r"^(you\s+|to\s+|that\s+|\?+$)", "", c).strip()
            c = re.sub(r"^(is|are|was|were|does|do|did|can|could|will|would|should|the)\s+", "", c).strip()
            c = re.sub(r"^[\s,.;:!?]+", "", c).strip()
            if not c:
                c = t
            return perf, c
    return "ask-one", t


def envelope(perf: str, sender: str, receiver: str, content: str,
             ontology: str = "lexicon") -> str:
    """Build a KQML message string."""
    c = content.strip().replace("(", "[ ").replace(")", " ]")
    return (f"({perf} :sender {sender} :receiver {receiver} "
            f":ontology {ontology} :content ( {c} ))")


def parse(message: str) -> Dict[str, Any]:
    """Parse a KQML message string back to a dict. Pure tokenizer."""
    toks = re.findall(r"\(|\)|:[a-z-]+|[^\s()]+", message)
    out: Dict[str, Any] = {"performative": None, "params": {}, "content": []}
    i, n = 0, len(toks)
    if i < n and toks[i] == "(":
        i += 1
        out["performative"] = toks[i] if i < n else None
        i += 1
    content_mode = False
    while i < n:
        tk = toks[i]
        if tk == ")":
            break
        if tk == "(":
            content_mode = True
            i += 1
            continue
        if tk.startswith(":"):
            out["params"][tk] = []
            cur = tk
            i += 1
            while i < n and not toks[i].startswith(":") and toks[i] != ")":
                if toks[i] != "(":
                    out["params"][cur].append(toks[i])
                i += 1
            continue
        if content_mode:
            out["content"].append(tk)
        i += 1
    for k in list(out["params"]):
        if k in (":sender", ":receiver", ":ontology"):
            out[k[1:]] = " ".join(out["params"][k])
        if k == ":content" and not out["content"]:
            out["content"] = out["params"][k]
    return out


def render_english(perf: str, content: str) -> str:
    """KQML -> human English (what the agent SAYS)."""
    return _ENGLISH.get(perf, _ENGLISH["reply"]).format(c=content)


def render_reply(perf: str, result: str) -> str:
    """Agent's reply to the human after acting on a performative."""
    return _REPLIES.get(perf, result).format(c=result)


def talk(text: str, lexicon=None) -> Dict[str, Any]:
    """Full loop: English -> KQML -> (optional lexicon tool binding) ->
    English reply. Returns the whole trace (inspectable, deterministic)."""
    perf, content = classify(text)
    msg = envelope(perf, "aegis", "bdi-fsm", content)
    parsed = parse(msg)
    tool = None
    if lexicon is not None:
        tool = lexicon.lookup_tool(text)
    reply = render_english(perf, content)
    if tool:
        reply = render_reply(perf, f"routed to tool [{tool}] — {content}")
    return {
        "input": text,
        "performative": perf,
        "content": content,
        "kqml": msg,
        "parsed": parsed,
        "tool": tool,
        "english": reply,
    }

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
