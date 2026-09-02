"""PHONOTACTICS — the token-stream guardrail (a DFA *is* an FSM).

Chris's mapping (2026-08-12): speech is a continuous acoustic wave; its
DISCRETE abstraction is a stream of phoneme tokens. The set of valid token
strings is a regular language L_valid over the phoneme alphabet Σ, recognised
by a deterministic finite automaton M = (Q, Σ, δ, q₀, F):

    Q  : phonetic states        (START, ONSET, NUCLEUS, CODA, END)
    Σ  : phoneme alphabet       (the token stream)
    δ  : Q × Σ -> Q             transition function (allowed sound sequences)
    q₀ : START                  initial state
    F  : {END}                  accepting state

An undefined transition δ(q, a) is the CRIB: the string leaves L_valid and
the hypothesis is eliminated. "Starting a word with /ftr/" is invalid for the
same structural reason that E(x)=x is invalid in Enigma, and that a syntax
error is invalid in the AST patcher. One principle — the ban/crib gate — in
three domains.

This module implements:

  1. SequenceDFA — a generic, data-driven DFA for ANY token alphabet (phonemes,
     shell-command tokens, action sequences, code tokens). The formal object.
  2. EnglishSyllableDFA — the phonotactic instance, with the Sonority
     Sequencing Principle as the crib (a sonority FALL in the onset is illegal,
     except the extra-syllabic /s/ cluster — so /str/ is valid, /ftr/ is not).
  3. Bark-scale formant space — vowels as coordinates in ℝ³ (F1, F2, F3),
     mapped to the Bark scale so perceptual distance ≈ ban distance.
  4. Isochrony — stress-timed rhythm: intervals between stressed syllables are
     ~constant; deviation from isochrony is evidence (in dBan).
  5. score_with_ledger — feed a token stream through the Banburismus ledger:
     each legal transition is +evidence, an illegal one is -inf (eliminate).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

try:
    from .bayes_engine import BanLedger, DECIBANS_PER_BAN
except ImportError:  # pragma: no cover - standalone invocation
    from bayes_engine import BanLedger, DECIBANS_PER_BAN


# ---------------------------------------------------------------------------
# Sonority — the acoustic substrate (why a DFA has the shape it does)
# ---------------------------------------------------------------------------

SONORITY = {
    "vowel": 4,
    "glide": 3,      # /w/ /j/
    "liquid": 2,     # /l/ /r/
    "nasal": 1,      # /m/ /n/ /ŋ/
    "fricative": 0,  # /f/ /s/ /ʃ/ ...
    "stop": -1,      # /p/ /t/ /k/ /b/ /d/ /g/
}


@dataclass(frozen=True)
class Phoneme:
    symbol: str
    cls: str  # sonority class

    @property
    def sonority(self) -> int:
        return SONORITY[self.cls]


# ---------------------------------------------------------------------------
# 1. SequenceDFA — the formal object (Q, Σ, δ, q₀, F)
# ---------------------------------------------------------------------------

@dataclass
class DFAResult:
    valid: bool
    path: List[Tuple[str, str, str]] = field(default_factory=list)
    failing: Optional[Tuple[str, str]] = None  # (state, symbol) where δ is undefined
    end_state: Optional[str] = None


class SequenceDFA:
    """A generic deterministic finite automaton over a symbol->class mapping.

    δ is a dict {(state, cls) -> next_state}. Missing keys are the undefined
    transitions — the crib that rejects a token stream. State-visibility is
    preserved: rejections report the EXACT (state, symbol) that failed, so the
    FSM knows *why* a sequence left the language, not just that it did.
    """

    def __init__(self, delta: Dict[Tuple[str, str], str],
                 start: str = "START", accepting: Optional[set] = None):
        self.delta = delta
        self.start = start
        self.accepting = accepting or {"END"}

    def accept(self, tokens: List[Phoneme]) -> DFAResult:
        state = self.start
        path: List[Tuple[str, str, str]] = []
        for tok in tokens:
            nxt = self.delta.get((state, tok.cls))
            if nxt is None:
                return DFAResult(False, path=path,
                                 failing=(state, tok.symbol),
                                 end_state=state)
            path.append((state, tok.symbol, nxt))
            state = nxt
        # empty-string / termination handling is the caller's concern; here the
        # stream must end in an accepting state (or an explicit END token).
        return DFAResult(state in self.accepting, path=path, end_state=state)


# ---------------------------------------------------------------------------
# 2. EnglishSyllableDFA — phonotactics with the Sonority Sequencing crib
# ---------------------------------------------------------------------------

# Small but real English phoneme inventory (symbol -> class).
PHONEMES = {
    # stops
    "p": Phoneme("p", "stop"), "t": Phoneme("t", "stop"),
    "k": Phoneme("k", "stop"), "b": Phoneme("b", "stop"),
    "d": Phoneme("d", "stop"), "g": Phoneme("g", "stop"),
    # fricatives
    "f": Phoneme("f", "fricative"), "s": Phoneme("s", "fricative"),
    # nasals
    "m": Phoneme("m", "nasal"), "n": Phoneme("n", "nasal"),
    # liquids
    "l": Phoneme("l", "liquid"), "r": Phoneme("r", "liquid"),
    # glides
    "w": Phoneme("w", "glide"), "j": Phoneme("j", "glide"),
    # vowels (nucleus)
    "a": Phoneme("a", "vowel"), "i": Phoneme("i", "vowel"),
    "u": Phoneme("u", "vowel"), "e": Phoneme("e", "vowel"),
    "o": Phoneme("o", "vowel"),
}


class EnglishSyllableDFA:
    """Phonotactic grammar of an English syllable.

    The state machine is START -> ONSET -> NUCLEUS -> CODA -> END. The crib is
    the Sonority Sequencing Principle (SSP):

      * onset sonority must be NON-DECREASING toward the nucleus, with ONE
        exception — /s/ may precede a stop (the "extra-syllabic s": /st/, /sp/,
        /sk/, /str/, /spl/, /skr/).
      * coda sonority must be NON-INCREASING away from the nucleus.

    So /str/ is valid (s-cluster + rising t->r) but /ftr/ is NOT (f->t is a
    sonority fall with no s-exception). This mirrors Enigma's "no fixed point":
    an illegal sonority contour is a contradiction, eliminating the string.
    """

    def __init__(self):
        self.start = ("START", None, None)  # (phase, last_sonority, last_symbol)

    def _delta(self, phase: str, last_s, last_sym,
               tok: Phoneme) -> Optional[Tuple[str, int, str]]:
        s = tok.sonority
        if phase == "START":
            if tok.cls == "vowel":
                return ("NUCLEUS", s, tok.symbol)
            return ("ONSET", s, tok.symbol)
        if phase == "ONSET":
            if tok.cls == "vowel":
                return ("NUCLEUS", s, tok.symbol)
            # consonant: a sonority FALL is illegal (SSP), except /s/->stop
            if last_s is not None and s < last_s:
                if last_sym == "s" and tok.cls == "stop":
                    return ("ONSET", s, tok.symbol)  # extra-syllabic s-cluster
                return None  # CRIB: illegal onset fall
            return ("ONSET", s, tok.symbol)
        if phase == "NUCLEUS":
            if tok.cls == "vowel":
                return ("NUCLEUS", s, tok.symbol)  # diphthong / vowel cluster
            return ("CODA", s, tok.symbol)
        if phase == "CODA":
            if tok.cls == "vowel":
                return None  # CRIB: vowel after coda
            if last_s is not None and s > last_s:
                return None  # CRIB: sonority RISE in coda
            return ("CODA", s, tok.symbol)
        return None

    def accept(self, tokens: List[Phoneme]) -> DFAResult:
        """tokens: a list of Phoneme objects (the token stream)."""
        state = self.start
        path = []
        for tok in tokens:
            phase, last_s, last_sym = state
            nxt = self._delta(phase, last_s, last_sym, tok)
            if nxt is None:
                return DFAResult(False, path=path,
                                 failing=(phase, tok.symbol), end_state=phase)
            path.append((phase, tok.symbol, nxt[0]))
            state = nxt
        # a well-formed syllable ends in NUCLEUS or CODA (has a vowel)
        ok = state[0] in ("NUCLEUS", "CODA")
        return DFAResult(ok, path=path, end_state=state[0])

    def accept_word(self, word: str) -> DFAResult:
        """Convenience: accept a string of phoneme symbols, e.g. 'strin'."""
        tokens = []
        for ch in word:
            tok = PHONEMES.get(ch)
            if tok is None:
                return DFAResult(False, path=[],
                                 failing=("UNKNOWN", ch), end_state=self.start[0])
            tokens.append(tok)
        return self.accept(tokens)


# ---------------------------------------------------------------------------
# 3. Bark-scale formant space (vowels as ℝ³ coordinates)
# ---------------------------------------------------------------------------

def bark(freq_hz: float) -> float:
    """Convert Hz to Bark (perceptual frequency). Perceptual distance in Bark
    space tracks log-frequency, so a Bark Δ ≈ a ban Δ (both log10-based)."""
    return 13.0 * math.atan(0.00076 * freq_hz) + \
           3.5 * math.atan((freq_hz / 7500.0) ** 2)


# Typical male vowel formants (Hz): F1, F2, F3.
FORMANTS_HZ = {
    "i": (270, 2290, 3010),  # beat
    "e": (530, 1840, 2480),  # bet
    "a": (730, 1090, 2440),  # father
    "o": (450, 870, 2520),   # boat
    "u": (300, 870, 2240),   # boot
}


def formant_vector(symbol: str) -> Optional[Tuple[float, float, float]]:
    """Return the vowel's (F1, F2, F3) in BARK space, or None if not a vowel."""
    hz = FORMANTS_HZ.get(symbol)
    if hz is None:
        return None
    return tuple(bark(f) for f in hz)


def formant_distance(a: str, b: str) -> Optional[float]:
    """Euclidean distance between two vowels in Bark space (≈ perceptual Δ)."""
    va, vb = formant_vector(a), formant_vector(b)
    if va is None or vb is None:
        return None
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(va, vb)))


# ---------------------------------------------------------------------------
# 4. Isochrony — stress-timed rhythm
# ---------------------------------------------------------------------------

def isochrony_score(stress_times: List[float]) -> Optional[float]:
    """How stress-timed a sequence is: ~constant intervals between stressed
    syllables. Returns the coefficient of variation of inter-stress intervals
    (0 = perfectly isochronous, higher = more syllable-timed / irregular)."""
    if len(stress_times) < 3:
        return None
    intervals = [b - a for a, b in zip(stress_times, stress_times[1:])]
    mean = sum(intervals) / len(intervals)
    if mean == 0:
        return 0.0
    var = sum((d - mean) ** 2 for d in intervals) / len(intervals)
    return math.sqrt(var) / mean


# ---------------------------------------------------------------------------
# 5. Banburismus: token stream -> evidence
# ---------------------------------------------------------------------------

def score_with_ledger(dfo, tokens: List[Phoneme],
                      threshold_dban: float = 20.0) -> Tuple[Optional[str], float]:
    """Feed a token stream through the BanLedger. Each legal transition is
    +evidence (positive likelihood ratio); an illegal one is a contradiction
    (eliminated to -inf). Returns (winner, dban) if the gate clears, else None.

    This is the phonotactic crib wired into Turing's deciban ledger: a valid
    utterance accumulates evidence transition-by-transition; /ftr/ is killed at
    the first illegal fall, exactly like a bad rotor setting.
    """
    ledger = BanLedger(threshold_dban=threshold_dban)
    ledger.register("valid_string", prior_prob=0.5)
    res = dfo.accept(tokens)
    if not res.valid:
        ledger.eliminate("valid_string")
        return None, float("-inf")
    # each transition is a small piece of positive evidence
    for _ in res.path:
        ledger.observe("valid_string", 0.75, 0.25)  # +4.77 dBan each
    gate = ledger.evaluate_gate()
    if gate is None:
        return None, ledger.scores.get("valid_string", 0.0)
    return gate
