"""ARCHITECTURE REGIMES — each reference architecture as a STATE; the BDI
meta-controller chooses which combination is active.

Chris directive (2026-08-13): the classic agent architectures all overlap
heavily — they define the same systems (controller / sequencer / deliberator,
blackboard / scheduler, knowledge areas, control rules, behavior layers). They
differ mainly in WHERE they put the control problem, not in what pieces exist.

So instead of running every architecture as a fixed subsumption priority stack
(arch_vectors.VectoredDriver — Brooks suppression, always-on), each one becomes
a REGIME: a named, BDI-selected combination of the existing decision vectors.
The deliberator picks the control regime from blackboard facts; the chosen
regime's vectors then produce the actual action.

This is Atlantis's thesis made literal (Gat): state is maintained at a HIGH
level of abstraction and used to GUIDE action, not control it directly. The
meta-controller (deliberator) guides; the regime's vectors (sequencer/controller)
control. It is also BB1's control-vs-domain split: selecting the regime IS the
control decision, decoupled from the domain action.

Pure stdlib. Deterministic. Zero LLM.
"""
import re
import threading
from typing import Any, Callable, Dict, List, Optional

from .arch_vectors import (Vector, AtlantisReflexVector, AtlantisSequencerVector,
                           BB1AgendaVector, MaesActivationVector,
                           ProdigyControlVector, SoarPreferenceVector,
                           PrsIntentionVector)


def _facts_ok(condition: str, facts: Dict[str, Any]) -> bool:
    """Evaluate one BDI precondition against blackboard facts.

    Supported: has_X, not_X, key==value, key!=value, key>=n, key<=n, key>n,
    key<n, and a bare key (truthiness). Mirrors bdi.BDIEngine's language.
    """
    condition = condition.strip()
    if not condition:
        return True
    if condition.startswith("has_"):
        return bool(facts.get(condition[4:]))
    if condition.startswith("not_"):
        return not bool(facts.get(condition[4:]))
    m = re.match(r"^(\w+)\s*(==|!=|>=|<=|>|<)\s*(.+)$", condition)
    if m:
        key, op, val = m.group(1), m.group(2), m.group(3)
        fact = facts.get(key)
        if fact is None:
            return False
        try:
            if op == "==":
                return str(fact).strip() == val.strip()
            if op == "!=":
                return str(fact).strip() != val.strip()
            f, v = float(fact), float(val)
            if op == ">=":
                return f >= v
            if op == "<=":
                return f <= v
            if op == ">":
                return f > v
            if op == "<":
                return f < v
        except (TypeError, ValueError):
            return False
        return False
    return bool(facts.get(condition))


class Regime:
    """A named control regime = a combination of decision vectors + an
    activation condition. Equivalent to one 'state' of the meta-controller."""

    def __init__(self, name: str, vectors: List[Vector], description: str,
                 requires: Optional[List[str]] = None,
                 preconditions: Optional[List[str]] = None):
        self.name = name
        self.vectors = sorted(vectors, key=lambda v: -v.priority)
        self.description = description
        self.requires = requires or []       # ctx keys that must be present (AND)
        self.preconditions = preconditions or []  # fact conditions (AND)
        self.activations = 0

    def active(self, ctx: Dict[str, Any]) -> bool:
        """True if the regime's structural triggers AND fact preconditions hold."""
        facts = ctx.get("facts", {})
        for key in self.requires:
            if not ctx.get(key):
                return False
        for cond in self.preconditions:
            if not _facts_ok(cond, facts):
                return False
        return True

    def __repr__(self) -> str:
        return f"<Regime {self.name} vectors={[v.name for v in self.vectors]}>"




# ---------------------------------------------------------------------------
# The default regime set (the 'states' of the meta-controller).
# Each regime is activated by a predicate over ctx facts/keys. Ordering here
# is selection priority: the FIRST active regime wins (BB1: reconcile
# desirability against feasibility).
# ---------------------------------------------------------------------------
def build_default_regimes() -> List[Regime]:
    """Return the standard architecture regimes, highest-priority first."""

    def reflex_active(ctx):
        f = ctx.get("facts", {})
        return (f.get("controller_active") is False
                or float(f.get("journal_fail_rate", 0)) > 0.5
                or float(f.get("disk_free_mb", 10**9)) < 200)

    def impasse_active(ctx):
        return bool(ctx.get("impasse"))

    def sequence_active(ctx):
        pool = ctx.get("pool")
        return bool(pool and getattr(pool, "next_open", None))

    def agenda_active(ctx):
        return bool(ctx.get("candidates"))

    def activate_active(ctx):
        return bool(ctx.get("nodes"))

    def learn_active(ctx):
        # PRODIGY control rules or SOAR chunks are worth consulting whenever
        # candidates exist AND we have learned knowledge to filter/select them.
        return bool(ctx.get("candidates") and ctx.get("learned"))

    regimes = [
        Regime("reflex",
               [AtlantisReflexVector()],
               "React to reflex facts (fail rate, disk low, controller down).",
               requires=None),
        Regime("impasse",
               [SoarPreferenceVector()],
               "SOAR: resolve a tie/conflict impasse by deferring or chunking.",
               requires=["impasse"]),
        Regime("learn",
               [ProdigyControlVector(), SoarPreferenceVector()],
               "PRODIGY + SOAR: filter/select via learned control rules + chunks.",
               requires=["candidates", "learned"]),
        Regime("sequence",
               [AtlantisSequencerVector(), PrsIntentionVector()],
               "Atlantis sequencer + PRS: run the task queue / activate intentions.",
               requires=["pool"]),
        Regime("agenda",
               [BB1AgendaVector()],
               "BB1: schedule the highest-weight executable KSAR.",
               requires=["candidates"]),
        Regime("activate",
               [MaesActivationVector()],
               "Maes: pick the most-activated behavior node.",
               requires=["nodes"]),
    ]
    # attach the predicates (kept out of __init__ so regimes stay plain data)
    preds = {
        "reflex": reflex_active,
        "impasse": impasse_active,
        "learn": learn_active,
        "sequence": sequence_active,
        "agenda": agenda_active,
        "activate": activate_active,
    }
    for r in regimes:
        r._active_fn = preds[r.name]
    return regimes


class RegimeDriver:
    """Meta-controller: choose the active regime, then decide within it.

    This is the BDI 'deliberator' layer on top of arch_vectors.VectoredDriver.
    Instead of a fixed all-vectors subsumption stack, it (1) selects the regime
    whose activation holds, then (2) routes the decision through only that
    regime's vectors in subsumption order. If no regime activates, it falls
    back to the full vector stack (the prior behavior), so a decision is
    always produced.
    """

    def __init__(self, regimes: Optional[List[Regime]] = None,
                 journal=None, default_vector: Optional[Vector] = None):
        self.regimes = regimes if regimes is not None else build_default_regimes()
        self.journal = journal
        # fallback = run every distinct vector once (back-compat subsumption)
        all_vecs: Dict[str, Vector] = {}
        for r in self.regimes:
            for v in r.vectors:
                all_vecs.setdefault(v.name, v)
        self._fallback_vectors = sorted(all_vecs.values(), key=lambda v: -v.priority)
        self._lock = threading.RLock()

    def select_regime(self, ctx: Dict[str, Any]) -> Regime:
        """Return the first active regime (highest priority), or None."""
        for r in self.regimes:
            if r._active_fn(ctx) and r.active(ctx):
                with self._lock:
                    r.activations += 1
                return r
        return None

    def decide(self, ctx: Dict[str, Any], agent: str = "bdi-fsm-agent",
               record: bool = True) -> Dict[str, Any]:
        """Select regime + decide within it. Returns {regime, vector, action, ...}."""
        regime = self.select_regime(ctx)
        vectors = regime.vectors if regime is not None else self._fallback_vectors
        for v in vectors:
            rec = v.evaluate(ctx)
            if rec.get("action"):
                decision = {"regime": regime.name if regime else "default",
                            "vector": v.name, "action": rec["action"],
                            "detail": rec.get("detail", ""),
                            "score": rec.get("score", 0.0)}
                if record and self.journal is not None:
                    self.journal.record(agent, f"regime:{regime.name if regime else 'default'}:{v.name}:{rec['action']}",
                                        rec.get("detail", ""), "ok")
                return decision
        return {"regime": regime.name if regime else "default",
                "vector": "none", "action": "idle",
                "detail": "no vector in the active regime recommended an action",
                "score": 0.0}

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            out = {}
            for r in self.regimes:
                out[r.name] = {"activations": r.activations,
                               "vectors": [v.name for v in r.vectors]}
            return out


if __name__ == "__main__":
    d = RegimeDriver()
    # reflex situation
    print(d.decide({"facts": {"controller_active": False}}))
    print(d.decide({"facts": {"journal_fail_rate": 0.7}}))
    # agenda situation
    print(d.decide({"candidates": [{"name": "x", "action": "do_x", "weight": 2.0}]}))
    print(d.stats())

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
