"""PLATEAU DETECTOR — one 'stalled' signal from many sources.

Chris directive: consolidate rotor_codec patience, MarkovPlateau entropy, and
FSM block states into a central signal generator returning
(is_stalled: bool, reason: PlateauType).

A STALL (soft plateau) is recoverable by MUTATION — expand the search horizon,
decompose into a subgoal, or commit at minimum regret. A HARD BLOCK (no
candidates, all rejected, verify failed) is NOT a stall: there is no
information left to mutate, so the only exits are give-up or a fresh slot.

Pure stdlib. Deterministic. Zero LLM.
"""
from enum import Enum
from typing import Tuple
import threading


class PlateauType(Enum):
    NONE = "none"
    SCORE_STAGNANT = "score_stagnant"    # rotor brute_find patience exhausted
    ENTROPY_FLAT = "entropy_flat"        # MarkovPlateau word-entropy leveled out
    CANDIDATE_TIE = "candidate_tie"      # equal maxima, no discriminator (SOAR)
    ALL_REJECTED = "all_rejected"        # hard: every candidate rejected
    NO_CANDIDATES = "no_candidates"      # hard: nothing produced
    VERIFY_FAIL = "verify_fail"          # hard: all candidates failed the crib


# Soft plateaus are recoverable by mutation; hard blocks are terminal.
_SOFT = {PlateauType.SCORE_STAGNANT, PlateauType.ENTROPY_FLAT,
         PlateauType.CANDIDATE_TIE}


class PlateauDetector:
    """Central stall classifier. Raw signals -> (is_stalled, PlateauType).

    Score stagnation (rotor patience) is tracked incrementally via observe();
    source reason strings (rotor "plateau", markov "plateaued", FSM block
    reasons) are classified via classify() into one unified signal.
    """

    def __init__(self, patience: int = 60):
        self.patience = patience
        self.stagnant = 0
        self._lock = threading.RLock()

    def observe(self, improved: bool) -> "PlateauDetector":
        """Feed a score-improvement flag (rotor / plateau loop)."""
        with self._lock:
            self.stagnant = 0 if improved else self.stagnant + 1
        return self

    def score_stalled(self) -> bool:
        with self._lock:
            return self.stagnant >= self.patience

    @staticmethod
    def classify(reason: str) -> Tuple[bool, PlateauType]:
        """Map a source's reason string to a unified (is_stalled, reason).

        Soft plateaus -> is_stalled=True (recoverable by mutation).
        Hard blocks / unknown -> is_stalled=False.
        """
        t = {
            "plateau": PlateauType.SCORE_STAGNANT,
            "score_stagnant": PlateauType.SCORE_STAGNANT,
            "plateaued": PlateauType.ENTROPY_FLAT,
            "entropy_flat": PlateauType.ENTROPY_FLAT,
            "tie": PlateauType.CANDIDATE_TIE,
            "candidate_tie": PlateauType.CANDIDATE_TIE,
            "all_rejected": PlateauType.ALL_REJECTED,
            "no_candidates": PlateauType.NO_CANDIDATES,
            "verify_fail": PlateauType.VERIFY_FAIL,
        }.get(reason, PlateauType.NONE)
        return (t in _SOFT), t

    def is_stalled(self) -> Tuple[bool, PlateauType]:
        """The unified signal for the current accumulated state."""
        with self._lock:
            if self.stagnant >= self.patience:
                return True, PlateauType.SCORE_STAGNANT
            return False, PlateauType.NONE

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
