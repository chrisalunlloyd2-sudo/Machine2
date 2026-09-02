"""HEX CELL — one fogged cell of the cellular mesh.

A cell hosts the LOCAL state an agent needs to act on a sub-goal: a blackboard
(facts), an FSM (the state tree), and a BanLedger (evidence for the intent's
hypotheses). Decision *logic* (the RegimeDriver) is shared at the mesh level —
cells are state loci, not full agents, so a mesh of many cells stays cheap.

Pure stdlib. Deterministic.
"""
from typing import Any, Dict, Optional

from .fsm import FSM
from .bayes_engine import BanLedger
from .hex_grid import Fog


class HexCell:
    """A single hex cell: coordinates + fog + local BDI state."""

    def __init__(self, q: int, r: int, fog: Fog = Fog.UNKNOWN,
                 threshold_dban: float = 20.0):
        self.q = q
        self.r = r
        self.fog = fog
        self.facts: Dict[str, Any] = {}
        self.fsm = FSM(initial_state="IDLE")
        self.ledger = BanLedger(threshold_dban=threshold_dban)
        self.agent_id: Optional[str] = None
        self.intent: Optional[str] = None

    @property
    def coord(self):
        return (self.q, self.r)

    @property
    def occupied(self) -> bool:
        return self.agent_id is not None

    def assert_fact(self, key: str, value: Any) -> None:
        self.facts[key] = value

    def register_hypothesis(self, hid: str, prior_prob: float = 0.5) -> None:
        self.ledger.register(hid, prior_prob=prior_prob)

    def observe(self, hid: str, p_h: float, p_not_h: float) -> None:
        self.ledger.observe(hid, p_evidence_given_h=p_h, p_evidence_given_not_h=p_not_h)

    def to_dict(self) -> Dict[str, Any]:
        return {"q": self.q, "r": self.r, "fog": self.fog.value,
                "agent_id": self.agent_id, "intent": self.intent,
                "facts": dict(self.facts)}
