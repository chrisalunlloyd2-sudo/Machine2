"""VERB FLAGS — verbs as flags: natural language -> performative -> action.

Chris's doctrine: "verbs should usually be a flag we are doing something".
Every action in the tree declares verbs. This module extracts verb flags
from an incoming sentence, maps them to KQML performatives, and lets the
behavior tree pull the matching action.

    "please save this code in repository x file a line 22"
    -> verbs: [save]  performative: achieve  action: save_code
    -> "It is done."

Verbs are LEARNABLE: unknown verbs encountered in chat with a known action
context get recorded to the lexicon so the flag table grows with use.
Pure stdlib, zero LLM.
"""

import json
import os
import re
from typing import Dict, List, Optional, Tuple

# Default verb -> performative flags (verbs are usually a flag we are DOING something)
VERB_PERFORMATIVE = {
    # do/achieve family
    "save": "achieve", "write": "achieve", "put": "achieve", "store": "achieve",
    "commit": "achieve", "push": "achieve", "add": "achieve", "create": "achieve",
    "fix": "achieve", "update": "achieve", "apply": "achieve", "patch": "achieve",
    "test": "achieve", "run": "achieve", "verify": "achieve", "validate": "achieve",
    "crawl": "achieve", "learn": "achieve", "train": "achieve", "fetch": "achieve",
    "mine": "achieve", "evolve": "achieve", "breed": "achieve", "mutate": "achieve",
    "optimize": "achieve", "improve": "achieve", "build": "achieve", "make": "achieve",
    "reload": "achieve", "restart": "achieve", "swap": "achieve", "warm": "achieve",
    "dream": "achieve", "prune": "achieve", "archive": "achieve", "consolidate": "achieve",
    "sleep": "achieve", "clean": "achieve", "do": "achieve", "execute": "achieve",
    "generate": "achieve", "synthesize": "achieve", "deploy": "achieve",
    "install": "achieve", "sync": "achieve", "merge": "achieve",
    "feature": "achieve", "publish": "achieve", "surface": "achieve",
    "showcase": "achieve", "highlight": "achieve", "announce": "achieve",
    "share": "achieve", "post": "achieve", "digest": "achieve",
    # ask family
    "ask": "ask-one", "check": "ask-one", "show": "ask-one", "list": "ask-one",
    "what": "ask-one", "status": "ask-one", "report": "ask-one", "state": "ask-one",
    "diff": "ask-one", "log": "ask-one", "tell": "ask-one", "explain": "ask-one",
    # insert/deny family
    "remember": "insert", "note": "insert", "set": "insert", "record": "insert",
    "stop": "deny", "never": "deny", "cancel": "deny", "reject": "deny", "halt": "deny",
}

# action-name -> verbs (kept in sync with action_lib; used for learning)
ACTION_VERBS = {
    "save_code": ["save", "write", "put", "store", "commit", "push", "add",
                  "create", "fix", "update", "apply", "patch"],
    "run_tests": ["test", "run", "verify", "check", "validate", "prove", "green"],
    "git_status": ["status", "show", "list", "what", "check", "report", "state",
                   "diff", "log"],
    "webcrawl": ["crawl", "learn", "train", "fetch", "read", "research", "scrape"],
    "dream_prune": ["dream", "prune", "archive", "consolidate", "sleep", "clean"],
    "foundry_mine": ["mine", "evolve", "breed", "foundry", "mutate", "optimize",
                     "darwin", "improve"],
    "reload_model": ["reload", "refresh", "restart", "swap", "warm", "model", "server"],
    "update_daily_feature": ["feature", "daily", "publish", "update", "surface",
                             "showcase", "highlight", "announce", "share", "post", "digest"],
}

STOP_WORDS = {"a", "an", "the", "to", "of", "in", "on", "at", "for", "with",
              "and", "or", "but", "please", "you", "your", "i", "my", "me",
              "this", "that", "it", "is", "are", "was", "be", "do", "can",
              "would", "could", "will", "should", "from", "into", "code",
              "repository", "repo", "file", "line", "x", "y", "z", "hello",
              "hi", "hey"}


class VerbFlags:
    """Extract verb flags from text; learn new ones from context."""

    def __init__(self, state_dir: Optional[str] = None):
        self.state_dir = state_dir
        self.extra: Dict[str, str] = {}
        if state_dir:
            p = os.path.join(state_dir, "verb_flags.json")
            if os.path.exists(p):
                try:
                    self.extra = json.load(open(p))
                except Exception:
                    self.extra = {}

    @staticmethod
    def tokenize(text: str) -> List[str]:
        return re.findall(r"[a-z']+", text.lower())

    def lookup(self, word: str) -> Optional[str]:
        if word in VERB_PERFORMATIVE:
            return VERB_PERFORMATIVE[word]
        return self.extra.get(word)

    def flags(self, text: str) -> Dict[str, str]:
        """Return {verb: performative} for every known verb in text."""
        out = {}
        for w in self.tokenize(text):
            perf = self.lookup(w)
            if perf and w not in out:
                out[w] = perf
        return out

    def verbs(self, text: str) -> List[str]:
        return list(self.flags(text).keys())

    def performative(self, text: str) -> str:
        """Pick the dominant performative: achieve > ask > insert > deny."""
        fl = self.flags(text)
        order = ["achieve", "ask-one", "insert", "deny", "ask-if", "ask-all"]
        for p in order:
            if p in fl.values():
                return p
        # fall back to KQML pattern classifier
        return self._kqml_fallback(text)

    def _kqml_fallback(self, text: str) -> str:
        t = text.lower().strip()
        if re.match(r"^(what|who|where|when|why|how|is|are|can|does|do|will|should)\b", t):
            return "ask-one"
        if re.match(r"^(please|go|run|do|make|build|fix|create|update|start|stop|call|execute)\b", t):
            return "achieve"
        if re.match(r"^(no|never|don'?t|stop|halt|cancel|reject)\b", t):
            return "deny"
        if re.match(r"^(i|we)\s+(think|believe|note|remember|set|record)\b", t):
            return "insert"
        return "ask-one"

    def action_hint(self, text: str) -> Optional[str]:
        """Best-guess action name from verb flags."""
        verbs = self.verbs(text)
        if not verbs:
            return None
        best, best_n = None, 0
        for action, action_verbs in ACTION_VERBS.items():
            hits = len(set(verbs) & set(action_verbs))
            if hits > best_n:
                best, best_n = action, hits
        return best

    def learn(self, text: str, action_name: Optional[str] = None) -> List[str]:
        """Learn new verb flags: unknown words near a known action context."""
        learned = []
        toks = self.tokenize(text)
        for w in toks:
            if len(w) < 3 or w in STOP_WORDS or self.lookup(w):
                continue
            if action_name and action_name in ACTION_VERBS:
                self.extra[w] = "achieve"   # appeared in an action sentence
                learned.append(w)
        if learned and self.state_dir:
            os.makedirs(self.state_dir, exist_ok=True)
            with open(os.path.join(self.state_dir, "verb_flags.json"), "w") as f:
                json.dump(self.extra, f, indent=2, sort_keys=True)
        return learned

    def stats(self) -> Dict:
        return {"builtin": len(VERB_PERFORMATIVE), "learned": len(self.extra),
                "total": len(VERB_PERFORMATIVE) + len(self.extra)}

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
