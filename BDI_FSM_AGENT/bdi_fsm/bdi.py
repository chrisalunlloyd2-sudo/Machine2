"""Belief-Desire-Intention planner with Subsumption arbitration.

* Beliefs   -> blackboard facts
* Desires   -> high-level goals (resolve_slot, fix_syntax, ...)
* Intentions-> active plans: precondition -> tool action -> postcondition

Subsumption: plans declare a priority; higher-priority plans (safety /
architecture) inhibit lower-priority reactive plans. Deterministic.
"""

import re
from typing import Any, Callable, Dict, List, Optional


class BDIPlan:
    """Plan schema: preconditions -> tool action -> postconditions."""

    def __init__(self, name: str, preconditions: List[str],
                 tool_action: str, action_args: Optional[Dict[str, Any]] = None,
                 priority: int = 100, postconditions: Optional[List[str]] = None,
                 desire: str = "general"):
        """Init.

        Args: name, preconditions, tool_action, action_args, priority, postconditions, desire.
        """
        self.name = name
        self.preconditions = preconditions
        self.tool_action = tool_action
        self.action_args = action_args or {}
        self.priority = priority          # lower number = higher priority
        self.postconditions = postconditions or []
        self.desire = desire


class BDIEngine:
    """Symbolic BDI engine: evaluates preconditions against blackboard,
    dispatches tools through a registry, applies postconditions."""

    def __init__(self, blackboard, tool_registry):
        """Init.

        Args: blackboard, tool_registry.
        """
        self.bb = blackboard
        self.tools = tool_registry          # dict name -> callable(**args)
        self.plan_library: List[BDIPlan] = []
        self.desires: List[str] = []        # active desire stack
        self.intentions: List[str] = []     # active plan names
        self.step_count = 0

    def add_plan(self, plan: BDIPlan) -> "BDIEngine":
        """Add plan.

        Args: plan.
        """
        self.plan_library.append(plan)
        self.plan_library.sort(key=lambda p: p.priority)
        return self

    def set_desire(self, desire: str) -> None:
        """Set desire.

        Args: desire.
        """
        if desire not in self.desires:
            self.desires.append(desire)

    def clear_desires(self) -> None:
        """Clear desires (function)."""
        self.desires = []

    def evaluate_preconditions(self, plan: BDIPlan) -> bool:
        """Evaluate preconditions.

        Args: plan.
        """
        for cond in plan.preconditions:
            cond = cond.strip()
            if not cond:
                continue
            if cond.startswith("has_"):
                if not self.bb.has_fact(cond):
                    return False
                continue
            if cond.startswith("not_"):
                key = cond[4:]
                if self.bb.has_fact(key):
                    return False
                continue
            # key == value | key != value | key >= n | key < n
            m = re.match(r"^(\w+)\s*(==|!=|>=|<=|>|<)\s*(.+)$", cond)
            if m:
                key, op, val = m.group(1), m.group(2), m.group(3)
                fact = self.bb.get_fact(key)
                if fact is None:
                    return False
                try:
                    if op == "==":
                        if str(fact).strip() != val.strip():
                            return False
                    elif op == "!=":
                        if str(fact).strip() == val.strip():
                            return False
                    else:
                        f = float(fact); v = float(val)
                        if op == ">=" and not f >= v: return False
                        if op == "<=" and not f <= v: return False
                        if op == ">" and not f > v: return False
                        if op == "<" and not f < v: return False
                except (TypeError, ValueError):
                    return False
                continue
            # bare fact truthiness
            if not self.bb.get_fact(cond):
                return False
        return True

    def step(self) -> Optional[str]:
        """One subsumption cycle: pick the highest-priority applicable plan,
        run its tool, apply postconditions. Returns plan name or None."""
        for plan in self.plan_library:
            # Subsumption: a desire filter — plans bound to a desire only
            # run while that desire is active.
            if plan.desire != "general" and plan.desire not in self.desires:
                continue
            if self.evaluate_preconditions(plan):
                self._execute(plan)
                return plan.name
        return None

    def _execute(self, plan: BDIPlan) -> None:
        self.intentions.append(plan.name)
        self.step_count += 1
        tool = self.tools.get(plan.tool_action)
        if tool is None:
            self.bb.emit_event("bdi", "missing_tool", {"tool": plan.tool_action})
            return
        try:
            result = tool(**plan.action_args)
            if isinstance(result, dict):
                for k, v in result.items():
                    self.bb.assert_fact(k, v)
        except Exception as e:  # tool failures become facts, not crashes
            self.bb.assert_fact("last_tool_error", str(e))
            self.bb.emit_event("bdi", "tool_error",
                               {"plan": plan.name, "error": str(e)})
        for post in plan.postconditions:
            self.bb.assert_fact(post, True)
        self.bb.emit_event("bdi", "intention", {"plan": plan.name})

    def run(self, max_steps: int = 100) -> int:
        """Run until quiescence (no plan fires). Returns steps taken."""
        n = 0
        while n < max_steps:
            if self.step() is None:
                break
            n += 1
        return n

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
