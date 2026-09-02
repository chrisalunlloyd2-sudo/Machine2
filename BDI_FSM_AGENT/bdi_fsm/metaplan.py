"""METAPLAN ABDUCTION — backward-chaining macro synthesis.

Chris roadmap item: "Metaplan abduction (backward-chaining macro
synthesis)".

From a goal, work BACKWARD through the Hap plan memory (and journal
successes): find a plan whose effect achieves the goal, then find a plan
whose effect achieves THAT plan's precondition, and so on, until a plan's
precondition matches the current state. The chain of plans is a MACRO —
a synthesized multi-step plan that abductively explains how to reach the
goal from here.

Also lands:
  - PRECONDITION GENERALIZATION (anti-unification on success): when a plan
    succeeds under several different preconditions, anti-unify those
    preconditions (common skeleton, differing constants -> variables) to
    synthesize a GENERAL precondition — "this plan works when ANY of these
    hold".

Pure stdlib. Zero LLM. ADD-only: macros are cached, never deleted.
"""

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# minimal precondition algebra (shared by abduction + anti-unification)
# ---------------------------------------------------------------------------

def atoms_of(pre: str) -> List[str]:
    """Split a precondition string into atomic propositions."""
    if not pre:
        return []
    return [a.strip().lower() for a in re.split(r"[,;]|\band\b|\bor\b", pre)
            if a.strip()]


def anti_unify(a: str, b: str) -> Optional[str]:
    """Anti-unify two precondition strings -> general form.

    'file exists AND x > 0' with 'file exists AND y > 0'
      -> 'file exists AND $V > 0'   (constant differs -> variable)
    Returns None if skeletons differ too much.
    """
    aa, bb = atoms_of(a), atoms_of(b)
    if not aa or not bb:
        return None
    # align by index; differing token at the same position -> variable
    out = []
    for x, y in zip(aa, bb):
        tx, ty = x.split(), y.split()
        if len(tx) != len(ty):
            return None  # skeleton mismatch
        parts = []
        for px, py in zip(tx, ty):
            if px == py:
                parts.append(px)
            elif px.isdigit() and py.isdigit():
                parts.append("$N")
            elif px.isidentifier() and py.isidentifier():
                parts.append("$V")
            else:
                return None
        out.append(" ".join(parts))
    # tail: if one has extra atoms, generalize with variable
    longer = aa if len(aa) > len(bb) else bb
    shorter = bb if len(aa) > len(bb) else aa
    for i in range(len(shorter), len(longer)):
        out.append("$V")
    return " AND ".join(out)


def general_precondition(success_preconditions: List[str]) -> str:
    """Anti-unify ALL recorded success preconditions of a plan into one
    general precondition (roadmap item 3)."""
    if not success_preconditions:
        return "*"
    g = success_preconditions[0]
    for p in success_preconditions[1:]:
        nu = anti_unify(g, p)
        if nu:
            g = nu
    return g


# ---------------------------------------------------------------------------
# plan memory (Hap-compatible shape)
# ---------------------------------------------------------------------------

class Plan:
    def __init__(self, name: str, effect: str, precondition: str,
                 steps: Optional[List[str]] = None, spec: float = 1.0):
        self.name = name
        self.effect = effect.lower()
        self.precondition = precondition.lower()
        self.steps = list(steps or [name])
        self.spec = spec
        self.success_preconditions: List[str] = []

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "effect": self.effect,
                "precondition": self.precondition, "steps": self.steps,
                "spec": self.spec,
                "success_preconditions": self.success_preconditions}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Plan":
        p = cls(d["name"], d["effect"], d["precondition"],
                d.get("steps"), d.get("spec", 1.0))
        p.success_preconditions = d.get("success_preconditions", [])
        return p


# ---------------------------------------------------------------------------
# MetaplanAbductor — backward-chaining macro synthesis
# ---------------------------------------------------------------------------

class MetaplanAbductor:
    """Chains plans backward from a goal until the current state is reached.

    abduct(goal, state) -> {
      'macro': [plan names in execution order],
      'steps': flattened primitive steps,
      'explanation': English chain,
      'achieved': True/False  (True when a plan's precondition is satisfied
                               by the current state)
    }
    """

    def __init__(self, plans: List[Plan], max_depth: int = 6):
        self.plans = plans
        self.max_depth = max_depth

    # -- backward chaining -------------------------------------------------
    def abduct(self, goal: str, state: str,
               depth: int = 0) -> Optional[Dict[str, Any]]:
        goal = goal.lower()
        state = state.lower()
        if depth > self.max_depth:
            return None

        # direct: does any plan achieve the goal and apply in this state?
        for p in self.plans:
            if goal in p.effect and self._applicable(p.precondition, state):
                return {
                    "macro": [p.name], "steps": list(p.steps),
                    "explanation": f"{p.name} achieves '{goal}' and applies "
                                   f"here ('{state}' satisfies '{p.precondition}')",
                    "achieved": True,
                }

        # backward: plan achieves the goal; recursively achieve its precondition
        for p in self.plans:
            if goal not in p.effect:
                continue
            sub = self.abduct(p.precondition, state, depth + 1)
            if sub and sub.get("achieved"):
                steps = list(sub["steps"]) + list(p.steps)
                return {
                    "macro": sub["macro"] + [p.name],
                    "steps": steps,
                    "explanation": (f"{sub['explanation']}; then {p.name} "
                                    f"('{p.precondition}' -> '{p.effect}')"),
                    "achieved": True,
                }
        return None

    @staticmethod
    def _applicable(pre: str, state: str) -> bool:
        """Cheap applicability: all precondition atoms appear in state."""
        return all(a in state for a in atoms_of(pre)) if pre else True

    # -- generalization (roadmap item 3) -----------------------------------
    def generalize_on_success(self, plan_name: str) -> str:
        """Anti-unify all recorded success preconditions of a plan."""
        for p in self.plans:
            if p.name == plan_name:
                return general_precondition(p.success_preconditions)
        return "*"

    def record_success(self, plan_name: str, precondition: str) -> None:
        for p in self.plans:
            if p.name == plan_name and precondition not in p.success_preconditions:
                p.success_preconditions.append(precondition.lower())

    # -- persistence -------------------------------------------------------
    def save(self, path: str) -> None:
        json.dump([p.to_dict() for p in self.plans], open(path, "w"), indent=1)

    @classmethod
    def load(cls, path: str) -> "MetaplanAbductor":
        plans = []
        if os.path.exists(path):
            try:
                plans = [Plan.from_dict(d) for d in json.load(open(path))]
            except Exception:
                plans = []
        return cls(plans)

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
