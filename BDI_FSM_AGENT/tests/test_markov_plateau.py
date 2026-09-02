"""MarkovPlateau tests — entropy-plateau candidate generation."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bdi_fsm.markov_plateau import MarkovPlateau, word_entropy, plateau_reply
from bdi_fsm.markov_chat import tokenize


CORPUS = [
    "the cat sat on the mat",
    "the dog ran in the park",
    "the cat chased the mouse",
    "a bird flew over the house",
    "the sun rose over the mountain",
]


def test_word_entropy_uniform_is_low():
    # a single repeated token -> zero entropy
    assert word_entropy(["cat", "cat", "cat"]) == 0.0


def test_word_entropy_diverse_is_higher():
    h1 = word_entropy(["cat", "cat", "cat"])
    h2 = word_entropy(["cat", "dog", "bird", "fish"])
    assert h2 > h1


def test_plateau_generates_best_and_curve():
    mp = MarkovPlateau(order=2, base_seed=7, eps=0.1, patience=3, max_candidates=20)
    out = mp.generate(CORPUS, "the cat", max_words=40, entropy_cap=3.0)
    assert "best" in out
    assert "curve" in out
    assert out["candidates"] == len(out["curve"])
    assert out["candidates"] >= 1
    assert out["best"]["text"]


def test_plateau_is_deterministic():
    mp1 = MarkovPlateau(order=2, base_seed=7, patience=3, max_candidates=20)
    mp2 = MarkovPlateau(order=2, base_seed=7, patience=3, max_candidates=20)
    o1 = mp1.generate(CORPUS, "the cat", max_words=40)
    o2 = mp2.generate(CORPUS, "the cat", max_words=40)
    assert o1["best"]["text"] == o2["best"]["text"]
    assert o1["candidates"] == o2["candidates"]


def test_plateau_stops_before_max_candidates():
    mp = MarkovPlateau(order=2, base_seed=7, eps=0.5, patience=2, max_candidates=50)
    out = mp.generate(CORPUS, "the", max_words=30)
    assert out["candidates"] <= 50
    # with a loose eps it should plateau quickly on a small corpus
    assert out["candidates"] < 50


def test_plateau_reply_convenience():
    out = plateau_reply(CORPUS, "the dog", max_words=30, order=2, base_seed=7)
    assert "best" in out and out["best"]["text"]


def test_expand_alias_matches_generate():
    mp = MarkovPlateau(order=2, base_seed=7, patience=3, max_candidates=20)
    g = mp.generate(CORPUS, "the cat", max_words=30)
    e = mp.expand(CORPUS, "the cat", max_words=30)
    assert g["best"]["text"] == e["best"]["text"]
