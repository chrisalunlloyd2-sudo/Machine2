"""IDENTITY — the agent's persistent model of ITSELF ("self") vs YOU.

Chris directive 2026-08-12:
"We need an idea of self to define 'you' and agent as the agent itself."

Two distinct identities:
  - OPERATOR ("you"): the human who sets goals, gives corrections, rates replies.
  - AGENT ("self"): the deterministic symbolic engine — its axioms, skills,
    history, and current internal state.

The self-model is immutable at its core (axioms never change) but ACCRETES:
skills mastered, facts learned, and a condensed narrative of its own evolution.
This is what the web UI shows as the "self" panel — separate from the operator.

Pure stdlib. Deterministic. Zero LLM.
"""

import json
import os
import time
from typing import Any, Dict, List, Optional


class Identity:
    """Persistent self-model for the agent, with an explicit operator boundary."""

    AXIOMS = [
        "I am deterministic: same input, same output.",
        "I learn from feedback: corrections reshape my rules.",
        "I am symbolic, not probabilistic: every decision is reproducible.",
        "I have no hidden state: my beliefs are auditable on the blackboard.",
        "I stop when Shannon entropy spikes: coherence is my boundary.",
    ]

    def __init__(self, path: str, name: str = "bdi-fsm-agent"):
        self.path = path
        self.name = name
        self.axioms = list(self.AXIOMS)
        self.skills: Dict[str, float] = {}       # skill -> confidence 0..1
        self.facts: Dict[str, str] = {}          # learned facts (key -> value)
        self.operator: Dict[str, Any] = {        # who YOU are (boundary)
            "name": None,
            "goals": [],
            "corrections": 0,
            "likes": 0,
            "dislikes": 0,
        }
        self.history: List[Dict[str, Any]] = []  # condensed evolution narrative
        self.born_at = time.time()
        self.cycle = 0
        self._load()

    # ---- identity -----------------------------------------------------
    def who_am_i(self) -> Dict[str, Any]:
        """The agent's self-report (what the 'self' panel shows)."""
        return {
            "name": self.name,
            "axioms": self.axioms,
            "skills": dict(sorted(self.skills.items(), key=lambda kv: -kv[1])),
            "facts": dict(self.facts),
            "born_at": self.born_at,
            "age_s": round(time.time() - self.born_at, 1),
            "cycle": self.cycle,
            "narrative": self.history[-10:],   # recent evolution
        }

    def operator_report(self) -> Dict[str, Any]:
        """What the agent knows about YOU (the operator)."""
        return dict(self.operator)

    # ---- accretion ----------------------------------------------------
    def master_skill(self, skill: str, confidence: float = 0.5) -> None:
        """Record a skill with a confidence score (0..1)."""
        prev = self.skills.get(skill, 0.0)
        self.skills[skill] = min(1.0, max(prev, confidence))
        self._narrate("master", f"skill '{skill}' -> confidence {self.skills[skill]:.2f}")

    def learn_fact(self, key: str, value: str) -> None:
        self.facts[key] = value
        self._narrate("fact", f"{key} = {value}")

    def tick(self) -> None:
        self.cycle += 1

    def _narrate(self, kind: str, detail: str) -> None:
        self.history.append({"kind": kind, "detail": detail, "ts": time.time()})
        if len(self.history) > 500:
            self.history = self.history[-500:]
        self.save()

    # ---- operator feedback (like/dislike) -----------------------------
    def feedback(self, positive: bool, note: str = "") -> None:
        if positive:
            self.operator["likes"] += 1
        else:
            self.operator["dislikes"] += 1
        self._narrate("feedback", f"{'LIKE' if positive else 'DISLIKE'} {note}")

    def record_correction(self, note: str = "") -> None:
        self.operator["corrections"] += 1
        self._narrate("correction", note)

    def set_operator_name(self, name: str) -> None:
        self.operator["name"] = name
        self._narrate("operator", f"operator name = {name}")

    def add_goal(self, goal: str) -> None:
        self.operator["goals"].append(goal)
        self._narrate("goal", goal)

    # ---- persistence --------------------------------------------------
    def save(self) -> None:
        data = {
            "name": self.name,
            "axioms": self.axioms,
            "skills": self.skills,
            "facts": self.facts,
            "operator": self.operator,
            "history": self.history,
            "born_at": self.born_at,
            "cycle": self.cycle,
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
            self.name = data.get("name", self.name)
            self.skills = data.get("skills", {})
            self.facts = data.get("facts", {})
            self.operator = data.get("operator", self.operator)
            self.history = data.get("history", [])
            self.born_at = data.get("born_at", self.born_at)
            self.cycle = data.get("cycle", 0)
        except (OSError, json.JSONDecodeError):
            pass

    def stats(self) -> Dict[str, Any]:
        return {
            "skills": len(self.skills),
            "facts": len(self.facts),
            "narrative_events": len(self.history),
            "operator_likes": self.operator.get("likes", 0),
            "operator_dislikes": self.operator.get("dislikes", 0),
            "operator_corrections": self.operator.get("corrections", 0),
        }
