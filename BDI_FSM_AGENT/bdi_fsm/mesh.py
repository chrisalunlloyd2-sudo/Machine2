"""CELLULAR MESH — v0.3.0 multi-agent hex fog grid + quorum voting.

The endpoint (origin cell) receives an INTENT ASK (a want -> machine intent),
decomposes it into sub-goals, and distributes them across hex cells in spiral
order (expanding into fog). Each cell ACTS on its sub-goal through the shared
RegimeDriver; a successful action POPULATES the cell (reveals it and its
neighbours). A cell whose gate impasses (no vector recommends an action) is
handed to the SEARCH FALLBACK, which webcrawls the intent's subject into the
corpus to break the loop.

Quorum voting resolves shared decisions by majority, with a deterministic
tie-break. Pure stdlib. Deterministic. Zero LLM.
"""
from typing import Any, Dict, List, Optional, Tuple

from .hex_grid import Fog, HexGrid, spiral
from .cell import HexCell
from .intent import Intent, decompose
from .arch_regimes import RegimeDriver

IMPASSE_ACTIONS = (None, "idle", "none")


class CellularMesh:
    """A hex grid of cells, each hosting local BDI state + a shared engine."""

    def __init__(self, radius: int = 3, engine: Optional[RegimeDriver] = None,
                 threshold_dban: float = 20.0):
        self.radius = radius
        self.grid = HexGrid(radius=radius)
        self.engine = engine or RegimeDriver()
        self.threshold_dban = threshold_dban
        self.origin = (0, 0)
        self.cells: Dict[Tuple[int, int], HexCell] = {}
        for coord in spiral(self.origin, radius):
            self.cells[coord] = HexCell(*coord, threshold_dban=threshold_dban)
        # occupy the endpoint
        self.cells[self.origin].fog = Fog.OCCUPIED
        self.cells[self.origin].agent_id = "endpoint"
        self.grid.set_fog(*self.origin, Fog.OCCUPIED)

    # ---- cell assignment --------------------------------------------------
    def assign_cell(self, index: int) -> Tuple[int, int]:
        """The index-th cell in the deterministic spiral explore order."""
        order = spiral(self.origin, self.radius)
        return order[index % len(order)]

    # ---- acting -----------------------------------------------------------
    def _candidates_for(self, sub_goal: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Deterministic candidate actions for a sub-goal (drives the agenda
        regime). One candidate per sub-goal, weighted by confidence."""
        conf = float(sub_goal.get("confidence", 0.5))
        if conf <= 0.0:
            return []   # unrecognized want -> nothing close -> impasse -> search
        verb = sub_goal.get("verb", "do")
        obj = sub_goal.get("object", "")
        name = f"{verb}_{obj.replace(' ', '_')}" if obj else verb
        return [{"name": name, "action": verb, "weight": max(conf, 0.01),
                 "object": obj}]

    def _act(self, cell: HexCell, sub_goal: Dict[str, Any]) -> Dict[str, Any]:
        """Run the cell's decision through the engine; flag an impasse."""
        cell.intent = f"{sub_goal.get('verb', '')} {sub_goal.get('object', '')}".strip()
        cell.assert_fact("intent_verb", sub_goal.get("verb", ""))
        cell.assert_fact("intent_object", sub_goal.get("object", ""))
        ctx = {
            "facts": dict(cell.facts),
            "candidates": self._candidates_for(sub_goal),
            "pool": None,
            "situation": cell.intent,
        }
        decision = self.engine.decide(ctx, record=False)
        impasse = decision.get("action") in IMPASSE_ACTIONS
        return {"impasse": impasse, "decision": decision, "cell": cell.coord}

    # ---- intent routing ---------------------------------------------------
    def submit_intent(self, intent: Intent, search=None) -> Dict[str, Any]:
        """Route an intent ask: decompose, distribute to cells in spiral order,
        act, populate fog, and aggregate. On impasse, invoke the search fallback.
        """
        goals = decompose(intent)
        results: List[Dict[str, Any]] = []
        explored = 0
        searched = 0
        for i, sg in enumerate(goals):
            coord = self.assign_cell(i)
            cell = self.cells[coord]
            outcome = self._act(cell, sg)
            if outcome["impasse"]:
                # anti-loop: search the subject into the corpus, then re-act
                if search is not None:
                    fb = search(intent, cell)
                    outcome["search"] = fb
                    if fb.get("injected", 0) > 0:
                        searched += 1
                        outcome = self._act(cell, sg)
                        outcome["search"] = fb
            if not outcome["impasse"]:
                self.grid.reveal(*coord)
                cell.fog = self.grid.fog(*coord)
                explored += 1
            results.append({"coord": coord, "sub_goal": sg, **outcome})
        return {
            "intent": intent.key,
            "sub_goals": len(goals),
            "explored": explored,
            "searched": searched,
            "results": results,
            "fog": self.grid.counts(),
        }

    # ---- quorum voting ----------------------------------------------------
    def quorum(self, votes: Dict[str, float]) -> Tuple[str, Dict[str, float]]:
        """Majority vote with deterministic tie-break (highest weight, then
        lexicographically largest option). Returns (winner, tally)."""
        tally: Dict[str, float] = {}
        for opt, w in votes.items():
            tally[opt] = tally.get(opt, 0.0) + w
        if not tally:
            return "", tally
        winner = max(tally, key=lambda k: (tally[k], k))
        return winner, tally

    # ---- snapshot ---------------------------------------------------------
    def snapshot(self) -> Dict[str, Any]:
        return {
            "radius": self.radius,
            "origin": list(self.origin),
            "fog": self.grid.snapshot(),
            "cells": {f"{q},{r}": c.to_dict() for (q, r), c in sorted(self.cells.items())},
        }
