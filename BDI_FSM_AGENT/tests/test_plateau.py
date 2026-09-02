"""PlateauDetector tests — unified (is_stalled, reason) signal."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bdi_fsm.plateau import PlateauDetector, PlateauType


def test_classify_soft_plateaus():
    d = PlateauDetector()
    assert d.classify("plateau") == (True, PlateauType.SCORE_STAGNANT)
    assert d.classify("plateaued") == (True, PlateauType.ENTROPY_FLAT)
    assert d.classify("tie") == (True, PlateauType.CANDIDATE_TIE)


def test_classify_hard_blocks_are_not_stalls():
    d = PlateauDetector()
    for r in ("all_rejected", "no_candidates", "verify_fail"):
        stalled, _ = d.classify(r)
        assert stalled is False, r


def test_classify_unknown_is_none():
    d = PlateauDetector()
    assert d.classify("garbage") == (False, PlateauType.NONE)


def test_score_stagnation():
    d = PlateauDetector(patience=3)
    d.observe(True)   # improve
    d.observe(False)  # stagnate
    d.observe(False)
    assert d.is_stalled() == (False, PlateauType.NONE)
    d.observe(False)  # 3rd stagnation -> stalled
    stalled, t = d.is_stalled()
    assert stalled is True and t is PlateauType.SCORE_STAGNANT


def test_observe_improvement_resets():
    d = PlateauDetector(patience=2)
    d.observe(False)
    d.observe(True)   # reset
    d.observe(False)
    assert d.is_stalled() == (False, PlateauType.NONE)
