"""VECTORED TERMINAL DRIVER — the agent-architecture survey as code.

Source: Patrick Doyle, "AI Qual Summary" (June 3, 1997) — the classic
survey of agent architectures (Atlantis, BB1, Maes, Oz/Tok, Pengi,
PRODIGY, PRS, RCS, Situated Automata, SOAR, Subsumption).

Each architecture contributes one DECISION VECTOR: a pure, deterministic
module that maps a decision context to a recommendation. The DRIVER
routes every decision through the vector stack in priority order
(subsumption-style: a higher vector can SUPPRESS a lower one), records
the decision + outcome in the action journal, and yields the winning
action. Learning (NMTD guardrails, skill-library hits) feeds back into
the PRODIGY control-rule vector so the driver gets better with use.

No cloud, no LLM. Every decision is a pure function of context facts.
"""

import json
import os
import time

from .aiception import AiceptionTree
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# VECTOR BASE
# ---------------------------------------------------------------------------
class Vector:
    """One architecture-derived decision vector.

    priority: higher subsumes (suppresses) lower vectors.
    evaluate(ctx) -> {"action": str|None, "detail": str, "score": 0..1}
    A None action means "no recommendation from this vector."
    """

    name = "vector"
    priority = 0

    def __init__(self):
        self.calls = 0
        self.wins = 0

    def evaluate(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<Vector {self.name} p={self.priority} wins={self.wins}>"


# ---------------------------------------------------------------------------
# ATLANTIS — controller/sequencer/deliberator layering (Gat 1991)
# ---------------------------------------------------------------------------
class AtlantisReflexVector(Vector):
    """The CONTROLLER layer: moment-by-moment reactions to current facts.
    Internal state guides but never directly controls (Gat's thesis)."""

    name = "atlantis-controller"
    priority = 90  # reflexes dominate

    def evaluate(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        facts = ctx.get("facts", {})
        if facts.get("controller_active") is False:
            return {"action": "seek_controller",
                    "detail": "no local LLM or human controller active",
                    "score": 1.0}
        if facts.get("journal_fail_rate", 0) > 0.5:
            return {"action": "heal",
                    "detail": f"fail rate {facts['journal_fail_rate']:.2f} > 0.5",
                    "score": 0.95}
        if facts.get("disk_free_mb", 10**9) < 200:
            return {"action": "prune",
                    "detail": f"disk low: {facts['disk_free_mb']}MB",
                    "score": 0.9}
        return {"action": None, "detail": "", "score": 0.0}


class AtlantisSequencerVector(Vector):
    """The SEQUENCER layer: RAP-style task queue with method fallbacks.
    A task carries a list of methods; on failure the next method is tried
    (cognizant failure — detect, don't prevent)."""

    name = "atlantis-sequencer"
    priority = 60

    def evaluate(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        pool = ctx.get("pool")
        if pool is None:
            return {"action": None, "detail": "", "score": 0.0}
        task = pool.next_open(prefer="probe")
        if task is None:
            return {"action": None, "detail": "", "score": 0.0}
        return {"action": "run_pool_task",
                "detail": f"task {task.get('id')}: {str(task.get('task'))[:80]}",
                "score": 0.8}


# ---------------------------------------------------------------------------
# BB1 — blackboard control: agenda of KSARs (Hayes-Roth 1985)
# ---------------------------------------------------------------------------
class BB1AgendaVector(Vector):
    """The BB1 control loop: enumerate pending KSARs -> rate -> choose ->
    execute. Candidates carry weights (Focus/Policy ratings); the highest
    executable candidate is chosen (To-Do-Set -> Chosen-Action)."""

    name = "bb1-agenda"
    priority = 50

    def evaluate(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        candidates = ctx.get("candidates") or []
        if not candidates:
            return {"action": None, "detail": "", "score": 0.0}
        # rate: weight * executability
        rated = []
        for c in candidates:
            w = float(c.get("weight", 1.0))
            exec_ok = not c.get("blocked", False)
            rated.append((w if exec_ok else 0.0, c))
        rated.sort(key=lambda x: -x[0])
        w, best = rated[0]
        if w <= 0:
            return {"action": None, "detail": "", "score": 0.0}
        return {"action": best.get("action", "execute"),
                "detail": f"KSAR {best.get('name', '?')} weight={w:.2f}",
                "score": min(1.0, w / 2.0)}


# ---------------------------------------------------------------------------
# MAES — behavior networks: activation spreading (Maes 1989)
# ---------------------------------------------------------------------------
class MaesActivationVector(Vector):
    """Competence modules + activation energy. env support + goal support +
    successor spread; executable node above threshold with highest
    activation wins. Link weights = reliability (learned S/T)."""

    name = "maes-activation"
    priority = 40

    def __init__(self):
        super().__init__()
        self.links: Dict[tuple, List[int]] = {}  # (src, dst) -> [S, T]

    def learn_link(self, src: str, dst: str, success: bool) -> None:
        key = (src, dst)
        if key not in self.links:
            self.links[key] = [1, 2]
        else:
            s, t = self.links[key]
            self.links[key] = [s + (1 if success else 0), t + 1]

    def reliability(self, src: str, dst: str) -> float:
        # Maes prior: unknown links start neutral (S0/T0 = 1/1 = 1.0),
        # never zero — zero would kill all activation before learning.
        s, t = self.links.get((src, dst), [1, 1])
        return s / max(1, t)

    def evaluate(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        nodes = ctx.get("nodes") or []
        if not nodes:
            return {"action": None, "detail": "", "score": 0.0}
        best = None
        best_act = -1.0
        for n in nodes:
            env = float(n.get("env_support", 0))
            goal = float(n.get("goal_support", 0))
            succ = float(n.get("successor_support", 0))
            act = 0.4 * env + 0.4 * goal + 0.2 * succ
            act *= self.reliability(ctx.get("last_action", ""), n.get("name", ""))
            if act > best_act and act >= float(ctx.get("threshold", 0.3)):
                best_act = act
                best = n
        if best is None:
            return {"action": None, "detail": "", "score": 0.0}
        return {"action": best.get("action", "execute"),
                "detail": f"maes node {best.get('name')} activation={best_act:.2f}",
                "score": min(1.0, best_act)}


# ---------------------------------------------------------------------------
# PRODIGY — control rules: select / reject / prefer (Carbonell et al.)
# ---------------------------------------------------------------------------
class ProdigyControlVector(Vector):
    """Control knowledge = rules that reduce search. Rules are SELECT,
    REJECT, or PREFER over candidates. NMTD guardrails become REJECT
    rules; skill-library hits become SELECT rules (compression: learned
    rules beat search)."""

    name = "prodigy-control"
    priority = 70  # learned control knowledge dominates raw search

    def __init__(self, guardrails_path: Optional[str] = None):
        super().__init__()
        self.guardrails_path = guardrails_path
        self._rules: List[Dict[str, str]] = []
        self.last_rejected: List[str] = []
        self.reload()

    def reload(self) -> None:
        if self.guardrails_path and os.path.exists(self.guardrails_path):
            try:
                for line in open(self.guardrails_path, encoding="utf-8"):
                    line = line.strip()
                    if not line:
                        continue
                    rec = json.loads(line)
                    self._rules.append({
                        "trigger": rec.get("trigger", "").lower(),
                        "rule": rec.get("rule", ""),
                    })
            except Exception:
                pass

    def add_guardrail(self, trigger: str, rule: str) -> None:
        self._rules.append({"trigger": trigger.lower(), "rule": rule})
        if self.guardrails_path:
            os.makedirs(os.path.dirname(self.guardrails_path) or ".", exist_ok=True)
            with open(self.guardrails_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"trigger": trigger, "rule": rule}) + "\n")

    def evaluate(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        candidates = ctx.get("candidates") or []
        if not candidates:
            return {"action": None, "detail": "", "score": 0.0}
        # REJECT phase: drop candidates matching a guardrail trigger
        kept = []
        rejected = []
        for c in candidates:
            name = str(c.get("name", c.get("action", ""))).lower()
            action = str(c.get("action", "")).lower()
            # guardrail trigger matches name OR action
            if any(r["trigger"] in name or r["trigger"] in action
                   for r in self._rules):
                rejected.append(c.get("name", "?"))
            else:
                kept.append(c)
        self.last_rejected = rejected
        if not kept:
            return {"action": None,
                    "detail": f"all candidates rejected by control rules ({rejected})",
                    "score": 0.0}
        # PREFER phase: weighted order
        kept.sort(key=lambda c: -float(c.get("weight", 1.0)))
        best = kept[0]
        self.last_rejected = rejected
        return {"action": best.get("action", "execute"),
                "detail": f"control-selected {best.get('name')}"
                          + (f" (rejected {rejected})" if rejected else ""),
                "score": min(1.0, float(best.get("weight", 1.0)))}


# ---------------------------------------------------------------------------
# SOAR — preferences + impasses (Laird, Newell 1982)
# ---------------------------------------------------------------------------
class SoarPreferenceVector(Vector):
    """Preferences (accept/reject/better/worse/indifferent) + decision
    procedure. A TIE impasse (multiple max choices, no discriminator)
    triggers a subgoal: defer, gather info, or pick random among
    indifferent maxima. Chunking = cache the winning preference."""

    name = "soar-preferences"
    priority = 55

    def __init__(self):
        super().__init__()
        self.chunks: Dict[str, str] = {}  # situation-fingerprint -> action
        self.impasse_count = 0

    def chunk(self, situation: str, action: str) -> None:
        """Learn-by-experience: cache the winning decision (SOAR chunking)."""
        self.chunks[situation] = action

    def evaluate(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        candidates = ctx.get("candidates") or []
        sit = str(ctx.get("situation", ""))
        # chunk lookup first (compiled knowledge, like SOAR chunks)
        if sit and sit in self.chunks:
            return {"action": self.chunks[sit], "detail": f"chunk hit {sit}",
                    "score": 1.0}
        if not candidates:
            return {"action": None, "detail": "", "score": 0.0}
        prefs = ctx.get("preferences") or {}  # name -> better/worse/reject/indifferent
        accepted = [c for c in candidates if prefs.get(c.get("name")) != "reject"]
        if not accepted:
            return {"action": None, "detail": "all candidates rejected", "score": 0.0}
        max_w = max(float(c.get("weight", 1.0)) for c in accepted)
        maxima = [c for c in accepted if float(c.get("weight", 1.0)) == max_w]
        if len(maxima) > 1:
            # TIE impasse: no discriminator among maxima
            self.impasse_count += 1
            if ctx.get("resolve_tie_random"):
                import random
                choice = random.choice(maxima)
                return {"action": choice.get("action", "execute"),
                        "detail": f"tie impasse resolved randomly -> {choice.get('name')}",
                        "score": 0.5}
            return {"action": "defer",
                    "detail": f"tie impasse among {[m.get('name') for m in maxima]}",
                    "score": 0.3}
        return {"action": maxima[0].get("action", "execute"),
                "detail": f"preference-selected {maxima[0].get('name')}",
                "score": 0.7}


# ---------------------------------------------------------------------------
# PRS — intention structure (Georgeff & Lansky 1987)
# ---------------------------------------------------------------------------
class PrsIntentionVector(Vector):
    """Knowledge Areas (plans w/ invocation conditions) + intention stack.
    Suspended intentions re-activate when their condition is met; the
    top intention executes next. Metalevel KAs can override (priority)."""

    name = "prs-intentions"
    priority = 45

    def __init__(self):
        super().__init__()
        self.intentions: List[Dict[str, Any]] = []  # [{name, condition, action, priority}]

    def post(self, name: str, condition: str, action: str, priority: int = 5) -> None:
        self.intentions.append({"name": name, "condition": condition,
                                "action": action, "priority": priority})

    def evaluate(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        facts = ctx.get("facts", {})
        for it in sorted(self.intentions, key=lambda x: -x["priority"]):
            cond = it["condition"]
            if cond in facts and facts[cond] is True:
                return {"action": it["action"],
                        "detail": f"intention activated: {it['name']}",
                        "score": 0.75}
        return {"action": None, "detail": "", "score": 0.0}


# ---------------------------------------------------------------------------
# THE DRIVER
# ---------------------------------------------------------------------------
class VectoredDriver:
    """Routes every decision through the vector stack.

    Subsumption semantics: vectors run highest-priority first; the first
    vector with a non-None action WINS and suppresses the rest (Brooks'
    suppression/inhibition wires, realized as priority ordering).
    Every decision + outcome is journaled (recording behavior).
    """

    def __init__(self, journal=None):
        self.vectors: List[Vector] = []
        self.journal = journal
        self.history_path = None

    def register(self, vector: Vector) -> "VectoredDriver":
        self.vectors.append(vector)
        self.vectors.sort(key=lambda v: -v.priority)
        return self

    def decide(self, ctx: Dict[str, Any], agent: str = "bdi-fsm-agent",
               record: bool = True, aiception: bool = True) -> Dict[str, Any]:
        for v in self.vectors:
            v.calls += 1
            rec = v.evaluate(ctx)
            if rec.get("action"):
                v.wins += 1
                decision = {"vector": v.name, "action": rec["action"],
                            "detail": rec.get("detail", ""), "score": rec.get("score", 0.0),
                            "ts": time.time()}
                if record and self.journal is not None:
                    self.journal.record(agent, f"vector:{v.name}:{rec['action']}",
                                        rec.get("detail", ""), "ok")
                if aiception:
                    self._build_aiception(ctx, decision)
                return decision
        decision = {"vector": "none", "action": "idle",
                    "detail": "no vector recommended an action", "score": 0.0,
                    "ts": time.time()}
        if aiception:
            self._build_aiception(ctx, decision)
        return decision

    def _build_aiception(self, ctx: Dict[str, Any],
                         decision: Dict[str, Any]) -> AiceptionTree:
        """Render the winning decision as an explicit BB1 control tree."""
        tree = AiceptionTree()
        tree.set_problem(
            domain=str(ctx.get("situation") or "agent-decision"),
            description=decision.get("detail", "")[:120])
        tree.set_strategy(
            "route through vector stack in priority order; desirability "
            "reconciled against feasibility at the To-Do-Set gate")
        candidates = ctx.get("candidates") or []
        # Build Focus/Policy heuristics from the active vector that won
        # (variable grain: fine for candidate attrs, coarse for global).
        tree.add_focus("class", "*", 1.0, grain="coarse",
                       label="all candidates are executable")
        if decision.get("vector") == "prodigy-control":
            tree.add_policy("source", "skill", 1.5, label="prefer learned skills")
            tree.add_policy("blocked", True, -99.0, label="reject guarded")
        if decision.get("vector") == "atlantis-sequencer":
            tree.add_focus("priority", {"min": 0}, 2.0, grain="fine",
                           label="priority>=1")
            tree.add_policy("done", False, 1.0, label="skip done")
        if decision.get("vector") == "soar-preferences":
            tree.add_policy("weight", {"min": 0}, 1.0, label="accept positives")
        # Candidates -> To-Do-Set (feasibility gate: blocked attrs +
        # rejections recorded by the winning vector, e.g. PRODIGY guardrails)
        blocked = [c.get("name") for c in candidates if c.get("blocked")]
        for v in self.vectors:
            if v.name == decision.get("vector"):
                blocked += list(getattr(v, "last_rejected", []) or [])
        cands = candidates or [{"name": decision.get("action"),
                                "action": decision.get("action"),
                                "class": "chosen", "blocked": False}]
        tree.evaluate(cands, blocked=blocked)
        # Force the chosen action to match the actual decision
        if tree.chosen is None:
            tree.chosen = {"name": decision.get("action"),
                           "action": decision.get("action")}
            tree.score = decision.get("score", 0.0)
        self.last_tree = tree
        self.last_render = tree.render_ascii()
        return tree

    def stats(self) -> Dict[str, Any]:
        return {v.name: {"calls": v.calls, "wins": v.wins, "priority": v.priority}
                for v in self.vectors}

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
