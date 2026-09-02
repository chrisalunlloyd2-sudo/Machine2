"""Tests for the phonotactic DFA (token-stream guardrail) + formant space."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bdi_fsm.phonotactics import (
    EnglishSyllableDFA, SequenceDFA, Phoneme, PHONEMES,
    bark, formant_vector, formant_distance, isochrony_score, score_with_ledger,
    SONORITY,
)


def test_sonority_hierarchy():
    assert SONORITY["vowel"] > SONORITY["glide"] > SONORITY["liquid"]
    assert SONORITY["liquid"] > SONORITY["nasal"] > SONORITY["fricative"] > SONORITY["stop"]


def test_str_valid():
    r = EnglishSyllableDFA().accept_word("strin")
    assert r.valid, r.failing


def test_ftr_invalid_crib():
    r = EnglishSyllableDFA().accept_word("ftrin")
    assert not r.valid
    assert r.failing == ("ONSET", "t")  # illegal sonority fall f->t


def test_s_cluster_allowed():
    # /s/ + stop is the extra-syllabic exception; /str/ onset is fine
    r = EnglishSyllableDFA().accept_word("sprint")
    assert r.valid, r.failing


def test_plan_bran_valid():
    for w in ("plan", "bran", "spar", "blad"):
        assert EnglishSyllableDFA().accept_word(w).valid, w


def test_lpin_invalid_crib():
    # liquid -> stop is a sonority fall in the onset (no s-exception)
    r = EnglishSyllableDFA().accept_word("lpin")
    assert not r.valid
    assert r.failing == ("ONSET", "p")


def test_onset_without_nucleus_rejected():
    # a bare onset ('str') is not a complete syllable
    r = EnglishSyllableDFA().accept_word("str")
    assert not r.valid


def test_vowel_alone_valid():
    assert EnglishSyllableDFA().accept_word("i").valid
    assert EnglishSyllableDFA().accept_word("ba").valid


def test_sequence_dfa_generic():
    dfa = SequenceDFA({("S", "a"): "A", ("A", "b"): "END"},
                      start="S", accepting={"END"})
    ok = dfa.accept([Phoneme("x", "a"), Phoneme("y", "b")])
    assert ok.valid
    bad = dfa.accept([Phoneme("x", "b")])
    assert not bad.valid
    assert bad.failing == ("S", "x")  # state visibility


def test_bark_monotonic():
    assert bark(500) < bark(2000) < bark(8000)
    assert bark(100) > 0


def test_formant_vector_3d():
    v = formant_vector("i")
    assert v is not None and len(v) == 3
    assert all(x > 0 for x in v)


def test_formant_distance_front_vs_back():
    # front vowels /i/,/e/ are closer than /i/ vs low-back /a/
    assert formant_distance("i", "a") > formant_distance("i", "e")


def test_isochrony_perfect_zero():
    assert isochrony_score([0.0, 0.5, 1.0, 1.5, 2.0]) == 0.0


def test_isochrony_irregular_higher():
    perfect = isochrony_score([0.0, 0.5, 1.0, 1.5, 2.0])
    irregular = isochrony_score([0.0, 0.3, 1.0, 2.1, 2.4])
    assert irregular > perfect


def test_banburismus_gate_fires_on_valid():
    dfa = EnglishSyllableDFA()
    toks = [PHONEMES[c] for c in "strin"]
    winner, dban = score_with_ledger(dfa, toks)
    assert winner == "valid_string"
    assert dban >= 20  # 5 transitions x +4.77 dBan clears threshold


def test_banburismus_eliminates_invalid():
    dfa = EnglishSyllableDFA()
    toks = [PHONEMES[c] for c in "ftrin"]
    winner, dban = score_with_ledger(dfa, toks)
    assert winner is None
    assert dban == float("-inf")  # contradiction -> eliminated


if __name__ == "__main__":
    n = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); n += 1; print(f"  {name} PASS")
    print(f"ALL phonotactics tests passed ({n})")
