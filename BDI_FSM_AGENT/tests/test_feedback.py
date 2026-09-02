"""FeedbackStore tests — like/dislike reinforcement, association learning."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bdi_fsm.feedback import FeedbackStore


def test_rate_records_preference_and_associations():
    d = tempfile.mkdtemp(prefix="bdi_fb_")
    fs = FeedbackStore(path=os.path.join(d, "fb.json"))
    r = fs.rate("hello world", "hello there", True)
    assert r["ok"] is True
    assert r["pref_score"] == 1
    assert r["associations"] > 0


def test_preference_score_tracks_net():
    d = tempfile.mkdtemp(prefix="bdi_fb_")
    fs = FeedbackStore(path=os.path.join(d, "fb.json"))
    fs.rate("hi", "hello", True)
    fs.rate("hi", "hello", True)
    fs.rate("hi", "hello", False)
    assert fs.preference("hi") == 1  # +1 +1 -1


def test_should_prefer_positive_after_like():
    d = tempfile.mkdtemp(prefix="bdi_fb_")
    fs = FeedbackStore(path=os.path.join(d, "fb.json"))
    fs.rate("the cat sat", "on the mat", True)
    score = fs.should_prefer("on the mat", "the cat sat")
    assert score > 0


def test_top_associations_sorted():
    d = tempfile.mkdtemp(prefix="bdi_fb_")
    fs = FeedbackStore(path=os.path.join(d, "fb.json"))
    fs.rate("apple", "fruit", True)
    fs.rate("apple", "fruit", True)
    fs.rate("car", "vehicle", True)
    top = fs.top_associations(limit=5)
    assert top[0]["score"] >= top[-1]["score"]
    assert any("apple" in t["pair"] for t in top)


def test_stats_counts_likes_dislikes():
    d = tempfile.mkdtemp(prefix="bdi_fb_")
    fs = FeedbackStore(path=os.path.join(d, "fb.json"))
    fs.rate("a", "b", True)
    fs.rate("a", "b", True)
    fs.rate("a", "b", False)
    s = fs.stats()
    assert s["likes"] == 2
    assert s["dislikes"] == 1
    assert s["rated_exchanges"] == 3


def test_rate_rejects_empty():
    d = tempfile.mkdtemp(prefix="bdi_fb_")
    fs = FeedbackStore(path=os.path.join(d, "fb.json"))
    assert fs.rate("", "", True)["ok"] is False


def test_feedback_persists():
    d = tempfile.mkdtemp(prefix="bdi_fb_")
    p = os.path.join(d, "fb.json")
    fs = FeedbackStore(path=p)
    fs.rate("ping", "pong", True)
    fs2 = FeedbackStore(path=p)
    assert fs2.preference("ping") == 1
