"""ToolObserver — rates how likely a chat message is a command/tool-use request.

The BDI agent needs a gate between "talk to me" and "go do something". This is
that gate. It is a small, explainable, trainable classifier — no LLM, stdlib
only — that scores text on a log-odds scale and returns a probability plus the
evidence behind it.

Why log-odds? It is the same Bayesian scoring Turing used in Banburismus to
decide rotor order: accumulate independent pieces of weak evidence (each a
weighted "factor") into a single posterior. Structural signals (imperative
lead, file references, shell syntax) are the cribs; learned word weights are
the accumulated experience.
"""
import json, math, re
from collections import defaultdict
from pathlib import Path

# ---- seed lexicons (weak priors; the online learner dominates over time) ----
IMPERATIVE_VERBS = {
    "run", "open", "fix", "build", "test", "commit", "push", "pull", "check",
    "create", "make", "delete", "remove", "install", "deploy", "start", "stop",
    "restart", "add", "update", "write", "edit", "rename", "move", "copy",
    "clone", "merge", "rebase", "lint", "format", "search", "find", "show",
    "list", "cat", "grep", "execute", "run", "kill", "ssh", "scp", "deploy",
}
TOOL_VERBS = {
    "run", "fix", "build", "test", "commit", "push", "pull", "deploy",
    "install", "compile", "execute", "refactor", "optimize", "debug",
    "generate", "parse", "fetch", "clone", "merge", "patch", "bump",
    "release", "seed", "harvest", "mirror", "scrape", "schedule",
}
ENTITY_PATTERN = re.compile(
    r"\b[\w./-]+\.(?:py|js|ts|jsx|tsx|json|md|sh|yml|yaml|toml|rs|go|c|cpp|h|java|sql)\b"
    r"|/[A-Za-z0-9_./-]{2,}/[A-Za-z0-9_./-]*"      # /path/to/thing
    r"|\bgit\s+\w+"                                  # git <subcommand>
    r"|\bnpm\s+\w+|\bpip\s+\w+|\bcargo\s+\w+|\bapt\s+\w+"
    r"|`[^`]+`"                                      # inline code
    r"|\$\s*[\w-]+"                                  # $VAR
)
CASUAL_WORDS = {
    "hey", "hi", "hello", "thanks", "thank", "please", "cool", "great",
    "awesome", "nice", "lol", "haha", "ok", "okay", "sure", "yo", "sup",
    "whats", "how", "are", "you", "doing", "howdy", "cheers", "love",
    "appreciate", "friend", "buddy", "man", "bro",
}

TOOL_KEYS = set(IMPERATIVE_VERBS) | TOOL_VERBS


class ToolScore:
    __slots__ = ("probability", "is_tool", "log_odds", "evidence", "matched_tools", "matched_entities")
    def __init__(self, probability, log_odds, evidence, matched_tools, matched_entities):
        self.probability = probability
        self.is_tool = probability >= 0.5
        self.log_odds = log_odds
        self.evidence = evidence
        self.matched_tools = matched_tools
        self.matched_entities = matched_entities
    def to_dict(self):
        return {
            "probability": round(self.probability, 4),
            "is_tool": self.is_tool,
            "log_odds": round(self.log_odds, 3),
            "matched_tools": self.matched_tools,
            "matched_entities": self.matched_entities,
            "evidence": self.evidence,
        }


def _sigmoid(x):
    return 1.0 / (1.0 + math.exp(-x))


def _words(text):
    return re.findall(r"[a-zA-Z][a-zA-Z0-9']*", text.lower())


class ToolObserver:
    """Log-odds tool-use detector with online learning."""

    def __init__(self, path=None, prior_log_odds=-0.6):
        self.path = Path(path) if path else None
        self.prior_log_odds = prior_log_odds  # slight prior toward chat
        self.word_score = defaultdict(float)   # learned: +tool / -chat
        self.n_tool = 0
        self.n_chat = 0
        self._load()

    # ---- scoring ----
    def score(self, text):
        text = (text or "").strip()
        lo = self.prior_log_odds
        evidence = []
        matched_tools, matched_entities = [], []

        ws = _words(text)
        for w in ws:
            if w in self.word_score:
                lo += self.word_score[w]

        if ws and ws[0] in IMPERATIVE_VERBS:
            lo += 2.0
            evidence.append(("imperative_lead", ws[0]))

        for w in ws:
            if w in TOOL_VERBS:
                matched_tools.append(w)
        if matched_tools:
            lo += 1.2 * len(matched_tools)
            evidence.append(("tool_verbs", matched_tools))

        ents = ENTITY_PATTERN.findall(text)
        matched_entities = [e if isinstance(e, str) else e[0] for e in ents]
        if matched_entities:
            lo += 0.8 * len(matched_entities)
            evidence.append(("entities", matched_entities))

        casual = [w for w in ws if w in CASUAL_WORDS]
        if casual:
            lo -= 1.0 * len(casual)
            evidence.append(("casual", casual))

        if "?" in text and not matched_tools:
            lo -= 0.5
            evidence.append(("question", True))

        # bound log-odds to keep it stable
        lo = max(-6.0, min(6.0, lo))
        return ToolScore(_sigmoid(lo), lo, evidence, matched_tools, matched_entities)

    # ---- online learning ----
    def record(self, text, is_tool):
        """Train: shift each word's weight toward +1 (tool) or -1 (chat)."""
        target = 1.0 if is_tool else -1.0
        lr = 0.25  # cautious step so single examples don't dominate
        for w in set(_words(text)):
            cur = self.word_score[w]
            self.word_score[w] = cur + lr * (target - max(-1.0, min(1.0, cur)))
        if is_tool:
            self.n_tool += 1
        else:
            self.n_chat += 1
        self._save()
        return self

    # ---- persistence ----
    def stats(self):
        n = self.n_tool + self.n_chat
        return {
            "n_tool": self.n_tool, "n_chat": self.n_chat,
            "n_total": n, "vocab": len(self.word_score),
        }

    def _save(self):
        if not self.path:
            return
        self.path.write_text(json.dumps({
            "prior_log_odds": self.prior_log_odds,
            "word_score": dict(self.word_score),
            "n_tool": self.n_tool, "n_chat": self.n_chat,
        }))

    def _load(self):
        if self.path and self.path.exists():
            try:
                d = json.loads(self.path.read_text())
                self.prior_log_odds = d.get("prior_log_odds", self.prior_log_odds)
                self.word_score = defaultdict(float, d.get("word_score", {}))
                self.n_tool = d.get("n_tool", 0)
                self.n_chat = d.get("n_chat", 0)
            except Exception:
                pass


if __name__ == "__main__":
    obs = ToolObserver()
    for s in [
        "hey, how are you doing today?",
        "run the tests and commit the fix",
        "fix the build in agent.py",
        "can you explain what a state machine is?",
        "deploy the new release to production",
        "thanks man, appreciate it",
        "open the server and check the logs",
    ]:
        sc = obs.score(s)
        bar = "TOOL" if sc.is_tool else "CHAT"
        print(f"[{bar}] p={sc.probability:.2f}  {s!r}")

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
