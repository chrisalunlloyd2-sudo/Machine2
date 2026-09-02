"""BAYES ENGINE — the Banburismus decision loop (decibans).

Chris's formulation (2026-08-12): a BDI-style FSM loop where a Bayesian
log-odds ledger (BanLedger) accumulates evidence across ticks until a
transition threshold clears, at which point the gate fires and the FSM moves.

This is Turing's Banburismus made literal:

  1. PRIOR — before evidence, the full realm of hypotheses (all rotor setups /
     all possible tool actions). Each starts at 50/50 => 0 dBan.

  2. EVIDENCE — each observation updates a hypothesis by its LIKELIHOOD RATIO:
        LR = P(evidence | H) / P(evidence | not-H).
     LR > 1 lifts H, LR < 1 sinks it. A hypothesis that violates an explicit
     rule (precondition / crib) is ELIMINATED: P -> 0, log-odds -> -inf.

  3. LOG-ODDS — multiplying tiny probabilities is awkward, so Turing took
     log10. In decibans (dBan), 1 deciban = 0.1 ban = 10 * log10(odds).
     Updating becomes ADDITION: +10 dBan = 10x more likely; -10 dBan = 10x
     less likely. This is the BAN UNIT from ban.py, scaled x10 for fine grain.

  4. GATE — when a hypothesis's accumulated score clears the threshold
     (e.g. +20 dBan = 100:1 odds), it fires: execute the action, transition
     the FSM, reset the ledger for the new state. This is the "brute force
     until game = Nash" convergence: more evidence -> posterior concentrates
     -> one hypothesis dominates -> fire.

Two fixes vs. the original sketch:
  (a) PERSISTENCE — the ledger must SURVIVE across ticks (self.ledger), or
      evidence never accumulates and the gate can never fire. The original
      recreated the ledger inside step(), discarding all prior evidence.
  (b) THRESHOLD MATH — with the example's two evidence streams the score
      reaches 6.02 + 12.79 = 18.81 dBan, which is BELOW +20 dBan, so a third
      observation is required. The demo below uses three to actually fire.

Pure stdlib. Deterministic. Zero LLM.
"""
import enum
import math
from typing import Callable, Dict, List, Optional, Tuple

from .enigma_lock import nash_threshold
import threading

DECIBANS_PER_BAN = 10.0  # 1 ban = 10 decibans


def nash_threshold_dban(c_miss: float, c_false: float) -> float:
    """Nash gate threshold in DECIBANS (1 ban = 10 dBan).

    theta* = 10 * log10(C_miss / C_false). Fire the gate when a hypothesis's
    score exceeds theta*. This is the point where acting and not-acting have
    equal expected cost (the Nash equilibrium of the gate). It is the
    self-tuning coupling constant: as observed costs move, so does the bar.
    """
    return DECIBANS_PER_BAN * nash_threshold(c_miss, c_false)


class NashTuner:
    """Adaptive gate threshold — the "smarter = better" coupling.

    Tracks observed misses (should have fired, didn't) and false alarms
    (fired, shouldn't have), and returns the live Nash threshold
        theta* = 10 * log10(C_miss / C_false)
    where C_miss / C_false are running cost estimates = base prior + observed
    counts. Feed every real outcome back through record_miss /
    record_false_alarm and the gate converges to the equilibrium of its own
    cost structure, across every domain that shares the gate.

    NOTE on sign convention: the direction of self-tuning (does a miss raise or
    lower the bar?) follows the user's handwritten theta* = log10(C_miss /
    C_false). Verify against the offline derivation before treating the
    adaptive loop as authoritative — flipping the ratio (C_false / C_miss)
    reverses the convergence direction in one line (nash_threshold_dban).
    """

    def __init__(self, c_miss: float = 1.0, c_false: float = 1.0):
        self.base_c_miss = c_miss
        self.base_c_false = c_false
        self.misses = 0
        self.false_alarms = 0

    def record_miss(self) -> None:
        """We failed to fire when we should have."""
        self.misses += 1

    def record_false_alarm(self) -> None:
        """We fired when we should not have."""
        self.false_alarms += 1

    def threshold_dban(self) -> float:
        c_miss = self.base_c_miss + self.misses
        c_false = self.base_c_false + self.false_alarms
        return nash_threshold_dban(c_miss, c_false)


class BanLedger:
    """Bayesian evidence ledger in decibans (dBan).

    score = 10 * log10( odds )  where odds = P(H) / P(not-H).
    +10 dBan = 10:1 in favour; +20 dBan = 100:1; +30 dBan = 1000:1.
    """

    def __init__(self, threshold_dban: Optional[float] = None,
                 c_miss: Optional[float] = None, c_false: Optional[float] = None,
                 tuner: Optional["NashTuner"] = None):
        # Precedence: explicit fixed threshold > live tuner > Nash-derived
        # from costs. No magic constant: omitted costs default to
        # C_miss/C_false = 100/1 (the classic 20 dBan = 100:1 odds), so the
        # stop is ALWAYS theta* = 10 * log10(C_miss/C_false).
        if threshold_dban is None:
            if tuner is not None:
                threshold_dban = tuner.threshold_dban()
            else:
                threshold_dban = nash_threshold_dban(
                    100.0 if c_miss is None else c_miss,
                    1.0 if c_false is None else c_false)
        self.threshold_dban = threshold_dban
        self.c_miss = c_miss
        self.c_false = c_false
        self.tuner = tuner
        self.scores: Dict[str, float] = {}
        self._lock = threading.RLock()

    def _effective_threshold(self) -> float:
        """Live threshold: a NashTuner re-evaluates on every call so the gate
        self-tunes as outcomes are recorded; otherwise the fixed value holds."""
        if self.tuner is not None:
            return self.tuner.threshold_dban()
        return self.threshold_dban

    def register(self, hypothesis_id: str, prior_prob: float = 0.5):
        """Prior in dBan. 0.5 -> 0 dBan; 0.9 -> ~+9.54 dBan; 0.1 -> ~-9.54."""
        with self._lock:
            if prior_prob <= 0.0:
                self.scores[hypothesis_id] = float("-inf")
            elif prior_prob >= 1.0:
                self.scores[hypothesis_id] = float("inf")
            else:
                odds = prior_prob / (1.0 - prior_prob)
                self.scores[hypothesis_id] = DECIBANS_PER_BAN * math.log10(odds)

    def observe(self, hypothesis_id: str,
                p_evidence_given_h: float, p_evidence_given_not_h: float):
        """Fold in one observation: score += 10 * log10(LR)."""
        if hypothesis_id not in self.scores:
            return
        if self.scores[hypothesis_id] in (float("-inf"), float("inf")):
            return  # already decided; further evidence is moot
        if p_evidence_given_h == 0.0:
            self.scores[hypothesis_id] = float("-inf")   # contradiction
            return
        if p_evidence_given_not_h == 0.0:
            self.scores[hypothesis_id] = float("inf")    # logical certainty
            return
        lr = p_evidence_given_h / p_evidence_given_not_h
        with self._lock:
            self.scores[hypothesis_id] += DECIBANS_PER_BAN * math.log10(lr)

    def eliminate(self, hypothesis_id: str):
        """Hard rule violation (crib failure) -> probability zero."""
        with self._lock:
            self.scores[hypothesis_id] = float("-inf")

    def evaluate_gate(self) -> Optional[Tuple[str, float]]:
        """Return (best_hypothesis, score) if it clears the threshold, else None."""
        with self._lock:
            active = {k: v for k, v in self.scores.items() if v != float("-inf")}
            if not active:
                return None
            best_id = max(active, key=active.get)
            if active[best_id] >= self._effective_threshold():
                return best_id, active[best_id]
            return None

    def in_bans(self, hypothesis_id: str) -> float:
        """Convert a score to bans (1 ban = 10 dBan)."""
        s = self.scores.get(hypothesis_id, 0.0)
        if s in (float("-inf"), float("inf")):
            return s
        return s / DECIBANS_PER_BAN


class State(enum.Enum):
    IDLE = "IDLE"
    ANALYZING = "ANALYZING"
    EXECUTING_TOOL = "EXECUTING_TOOL"
    DONE = "DONE"


class TransitionRule:
    def __init__(self, target_state: State, action_name: str,
                 precondition_check: Callable[[dict], bool],
                 action_payload: Optional[Callable[[dict], None]] = None):
        self.target_state = target_state
        self.action_name = action_name
        self.precondition_check = precondition_check
        self.action_payload = action_payload


class BDIStateEngine:
    """FSM whose transitions are gated by a persistent BanLedger.

    The ledger LIVES on the engine (self.ledger) so evidence accumulates
    across ticks until a threshold clears. It resets only on a state change.
    """

    def __init__(self, threshold_dban: Optional[float] = None,
                 c_miss: Optional[float] = None, c_false: Optional[float] = None,
                 tuner: Optional[NashTuner] = None):
        self.current_state = State.IDLE
        self.context: dict = {}
        self.transitions: Dict[State, List[TransitionRule]] = {}
        self.threshold_dban = threshold_dban
        self.c_miss = c_miss
        self.c_false = c_false
        self.tuner = tuner
        self.ledger: Optional[BanLedger] = None
        self.history: List[dict] = []

    def add_transition(self, source_state: State, rule: TransitionRule):
        self.transitions.setdefault(source_state, []).append(rule)

    def _fresh_ledger(self) -> BanLedger:
        """(Re)register every candidate action at a neutral 50/50 prior."""
        ledger = BanLedger(threshold_dban=self.threshold_dban,
                           c_miss=self.c_miss, c_false=self.c_false,
                           tuner=self.tuner)
        for rule in self.transitions.get(self.current_state, []):
            ledger.register(rule.action_name, prior_prob=0.5)
        return ledger

    def step(self, incoming_evidence: List[dict]) -> Optional[Tuple[str, float]]:
        """One tick of the continuous thought/execution loop. Returns the fired
        (action, score) if the gate cleared this tick, else None."""
        valid_rules = self.transitions.get(self.current_state, [])
        if not valid_rules:
            return None  # terminal state

        # persist the ledger across ticks within the same state
        if self.ledger is None:
            self.ledger = self._fresh_ledger()

        # 1. Logic DAG / precondition gate (the "crib filter")
        active_rules: Dict[str, TransitionRule] = {}
        for rule in valid_rules:
            if not rule.precondition_check(self.context):
                self.ledger.eliminate(rule.action_name)
            else:
                active_rules[rule.action_name] = rule

        # 2. Sequential evidence processing (Bayesian reduction)
        for ev in incoming_evidence:
            action = ev.get("action")
            if action in active_rules:
                self.ledger.observe(action, ev["p_h"], ev["p_not_h"])

        # 3. Evaluate the transition gate
        fired = self.ledger.evaluate_gate()
        if fired:
            selected_action, dban_score = fired
            rule = active_rules[selected_action]
            if rule.action_payload:
                rule.action_payload(self.context)
            old = self.current_state
            self.current_state = rule.target_state
            self.history.append({
                "from": old.value, "to": self.current_state.value,
                "action": selected_action, "dban": round(dban_score, 2),
            })
            self.ledger = None  # reset for the new state
        return fired


def demo():
    """Run the worked example with THREE evidence streams so the gate fires."""
    ctx = {"user_intent": "query_database", "db_connected": True,
           "api_key_valid": False}
    engine = BDIStateEngine()   # defaults to theta* = 10*log10(100/1) = 20 dBan
    engine.context = ctx  # wire the world state into the engine

    engine.add_transition(State.IDLE, TransitionRule(
        target_state=State.EXECUTING_TOOL, action_name="exec_sql_query",
        precondition_check=lambda c: c.get("db_connected") is True,
        action_payload=lambda c: print("    [payload] EXEC SQL QUERY")))
    engine.add_transition(State.IDLE, TransitionRule(
        target_state=State.EXECUTING_TOOL, action_name="call_rest_api",
        precondition_check=lambda c: c.get("api_key_valid") is True,
        action_payload=lambda c: print("    [payload] CALL REST API")))

    print("=== TICK 1 ===")
    fired = engine.step([
        {"action": "exec_sql_query", "p_h": 0.8, "p_not_h": 0.2},   # +6.02
        {"action": "call_rest_api", "p_h": 0.9, "p_not_h": 0.1},    # DAG-eliminated
    ])
    print("    fired:", fired, "| scores:", {k: round(v,2) for k,v in engine.ledger.scores.items()})

    print("=== TICK 2 ===")
    fired = engine.step([
        {"action": "exec_sql_query", "p_h": 0.95, "p_not_h": 0.05},  # +12.79 => 18.81
    ])
    print("    fired:", fired, "| scores:", {k: round(v,2) for k,v in engine.ledger.scores.items()})

    print("=== TICK 3 ===")
    fired = engine.step([
        {"action": "exec_sql_query", "p_h": 0.9, "p_not_h": 0.1},    # +9.54 => 28.35 > 20
    ])
    print("    fired:", fired, "| state:", engine.current_state.value)


if __name__ == "__main__":
    demo()

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
