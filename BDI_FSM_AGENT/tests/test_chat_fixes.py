"""Chat fixes: listing verbs -> list_details, and zero-repeat dedup (Chris 2026-08-14)."""
import tempfile
from collections import deque

from bdi_fsm.agent import BDIFSMAgent


def test_is_listing_detects_verbs():
    a = object.__new__(BDIFSMAgent)
    assert a._is_listing("list all details") is True
    assert a._is_listing("show me everything") is True
    assert a._is_listing("tell me a story") is False
    assert a._is_listing("build a hex grid") is False


def test_pick_nonrecent_skips_repeat():
    a = object.__new__(BDIFSMAgent)
    a._recent_replies = deque(["already said", "said too"], maxlen=16)
    curve = [
        {"text": "already said", "word_entropy": 0.5},
        {"text": "said too", "word_entropy": 0.7},
        {"text": "fresh answer", "word_entropy": 1.2},
    ]
    c = a._pick_nonrecent(curve)
    assert c["text"] == "fresh answer"


def test_remember_reply_records():
    a = object.__new__(BDIFSMAgent)
    a._recent_replies = deque(maxlen=16)
    a._remember_reply("  hello  ")
    assert "hello" in a._recent_replies
    a._remember_reply("   ")
    assert "   " not in a._recent_replies


def test_list_details_returns_keys():
    a = BDIFSMAgent(state_dir=tempfile.mkdtemp())
    d = a.list_details()
    for k in ("facts", "plans", "skills", "corpus", "journal", "world", "self"):
        assert k in d, f"missing {k}"


def test_chat_plateau_remembers_reply():
    a = BDIFSMAgent(state_dir=tempfile.mkdtemp())
    a._recent_replies.clear()
    out = a.chat_plateau("hello world", max_candidates=8)
    best = (out.get("best") or {}).get("text", "")
    if best:
        assert best.strip() in a._recent_replies
