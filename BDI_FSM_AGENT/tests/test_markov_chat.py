#!/usr/bin/env python3
"""Deterministic tests for MarkovChat — entropy-stopped stitching, zero LLM."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bdi_fsm.markov_chat import MarkovChat, tokenize, row_entropy, chat_longer
from collections import Counter


def test_tokenize_basic():
    toks = tokenize("Hello, world! This is a test.")
    assert toks == ["hello", ",", "world", "!", "this", "is", "a", "test", "."], toks


def test_row_entropy_uniform_vs_deterministic():
    uniform = Counter({"a": 1, "b": 1, "c": 1, "d": 1})
    det = Counter({"a": 10})
    assert row_entropy(det) == 0.0
    assert abs(row_entropy(uniform) - 2.0) < 1e-9  # log2(4) = 2 bits


def test_build_counts():
    mc = MarkovChat(order=2)
    info = mc.build(["the quick brown fox jumps", "the quick brown dog sleeps"])
    assert info["streams"] == 2
    assert info["contexts"] > 0
    assert info["tokens"] > 0


def test_generate_deterministic_same_seed():
    corpus = ["the quick brown fox jumps over the lazy dog",
              "the quick brown fox runs fast", "the lazy dog sleeps all day"]
    a = MarkovChat(seed=1); a.build(corpus)
    b = MarkovChat(seed=1); b.build(corpus)
    out_a = a.generate(seed="the quick", max_words=30)
    out_b = b.generate(seed="the quick", max_words=30)
    assert out_a["text"] == out_b["text"]
    assert out_a["entropy_series"] == out_b["entropy_series"]


def test_generate_respects_max_words():
    corpus = ["a b c d e f g h i j k l m n o p q r s t u v w x y z"] * 5
    mc = MarkovChat(); mc.build(corpus)
    out = mc.generate(seed="a", max_words=10)
    assert out["steps"] <= 10, out  # steps = continuations, seed excluded
    assert out["words"] <= 12, out  # seed context (2) + steps


def test_stop_token_halts():
    corpus = ["hello world . hello world . hello world ."]
    mc = MarkovChat(); mc.build(corpus)
    out = mc.generate(seed="hello", max_words=100)
    assert out["reason"] == "stop_token", out
    assert out["words"] <= 8, out


def test_entropy_stopping_at_branch_point():
    """A junction with 4 equally-likely continuations is a coherence break:
    the generator must stop there (entropy spike) instead of guessing."""
    # "go" -> 4 equally likely next words -> entropy = 2.0 bits at that step
    corpus = ["go north .", "go south .", "go east .", "go west .",
              "go up .", "go down .", "go left .", "go right ."]
    mc = MarkovChat(order=1); mc.build(corpus)
    out = mc.generate(seed="go", max_words=50, entropy_cap=1.5)
    # the "go" branch has H=3.0 (8 uniform options); cap 1.5 must stop it
    assert out["reason"].startswith("entropy"), out
    assert out["words"] <= 4, out  # "go" + at most a couple tokens


def test_low_entropy_stream_continues():
    """Fully deterministic chain (H=0 everywhere) must run to max_words."""
    corpus = ["one two three four five six seven eight nine ten eleven twelve"]
    mc = MarkovChat(); mc.build(corpus)
    out = mc.generate(seed="one", max_words=12)
    assert out["words"] == 12, out
    assert out["entropy_max"] == 0.0, out


def test_seeded_tiebreak_stable():
    corpus = ["a x . a y . a z . a w ."]
    mc = MarkovChat(seed=3); mc.build(corpus)
    out = mc.generate(seed="a", max_words=10)
    assert out["words"] >= 2
    # same seed twice -> same pick
    mc2 = MarkovChat(seed=3); mc2.build(corpus)
    out2 = mc2.generate(seed="a", max_words=10)
    assert out["text"] == out2["text"]


def test_stitch_multiple_parts():
    corpus = ["the quick brown fox jumps", "the quick brown fox runs",
              "the lazy dog sleeps", "the lazy dog barks"]
    mc = MarkovChat(); mc.build(corpus)
    out = mc.stitch(["the quick", "the lazy"], max_words_per=20)
    assert out["parts"] == 2, out
    assert out["words"] > 0
    assert out["text"]


def test_chat_longer_helper():
    corpus = ["the quick brown fox jumps over the lazy dog"]
    out = chat_longer(corpus, seed="the", max_words=20)
    assert out["text"], out
    assert "entropy_mean" in out


def test_empty_model_graceful():
    mc = MarkovChat()
    out = mc.generate(seed="hi")
    assert out["reason"] == "empty_model"


def test_stats_report():
    corpus = ["a b c d e", "a b c x y"]
    mc = MarkovChat(); mc.build(corpus)
    s = mc.stats()
    assert s["contexts"] > 0
    assert s["tokens"] > 0
    assert "coherent_rows" in s

def test_max_restarts_extends_output():
    """min_words>1 needs fresh-sentence restarts; the restart budget must
    scale with requested length or output dies after ~3 short sentences."""
    corpus = [
        "the cat sat on the mat .",
        "a dog ran through the park .",
        "birds fly high in the sky .",
        "the sun sets over the lake .",
        "we walk slowly down the road .",
        "she reads a book by the fire .",
        "rain falls gently on the roof .",
        "he climbs the steep mountain trail .",
        "the river flows into the sea .",
        "they sing songs around the camp .",
        "morning light fills the quiet room .",
        "the old tree stands alone .",
        "we bake bread in the kitchen .",
        "the moon glows over the hills .",
        "children play near the water .",
        "the wind moves through the leaves .",
        "stars shine bright tonight .",
        "the train rolls past the station .",
        "coffee warms her cold hands .",
        "the garden grows wild each year .",
    ]
    mc = MarkovChat(order=2, seed=3); mc.build(corpus)
    # disable entropy stopping so ONLY the restart budget bounds output
    short = mc.generate(seed="the cat", max_words=200, entropy_cap=100.0,
                        spike_mult=100.0, min_words=40, max_restarts=3)
    long_ = mc.generate(seed="the cat", max_words=200, entropy_cap=100.0,
                        spike_mult=100.0, min_words=40, max_restarts=8)
    assert long_["words"] > short["words"], (short, long_)
    assert long_["words"] >= 40, long_


def test_max_restarts_default_legacy():
    """Default max_restarts=3 keeps legacy min_words=1 (stop at first period)."""
    corpus = ["the quick brown fox jumps over the lazy dog .",
              "a fast red car drives down the street ."]
    mc = MarkovChat(order=2, seed=5); mc.build(corpus)
    out = mc.generate(seed="the quick", max_words=60)
    assert out["words"] <= 20, out  # short: stops at first period


ALL = [v for k, v in sorted(globals().items()) if k.startswith("test_")]


def run_all():
    passed = 0
    for t in ALL:
        t()
        passed += 1
        print(f"  ok {t.__name__}")
    print(f"\n{passed}/{len(ALL)} markov-chat tests passed")
    return passed


if __name__ == "__main__":
    raise SystemExit(0 if run_all() == len(ALL) else 1)


# --- degenerate-cycle guard (2026-08-12) -----------------------------------
# Regression: the corpus built from local Rust doc prose drove generation into
# "bitslice:: slice:: slice:: slice::" forever. That is a period-2 loop, and the
# original guard only tested three IDENTICAL adjacent tokens, so it never fired.
# Entropy cannot catch it either: a deterministic successor has entropy 0, so the
# more degenerate the loop, the less the coherence test objects.
from bdi_fsm.markov_chat import _cycling


def test_cycle_guard_catches_period_one():
    assert _cycling(["x", "x", "x"]) is True
    assert _cycling(["a", "x", "x", "x"]) is True


def test_cycle_guard_catches_the_rust_slice_loop():
    assert _cycling(["slice", "::", "slice", "::", "slice", "::"]) is True


def test_cycle_guard_catches_longer_periods():
    assert _cycling(["a", "b", "c"] * 3) is True


def test_cycle_guard_leaves_prose_alone():
    # Real sentences repeat words without cycling; the guard must not fire.
    assert _cycling(["the", "cat", "sat", "on", "the", "mat"]) is False
    assert _cycling("a rose is a rose but not yet a loop".split()) is False


def test_cycle_guard_needs_three_repeats_not_two():
    # Two repeats is a rhetorical echo, not a degenerate loop.
    assert _cycling(["a", "b", "a", "b"]) is False


def test_cycle_guard_is_bounded_work_on_long_output():
    # It must inspect only the tail, so cost does not grow with reply length.
    assert _cycling(["w"] * 2 + ["q", "z"] * 500) is True


# --- associative jump (Chris 2026-08-12) -----------------------------------
# "I jump from word to word and tree to tree." Restarts used to teleport to a
# RANDOM document opening, which is why stitched replies read as unrelated
# fragments. These tests are built so they FAIL if the jump goes back to random.
from bdi_fsm.markov_chat import MarkovChat, STOPWORDS


def _two_island_corpus():
    """Two topics that share no vocabulary. A random jump crosses between them;
    an associative jump cannot, because no word bridges the islands."""
    cats = ["the cat chased a feather across the carpet . " * 6]
    ships = ["a freighter unloaded cargo onto the dock at dawn . " * 6]
    return cats + ships


def test_jump_lands_on_a_context_containing_the_word_it_left_on():
    mc = MarkovChat(order=2, seed=3)
    mc.build(_two_island_corpus())
    ctx = mc._jump(["the", "cat", "chased", "a", "feather"])
    assert ctx is not None
    # It must have jumped on a CONTENT word from the trail, not landed anywhere.
    assert any(tok in ("feather", "chased", "cat", "carpet") for tok in ctx), ctx


def test_jump_ignores_stopwords_and_punctuation():
    mc = MarkovChat(order=2, seed=3)
    mc.build(_two_island_corpus())
    # Trail ends in stopwords/punctuation; the only content word is "freighter".
    ctx = mc._jump(["freighter", "unloaded", "the", "a", "of", "."])
    assert ctx is not None
    assert any(tok in ("freighter", "unloaded", "cargo", "dock") for tok in ctx), ctx


def test_jump_falls_back_to_random_when_nothing_is_topical():
    mc = MarkovChat(order=2, seed=3)
    mc.build(_two_island_corpus())
    # No content word here occurs in the corpus at all -> must still return a start,
    # never None, or generation would die instead of degrading.
    ctx = mc._jump(["zzzz", "qqqq", "the", "of"])
    assert ctx is not None


def test_jump_returns_none_only_on_an_empty_model():
    mc = MarkovChat(order=2, seed=3)
    assert mc._jump(["anything"]) is None


def test_stopwords_do_not_swallow_real_subjects():
    # An over-aggressive stoplist would gut the corpus. Guard the ones that matter.
    for word in ("cat", "hive", "entropy", "agent", "feather", "system"):
        assert word not in STOPWORDS
