"""HAP — the Oz/Tok goal-directed reactive engine (Bates et al., CMU Oz).

From the Doyle survey (Oz/Tok section):
  Hap is Tok's goal-directed, reactive engine. Goals contain an atomic
  name + params, and DO NOT characterize world states (no explicit
  planning). Sets of actions (plans) are chosen from plan memory, which
  may hold one or more plans per goal. Plans have preconditions; if a
  plan fails, alternate plans are tried.

  The Active Plan Tree (APT) is an AND-OR tree: alternating layers of
  goal nodes and plan nodes. A plan node succeeds when ALL its subgoal
  children succeed (AND); a goal node succeeds via ANY applicable plan
  (OR). Root = persistent top-level goals.

  Theory of Activity loop: (1) revise the APT (evaluate context
  conditions + success tests, prune satisfied/failed), (2) pick a leaf
  goal via the goal arbiter (prefers high priority, then continuation
  of the current line, then plan specificity), (3) execute: primitive
  action, or expand the subgoal.

  Complements Aiception (BB1: WHAT to do) with HOW to do it.

  No cloud, no LLM. Pure stdlib.
"""

import time
from typing import Any, Dict, List, Optional


class Plan:
    """One plan in plan memory: how to achieve a goal."""

    def __init__(self, goal: str, name: str, steps: List[Dict[str, Any]],
                 precondition: Optional[Dict[str, Any]] = None,
                 context: Optional[Dict[str, Any]] = None,
                 specificity: float = 1.0):
        self.goal = goal              # goal name this plan achieves
        self.name = name
        self.steps = steps            # [{type: subgoal|action, name, params, priority_mod}]
        self.precondition = precondition or {}  # facts that must hold
        self.context = context or {}            # must stay true to make sense
        self.specificity = specificity          # more specific preferred

    def __repr__(self) -> str:
        return f"<Plan {self.name} for {self.goal} spec={self.specificity}>"


class HapEngine:
    def __init__(self):
        self.plan_memory: List[Plan] = []
        self.apt_root = {"type": "goal", "name": "ROOT", "priority": 0,
                         "children": [], "persistent": True}
        self.current_line: Optional[str] = None
        self.failed_plans: Dict[str, List[str]] = {}  # goal -> plan names tried
        self.stats = {"goals_posted": 0, "plans_selected": 0,
                      "actions": 0, "goals_satisfied": 0, "goals_failed": 0}

    # ---- plan memory -----------------------------------------------------
    def add_plan(self, plan: Plan) -> None:
        self.plan_memory.append(plan)

    def plans_for(self, goal: str, facts: Dict[str, Any]) -> List[Plan]:
        """Plans whose goal matches AND preconditions hold AND not already
        failed for this goal instance (never retry blindly — NMTD)."""
        tried = self.failed_plans.get(goal, [])
        out = []
        for p in self.plan_memory:
            if p.goal != goal or p.name in tried:
                continue
            if all(facts.get(k) == v for k, v in p.precondition.items()):
                out.append(p)
        out.sort(key=lambda p: -p.specificity)
        return out

    # ---- goals -------------------------------------------------------------
    def post_goal(self, name: str, priority: int = 5, params: Optional[Dict] = None,
                  persistent: bool = False) -> None:
        self.stats["goals_posted"] += 1
        self.apt_root["children"].append({
            "type": "goal", "name": name, "priority": priority,
            "params": params or {}, "children": [],
            "persistent": persistent, "status": "open",
        })

    def _goal_satisfied(self, node: Dict[str, Any], facts: Dict[str, Any]) -> bool:
        return bool(facts.get(f"goal:{node['name']}"))

    # ---- Theory of Activity: revise ----------------------------------------
    def revise(self, facts: Dict[str, Any]) -> int:
        """Step 1: prune satisfied/failed nodes; drop plans whose context
        condition no longer holds. Returns nodes pruned."""
        pruned = 0
        new_children = []
        for g in self.apt_root["children"]:
            if self._goal_satisfied(g, facts):
                self.stats["goals_satisfied"] += 1
                pruned += 1
                continue
            g["children"] = self._revise_plans(g, facts)
            new_children.append(g)
        self.apt_root["children"] = new_children
        return pruned

    def _revise_plans(self, goal: Dict, facts: Dict) -> List[Dict]:
        kept = []
        for pl in goal.get("children", []):
            if pl.get("status") == "succeeded":
                continue
            # plan succeeded if all subgoals done
            subs = pl.get("children", [])
            if subs and all(s.get("status") == "satisfied" for s in subs):
                pl["status"] = "succeeded"
                goal["status"] = "satisfied"
                self.stats["goals_satisfied"] += 1
                continue
            if pl.get("status") == "failed":
                continue
            kept.append(pl)
        return kept

    # ---- Theory of Activity: pick a leaf goal --------------------------------
    def arbiter_pick(self, facts: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Step 2: pick a leaf goal. Prefer high priority; tie -> continue
        the current line of expansion (persistence); then specificity."""
        leaves = self._leaf_goals()
        if not leaves:
            return None
        # priority first
        max_p = max(l["priority"] for l in leaves)
        top = [l for l in leaves if l["priority"] == max_p]
        if len(top) == 1:
            return top[0]
        # continuation preference: keep expanding the line we're on
        cont = [l for l in top if self._line_contains(l)]
        if len(cont) == 1:
            return cont[0]
        if cont:
            top = cont
        # then specificity of the plan that would expand this leaf
        best = None
        best_spec = -1.0
        for l in top:
            plans = self.plans_for(l["name"], facts)
            spec = plans[0].specificity if plans else 0.0
            if spec > best_spec:
                best_spec, best = spec, l
        return best or top[0]

    def _line_contains(self, leaf: Dict) -> bool:
        if not self.current_line:
            return False
        n = leaf
        while n is not None:
            if n.get("name") == self.current_line:
                return True
            n = n.get("_parent")
        return False

    def _leaf_goals(self) -> List[Dict[str, Any]]:
        out = []
        for g in self.apt_root["children"]:
            if g.get("status") == "open" and not g.get("children"):
                out.append(g)
        return out

    # ---- Theory of Activity: execute ----------------------------------------
    def execute(self, facts: Dict[str, Any]) -> Dict[str, Any]:
        """Step 3: expand the chosen leaf (plan) or return primitive action."""
        leaf = self.arbiter_pick(facts)
        if leaf is None:
            return {"action": "idle", "detail": "no open goals"}
        goal_name = leaf["name"]
        self.current_line = goal_name
        plans = self.plans_for(goal_name, facts)
        if not plans:
            leaf["status"] = "failed"
            self.stats["goals_failed"] += 1
            self.failed_plans.setdefault(goal_name, []).append("*exhausted*")
            return {"action": "goal_failed", "goal": goal_name,
                    "detail": f"no applicable plan for {goal_name}"}
        plan = plans[0]
        self.stats["plans_selected"] += 1
        plan_node = {"type": "plan", "name": plan.name, "goal": goal_name,
                     "children": [], "status": "active", "_parent": leaf}
        leaf["children"].append(plan_node)
        for step in plan.steps:
            if step["type"] == "action":
                self.stats["actions"] += 1
                plan_node["children"].append({
                    "type": "action", "name": step["name"],
                    "params": step.get("params", {}), "status": "done",
                    "_parent": plan_node})
                return {"action": step["name"], "goal": goal_name,
                        "plan": plan.name, "params": step.get("params", {}),
                        "detail": f"{plan.name}: {step['name']}"}
            plan_node["children"].append({
                "type": "goal", "name": step["name"],
                "priority": leaf["priority"] + step.get("priority_mod", 0),
                "params": step.get("params", {}), "children": [],
                "status": "open", "_parent": plan_node})
        # all steps were subgoals -> expand next round
        return {"action": "expand", "goal": goal_name, "plan": plan.name,
                "detail": f"expanded {plan.name} -> subgoals"}

    # ---- APT render (Aiception-style visibility) ------------------------------
    def render_apt(self) -> str:
        lines = [f"ACTIVE PLAN TREE — {time.strftime('%Y-%m-%d %H:%M:%S')}"]
        lines.append("ROOT (persistent goals)")
        self._render_node(self.apt_root, lines, "  ")
        return "\n".join(lines)

    def _render_node(self, node: Dict, lines: List[str], prefix: str) -> None:
        kids = node.get("children", [])
        if not kids:
            return
        for i, k in enumerate(kids):
            last = i == len(kids) - 1
            branch = "└─" if last else "├─"
            tag = {"goal": "GOAL", "plan": "PLAN", "action": "ACT"}[k.get("type", "?")]
            status = k.get("status", "")
            lines.append(f"{prefix}{branch} {tag} {k.get('name')}"
                         + (f" [{status}]" if status else ""))
            self._render_node(k, lines, prefix + ("   " if last else "│  "))

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
