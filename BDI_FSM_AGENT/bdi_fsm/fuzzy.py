"""fuzzy.py — fuzzy semantic sets (Zadeh), replacing strict ZFC membership.

Chris 2026-08-15: an element is not strictly in/out of a set (1/0). Language
grades each concept with a degree of membership in [0,1] — a probability cloud:
a sentence might be 0.8 "request for help", 0.4 "sarcasm", 0.1 "hostility".
Fuzzy boundaries are gradients, not cliffs. Deterministic, zero-LLM.
"""

from __future__ import annotations

import math
from typing import Callable, Dict, List


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


# --- membership-function builders -------------------------------------------

def trapezoid(a: float, b: float, c: float, d: float) -> Callable[[float], float]:
    """Standard trapezoidal membership: 0 at a, 1 in [b,c], 0 at d."""
    def mu(x: float) -> float:
        if x <= a or x >= d:
            return 0.0
        if b <= x <= c:
            return 1.0
        if a < x < b:
            return (x - a) / (b - a)
        return (d - x) / (d - c)
    return mu


def gaussian(center: float, sigma: float) -> Callable[[float], float]:
    def mu(x: float) -> float:
        return math.exp(-((x - center) ** 2) / (2 * sigma * sigma))
    return mu


def keyword_membership(keywords: List[str]) -> Callable[[str], float]:
    """Membership = fraction of keywords present in the text (partial credit)."""
    kws = [k.lower() for k in keywords]
    def mu(text: str) -> float:
        t = (text or "").lower()
        if not kws:
            return 0.0
        hits = sum(1 for k in kws if k in t)
        return hits / len(kws)
    return mu


class FuzzySet:
    """A named fuzzy semantic set over a universe."""

    def __init__(self, name: str, mu: Callable):
        self.name = name
        self.mu = mu

    def __call__(self, x) -> float:
        return clamp(self.mu(x))

    def __repr__(self) -> str:
        return f"FuzzySet({self.name!r})"


class FuzzySpace:
    """A universe of fuzzy sets; grades a text into a probability cloud."""

    def __init__(self):
        self.sets: Dict[str, FuzzySet] = {}

    def add(self, name: str, mu: Callable) -> "FuzzySpace":
        self.sets[name] = FuzzySet(name, mu)
        return self

    def grade(self, text) -> Dict[str, float]:
        """The probability cloud: {concept: degree of membership}."""
        return {n: s(text) for n, s in self.sets.items()}

    def best(self, text) -> str:
        cloud = self.grade(text)
        return max(cloud, key=cloud.get) if cloud else None
