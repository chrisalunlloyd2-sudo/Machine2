"""hdc.py — Hyperdimensional Computing / Vector Symbolic Architecture (VSA).

Chris 2026-08-15: map symbols/syntax into fixed-dimension bipolar hypervectors
(D=10000), then operate with three algebraic primitives:
    bind    (Hadamard product)   — associate a role with a filler (invertible)
    bundle  (majority vote)      — superpose constituents into a signature
    permute (cyclic bit-shift)   — encode sequence/order (orthogonalizes)

Deterministic (seeded), zero-LLM, single-core, stdlib-only. The duplicate gate
uses the ADAPTIVE NASH THRESHOLD (enigma_lock.nash_threshold) instead of a
magic 0.50 inner-product cutoff: same code iff similarity_ban(cosine) >= theta*.
"""

from __future__ import annotations

import hashlib
import math
import random
from typing import List, Optional, Tuple

DIMENSION = 10000


class Hypervector:
    """A bipolar {-1,+1}^D vector."""

    __slots__ = ("data",)

    def __init__(self, data: List[int]):
        self.data = data

    @staticmethod
    def random(seed: int, D: int = DIMENSION) -> "Hypervector":
        rng = random.Random(seed)
        return Hypervector([1 if rng.random() < 0.5 else -1 for _ in range(D)])

    @staticmethod
    def from_string(s: str, D: int = DIMENSION) -> "Hypervector":
        seed = int(hashlib.sha256(s.encode("utf-8")).hexdigest(), 16)
        return Hypervector.random(seed, D)

    @staticmethod
    def bundle_many(vectors: List["Hypervector"], D: Optional[int] = None) -> "Hypervector":
        """Superposition (majority vote) of many vectors into one signature."""
        if not vectors:
            raise ValueError("cannot bundle an empty list")
        D = D or len(vectors[0].data)
        sums = [0] * D
        for v in vectors:
            for i in range(D):
                sums[i] += v.data[i]
        return Hypervector([1 if s >= 0 else -1 for s in sums])

    def bind(self, other: "Hypervector") -> "Hypervector":
        """Hadamard (component-wise) product — role/filler binding."""
        return Hypervector([a * b for a, b in zip(self.data, other.data)])

    def bundle(self, other: "Hypervector") -> "Hypervector":
        """Pairwise majority-vote superposition."""
        return Hypervector([1 if (a + b) >= 0 else -1
                            for a, b in zip(self.data, other.data)])

    def permute(self, shift: int = 1) -> "Hypervector":
        """Cyclic shift — sequence/order encoding (the rotor step)."""
        s = shift % len(self.data)
        return Hypervector(self.data[s:] + self.data[:s])

    def cosine(self, other: "Hypervector") -> float:
        D = len(self.data)
        return sum(a * b for a, b in zip(self.data, other.data)) / D

    def __xor__(self, other): return self.bind(other)
    def __add__(self, other): return self.bundle(other)
    def __repr__(self): return f"Hypervector(D={len(self.data)})"


def code_signature(code: str, D: int = DIMENSION, n: int = 4) -> Optional[Hypervector]:
    """N-gram sliding + positional permute + bundle -> a module signature."""
    if not code:
        return None
    grams = [code[i:i + n] for i in range(len(code) - n + 1)] or [code]
    vecs = []
    for pos, g in enumerate(grams):
        hv = Hypervector.from_string(g, D)
        vecs.append(hv.permute(pos))
    return Hypervector.bundle_many(vecs, D)


def similarity_ban(similarity: float) -> float:
    """Cosine similarity in [-1,1] -> log-odds in BANS (monotonic logit)."""
    s = max(-0.999999, min(0.999999, similarity))
    return 10.0 * math.log10((1.0 + s) / (1.0 - s))


def same_code_gate(similarity: float, c_miss: float, c_false: float) -> bool:
    """Adaptive duplicate gate: fire when similarity_ban >= nash_threshold.

    This replaces the magic 0.50 inner-product cutoff with the same
    decision-theoretic theta* used across the agent (log10(C_miss/C_false)).
    """
    from .enigma_lock import nash_threshold
    return similarity_ban(similarity) >= nash_threshold(c_miss, c_false)


class CodeSignatureStore:
    """Never-make-code-twice: store signatures, dedupe via the Nash gate."""

    def __init__(self, D: int = DIMENSION, c_miss: float = 1000.0, c_false: float = 1.0):
        self.D = D
        self.c_miss = c_miss
        self.c_false = c_false
        self.entries: List[Tuple[str, Hypervector]] = []

    def add(self, code_id: str, code: str) -> Hypervector:
        sig = code_signature(code, self.D)
        self.entries.append((code_id, sig))
        return sig

    def lookup(self, code: str) -> dict:
        sig = code_signature(code, self.D)
        if sig is None or not self.entries:
            return {"duplicate": False, "best_similarity": None, "best_id": None}
        best_id, best_sim = None, -1.0
        for code_id, stored in self.entries:
            s = sig.cosine(stored)
            if s > best_sim:
                best_sim, best_id = s, code_id
        return {
            "duplicate": same_code_gate(best_sim, self.c_miss, self.c_false),
            "best_similarity": round(best_sim, 4),
            "best_id": best_id,
            "ban": round(similarity_ban(best_sim), 2),
        }

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
