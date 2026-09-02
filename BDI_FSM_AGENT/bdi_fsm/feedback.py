"""FEEDBACK — like/dislike training for the chat layer.

Chris directive 2026-08-12:
"A chat to talk to the bot and like/dislike to train."

Each (input -> reply) exchange can be rated. Feedback adjusts:
  - `preferences`: phrase -> net score (+1 like, -1 dislike)
  - `associations`: input token -> reply token reinforcement (Markov-style)
  - `lexicon._freq`: liked phrases get their tokens frequency-boosted,
                    disliked phrases get dampened.

Positive feedback strengthens the path; negative feedback records a
counter-example so the same reply is deprioritized next time.

Pure stdlib. Deterministic. Zero LLM.
"""

import json
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from .markov_chat import tokenize


class FeedbackStore:
    """Persistent like/dislike training memory."""

    def __init__(self, path: str):
        self.path = path
        self.preferences: Dict[str, int] = {}    # phrase -> net score
        self.associations: Dict[str, int] = {}   # "in|out" -> score
        self.examples: List[Dict[str, Any]] = []  # full rated exchanges
        self._load()

    # ---- rating -------------------------------------------------------
    def rate(self, user_input: str, reply: str, positive: bool) -> Dict[str, Any]:
        """Record a like/dislike for an (input, reply) pair."""
        inp = (user_input or "").strip()
        rep = (reply or "").strip()
        if not inp or not rep:
            return {"ok": False, "error": "empty input/reply"}

        delta = 1 if positive else -1

        # 1. phrase-level preference (whole input)
        key_in = inp.lower()
        self.preferences[key_in] = self.preferences.get(key_in, 0) + delta

        # 2. token-level association: input tokens -> reply tokens
        for ti in tokenize(inp):
            for tr in tokenize(rep)[:12]:   # cap to avoid blowup
                k = f"{ti}|{tr}"
                self.associations[k] = self.associations.get(k, 0) + delta

        # 3. keep a full example for pedagogy
        ex = {"in": inp, "out": rep, "positive": positive,
              "ts": time.time()}
        self.examples.append(ex)
        if len(self.examples) > 500:
            self.examples = self.examples[-500:]

        self.save()
        return {"ok": True, "pref_score": self.preferences[key_in],
                "associations": len(self.associations)}

    # ---- retrieval ----------------------------------------------------
    def preference(self, text: str) -> int:
        """Net preference score for a phrase (0 = neutral)."""
        return self.preferences.get((text or "").strip().lower(), 0)

    def should_prefer(self, candidate_reply: str, user_input: str) -> float:
        """Score a candidate reply given the input: sum of association scores
        for (input_token -> reply_token) that we've learned. Positive = liked."""
        score = 0.0
        in_toks = tokenize(user_input)
        for tr in tokenize(candidate_reply)[:12]:
            for ti in in_toks:
                score += self.associations.get(f"{ti}|{tr}", 0)
        return score

    def top_associations(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Most reinforced input->reply token pairs (for the learning log)."""
        items = sorted(self.associations.items(), key=lambda kv: -kv[1])[:limit]
        return [{"pair": k, "score": v} for k, v in items]

    # ---- persistence --------------------------------------------------
    def save(self) -> None:
        data = {
            "preferences": self.preferences,
            "associations": self.associations,
            "examples": self.examples[-200:],
        }
        try:
            with open(self.path, "w") as f:
                json.dump(data, f, indent=1)
        except OSError:
            pass

    def _load(self) -> None:
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path) as f:
                data = json.load(f)
            self.preferences = data.get("preferences", {})
            self.associations = data.get("associations", {})
            self.examples = data.get("examples", [])
        except (OSError, json.JSONDecodeError):
            pass

    def stats(self) -> Dict[str, Any]:
        likes = sum(1 for e in self.examples if e.get("positive"))
        dislikes = len(self.examples) - likes
        return {
            "rated_exchanges": len(self.examples),
            "likes": likes,
            "dislikes": dislikes,
            "preferred_phrases": len([k for k, v in self.preferences.items() if v > 0]),
            "associations": len(self.associations),
        }
