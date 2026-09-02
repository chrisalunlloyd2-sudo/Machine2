"""AICEPTION — explicit control decisions as a decision tree.

BB1 (Hayes-Roth 1985) control problem, implemented as a decision tree:

  "Make explicit control decisions that solve the control problem.
   Decide what actions to perform by reconciling independent decisions
   about what actions are DESIRABLE and what actions are FEASIBLE.
   Adopt variable grain-size control heuristics that focus on whatever
   action attributes are useful in the current problem-solving domain."

Levels (in importance order, top-down — each level is a node in the
decision tree):

  PROBLEM        what problem are we solving?        (root)
  STRATEGY       general plan for the episode
  FOCUS          local objectives: rate candidates by attribute-value
                 pairs (variable grain: fine/medium/coarse)
  POLICY         global scheduling criteria (long-lived)
  TO-DO-SET      FEASIBLE actions (preconditions true) vs triggered
  CHOSEN-ACTION  the winner + rationale (which Foci/Policies led)

Desirability comes from Focus + Policy weights; feasibility from the
To-Do-Set gate. The Chosen-Action is the feasible candidate with the
highest desirability. The whole path renders as an ASCII tree so every
auto-choice is inspectable.

No cloud, no LLM. Pure stdlib.
"""

import time
from typing import Any, Dict, List, Optional


class AiceptionTree:
    def __init__(self):
        self.problem = {"domain": "unknown", "description": ""}
        self.strategy = {"description": ""}
        self.foci: List[Dict[str, Any]] = []      # in importance order
        self.policies: List[Dict[str, Any]] = []
        self.candidates: List[Dict[str, Any]] = []
        self.rejected: List[Dict[str, Any]] = []  # infeasible/guardrailed
        self.chosen: Optional[Dict[str, Any]] = None
        self.score: float = 0.0
        self.rationale: List[str] = []
        self.ts = time.time()

    # ---- level setters --------------------------------------------------
    def set_problem(self, domain: str, description: str) -> "AiceptionTree":
        self.problem = {"domain": domain, "description": description}
        return self

    def set_strategy(self, description: str) -> "AiceptionTree":
        self.strategy = {"description": description}
        return self

    def add_focus(self, attr: str, value: Any, weight: float,
                  grain: str = "medium", label: str = "") -> "AiceptionTree":
        """Local objective: rate candidates whose `attr` matches `value`.
        grain: fine (single attr), medium (attr group), coarse (all)."""
        self.foci.append({"attr": attr, "value": value, "weight": weight,
                          "grain": grain, "label": label or f"{attr}={value}"})
        return self

    def add_policy(self, attr: str, value: Any, weight: float,
                   label: str = "") -> "AiceptionTree":
        """Global scheduling criterion (operative until episode end)."""
        self.policies.append({"attr": attr, "value": value, "weight": weight,
                              "label": label or f"{attr}={value}"})
        return self

    # ---- matching --------------------------------------------------------
    @staticmethod
    def _matches(attr_value: Any, cond: Any) -> bool:
        if isinstance(cond, dict):
            # numeric range conditions: {"min":x,"max":y,"gt":x,"lt":x}
            try:
                n = float(attr_value)
                if "min" in cond and n < float(cond["min"]):
                    return False
                if "max" in cond and n > float(cond["max"]):
                    return False
                if "gt" in cond and n <= float(cond["gt"]):
                    return False
                if "lt" in cond and n >= float(cond["lt"]):
                    return False
                return True
            except (TypeError, ValueError):
                return False
        if cond == "*":
            return attr_value is not None
        return attr_value == cond

    def _desirability(self, cand: Dict[str, Any]) -> float:
        """Sum of Focus + Policy weights matching this candidate."""
        score = 0.0
        hits = []
        for foc in self.foci:
            if self._matches(cand.get(foc["attr"]), foc["value"]):
                score += float(foc["weight"])
                hits.append(f"focus {foc['label']} +{foc['weight']}")
        for pol in self.policies:
            if self._matches(cand.get(pol["attr"]), pol["value"]):
                score += float(pol["weight"])
                hits.append(f"policy {pol['label']} +{pol['weight']}")
        return score, hits

    # ---- the decision -----------------------------------------------------
    def evaluate(self, candidates: List[Dict[str, Any]],
                 blocked: Optional[List[str]] = None) -> Dict[str, Any]:
        """Reconcile desirability vs feasibility. Chosen-Action = feasible
        candidate with the highest desirability (importance order)."""
        blocked = blocked or []
        self.candidates = list(candidates)
        best: Optional[Dict[str, Any]] = None
        best_score = -1.0
        best_hits: List[str] = []
        for c in candidates:
            name = str(c.get("name", c.get("action", "?")))
            # To-Do-Set feasibility gate
            if c.get("blocked") or name in blocked:
                self.rejected.append({**c, "why": "infeasible"})
                continue
            score, hits = self._desirability(c)
            if score > best_score:
                best_score, best, best_hits = score, c, hits
        self.chosen = best
        self.score = best_score
        self.rationale = best_hits
        if best is None:
            return {"action": "idle", "score": 0.0,
                    "detail": "no feasible candidate"}
        return {"action": best.get("action", "execute"),
                "name": best.get("name"),
                "score": best_score,
                "rationale": best_hits,
                "detail": f"{best.get('name')} score={best_score:.2f}"}

    # ---- ASCII render ------------------------------------------------------
    def render_ascii(self) -> str:
        lines = []
        lines.append(f"AICEPTION DECISION TREE — {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.ts))}")
        lines.append(f"PROBLEM: {self.problem['domain']} — {self.problem['description']}")
        lines.append(f"├─ STRATEGY: {self.strategy['description']}")
        # foci in importance order
        lines.append("│  ├─ FOCUS (importance order):")
        if self.foci:
            for i, f in enumerate(self.foci, 1):
                last = (i == len(self.foci))
                branch = "└─" if last else "├─"
                lines.append(f"│  │  {branch} [{i}] {f['label']} weight={f['weight']} grain={f['grain']}")
        else:
            lines.append("│  │  └─ (none)")
        # policies
        lines.append("│  ├─ POLICY:")
        if self.policies:
            for i, p in enumerate(self.policies, 1):
                last = (i == len(self.policies))
                branch = "└─" if last else "├─"
                lines.append(f"│  │  {branch} [{i}] {p['label']} weight={p['weight']}")
        else:
            lines.append("│  │  └─ (none)")
        # to-do-set
        lines.append("│  ├─ TO-DO-SET (feasible):")
        feas = [c for c in self.candidates
                if not (c.get("blocked") or str(c.get("name", c.get("action", "?"))) in
                        [r.get("name") for r in self.rejected])]
        if feas:
            for i, c in enumerate(feas, 1):
                last = (i == len(feas))
                branch = "└─" if last else "├─"
                lines.append(f"│  │  {branch} {c.get('name')} ({c.get('action')})")
        else:
            lines.append("│  │  └─ (none)")
        if self.rejected:
            lines.append("│  │  └─ REJECTED:")
            for i, r in enumerate(self.rejected, 1):
                last = (i == len(self.rejected))
                branch = "└─" if last else "├─"
                lines.append(f"│  │     {branch} {r.get('name')} — {r.get('why', 'blocked')}")
        # chosen action
        if self.chosen is not None:
            lines.append(f"│  └─ CHOSEN-ACTION: {self.chosen.get('name')} ({self.chosen.get('action')}) score={self.score:.2f}")
            if self.rationale:
                lines.append(f"│     └─ rationale: {' · '.join(self.rationale)}")
        else:
            lines.append("│  └─ CHOSEN-ACTION: none (idle)")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "problem": self.problem, "strategy": self.strategy,
            "foci": self.foci, "policies": self.policies,
            "candidates": self.candidates, "rejected": self.rejected,
            "chosen": self.chosen, "score": self.score,
            "rationale": self.rationale, "ts": self.ts,
        }
