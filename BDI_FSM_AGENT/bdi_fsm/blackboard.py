"""BB1 / Hearsay-II shared blackboard bus.

The single source of truth the whole agent reasons over:
facts (beliefs), an event register, and plan fitness scores.
Pure stdlib, deterministic, bounded memory.
"""

import json
import time
from typing import Any, Dict, List, Optional


class Blackboard:
    """Central shared memory bus for state, events and plan scoring."""

    def __init__(self, max_events: int = 500):
        self.facts: Dict[str, Any] = {}
        self.event_log: List[Dict[str, Any]] = []
        self.plan_fitness: Dict[str, float] = {}
        self.max_events = max_events

    # -- facts (beliefs) ------------------------------------------------
    def assert_fact(self, key: str, value: Any) -> None:
        self.facts[key] = value

    def get_fact(self, key: str, default: Any = None) -> Any:
        return self.facts.get(key, default)

    def has_fact(self, key: str) -> bool:
        return key in self.facts

    def retract_fact(self, key: str) -> None:
        self.facts.pop(key, None)

    # -- events ---------------------------------------------------------
    def emit_event(self, source: str, event_type: str, details: Optional[Dict[str, Any]] = None) -> None:
        self.event_log.append({
            "ts": time.time(),
            "source": source,
            "type": event_type,
            "details": details or {},
        })
        if len(self.event_log) > self.max_events:
            self.event_log = self.event_log[-self.max_events:]

    def recent_events(self, n: int = 20) -> List[Dict[str, Any]]:
        return self.event_log[-n:]

    # -- plan fitness ----------------------------------------------------
    def set_fitness(self, plan_id: str, score: float) -> None:
        self.plan_fitness[plan_id] = score

    def get_fitness(self, plan_id: str, default: float = 0.0) -> float:
        return self.plan_fitness.get(plan_id, default)

    # -- serialization ----------------------------------------------------
    def snapshot(self) -> Dict[str, Any]:
        return {
            "facts": self.facts,
            "events": self.event_log[-50:],
            "fitness": self.plan_fitness,
        }

    def to_json(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.snapshot(), f, indent=2)

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
