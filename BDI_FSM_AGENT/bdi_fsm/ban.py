"""
BAN — the hartley/ban/dit unit as the SOUL of the agent (Chris 2026-08-11).

Definitions (Wikipedia — "Hartley (unit)"):
    The hartley (symbol Hart), also called a BAN, or a DIT (short for
    "decimal digit"), is a logarithmic unit that measures information or
    entropy, based on base-10 logarithms and powers of 10.
    One hartley is the information content of an event if the probability
    of that event occurring is 1/10. It equals the information contained
    in one decimal digit (dit), assuming a priori equiprobability.

    Base-2 -> shannon (bit):  event with p = 1/2.
    Natural -> nat:           powers of e.
    1 ban = ln(10) nat ~ 2.303 nat = log2(10) Sh ~ 3.322 Sh (3.322 bit).

THE SOUL (step by step):
    Every step of the agent is measured in bans.
        H = -SUM p * log10(p)        uncertainty (entropy), in bans
        gain = H_before - H_after    information a step actually carries
        certainty = 10^(-H_remaining)   100% certainty <=> 0 bans of
                                        uncertainty remain

    STEP-BY-STEP DOCTRINE:
        1. measure uncertainty BEFORE the step (bans)
        2. act
        3. measure uncertainty AFTER the step (bans)
        4. gain = before - after
        5. remaining entropy = 0 bans  -> task 100% complete (certitude)
        6. gain ~ 0 bans -> the step carried NO information -> step back,
           assess, redo (a zero-ban step is a wasted step — this is the ban
           soul of the certitude gate: a step that adds nothing is a NO-GO)

    One canonical ban: choosing 1 of 10 equiprobable digits carries
    exactly 1.000 ban of information (hartley(10) = log10(10) = 1).

Deterministic, pure stdlib, zero LLM.
"""

import math

LOG10 = math.log(10.0)
BITS_PER_BAN = math.log2(10.0)   # ~ 3.321928
NATS_PER_BAN = math.log(10.0)    # ~ 2.302585


class Ban:
    """Static information theory in bans (base 10)."""

    @staticmethod
    def self_info(p: float) -> float:
        """Self-information of an event with probability p, in bans.
        I(p) = -log10(p).  p = 0.1 -> 1.000 ban (the definition)."""
        if p <= 0.0:
            return float("inf")
        if p > 1.0:
            raise ValueError("probability must be <= 1.0")
        return -math.log10(p)

    @staticmethod
    def hartley(n: int) -> float:
        """Information of choosing 1 of n equiprobable outcomes, in bans.
        hartley(n) = log10(n).  n=10 -> 1.000 ban = one dit."""
        if n < 1:
            raise ValueError("n must be >= 1")
        return math.log10(n)

    @staticmethod
    def entropy(probs) -> float:
        """Shannon entropy of a probability distribution, in bans.
        H = -SUM p * log10(p).  Fair 10-way -> 1.000 ban."""
        total = 0.0
        for p in probs:
            if p < 0.0:
                raise ValueError("negative probability")
            if p > 0.0:
                total -= p * math.log10(p)
        return total

    @staticmethod
    def kl(p, q) -> float:
        """KL divergence D_KL(p || q) in bans = SUM p log10(p/q)."""
        total = 0.0
        for pi, qi in zip(p, q):
            if pi > 0.0:
                if qi <= 0.0:
                    return float("inf")
                total += pi * math.log10(pi / qi)
        return total

    @staticmethod
    def to_bits(bans: float) -> float:
        return bans * BITS_PER_BAN

    @staticmethod
    def to_nats(bans: float) -> float:
        return bans * NATS_PER_BAN

    @staticmethod
    def from_bits(bits: float) -> float:
        return bits / BITS_PER_BAN

    @staticmethod
    def certainty(entropy_bans: float) -> float:
        """Certainty = 10^(-H). H=0 -> 1.0 (100%). H=1 -> 0.1 (10%)."""
        return 10.0 ** (-max(entropy_bans, 0.0))


class BanLedger:
    """Step-by-step ban accounting — the soul running the agent.

    Every step logs: name, uncertainty before (bans), after (bans),
    info gain (bans), certainty after. The task is 100% complete when
    remaining entropy = 0 bans. A step with ~0 gain is a wasted step.
    """

    def __init__(self, eps: float = 1e-9, min_gain_bans: float = 0.0):
        self.steps = []
        self.eps = eps
        self.min_gain_bans = min_gain_bans
        self._H = 0.0   # persistent current uncertainty (bans)

    def step(self, name: str, before_probs, after_probs) -> dict:
        h0 = Ban.entropy(before_probs)
        h1 = Ban.entropy(after_probs)
        gain = h0 - h1
        entry = {
            "step": name,
            "H_before_bans": round(h0, 6),
            "H_after_bans": round(h1, 6),
            "gain_bans": round(gain, 6),
            "certainty_after": round(Ban.certainty(h1), 6),
            "ts": __import__("time").time(),
        }
        self.steps.append(entry)
        self._H = h1          # persistent state: uncertainty AFTER this step
        return entry

    def remaining(self) -> float:
        """Persistent current uncertainty in bans (0 if fully resolved)."""
        return self._H

    def is_done(self) -> bool:
        """100% complete: 0 bans of uncertainty remain."""
        return self.remaining() <= self.eps

    def total_gain(self) -> float:
        return sum(s["gain_bans"] for s in self.steps)

    def wasted_steps(self) -> list:
        """Steps that carried ~0 bans of information (the soul says: redo)."""
        return [s for s in self.steps if s["gain_bans"] <= self.eps]

    def verdict(self, name: str, before_probs, after_probs) -> dict:
        """The ban gate: GO if the step carried real information
        (gain >= min_gain_bans), else STEP_BACK (zero-ban step = wasted)."""
        h_before_step = self.remaining()   # persistent state BEFORE this step
        entry = self.step(name, before_probs, after_probs)
        gain = entry["gain_bans"]
        if gain < self.min_gain_bans:
            return {**entry, "verdict": "STEP_BACK",
                    "why": f"info gain {gain} bans < min {self.min_gain_bans}"}
        if gain <= self.eps and h_before_step > self.eps:
            # zero-ban step while uncertainty REMAINED = wasted -> step back
            return {**entry, "verdict": "STEP_BACK",
                    "why": "zero-ban step while uncertainty remains (wasted)"}
        if self.is_done():
            return {**entry, "verdict": "DONE",
                    "why": "0 bans of uncertainty remain (100%)"}
        return {**entry, "verdict": "GO",
                "why": f"carried {gain} bans of information"}

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
