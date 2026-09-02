#!/usr/bin/env python3
"""Deterministic tests for the KQML ACL layer — English <-> performatives."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bdi_fsm.kqml import classify, envelope, parse, render_english, render_reply, talk


def test_classify_ask_one():
    perf, content = classify("what is the pool status?")
    assert perf == "ask-one", perf
    assert content == "the pool status", content


def test_classify_achieve_please():
    perf, content = classify("please build the bridge")
    assert perf == "achieve", perf
    assert content == "build the bridge", content


def test_classify_achieve_imperative():
    perf, content = classify("run the tests now")
    assert perf == "achieve", perf
    assert content == "tests now", content  # leading 'the' stripped as noise


def test_classify_insert_belief():
    perf, content = classify("i think the port is broken")
    assert perf == "insert", perf
    assert content == "port is broken", content  # article stripped


def test_classify_deny():
    perf, content = classify("no, never do that")
    assert perf == "deny", perf
    assert content == "never do that", content


def test_classify_thanks():
    perf, content = classify("thank you")
    assert perf == "tell", perf


def test_classify_ask_if():
    perf, content = classify("is the server up?")
    assert perf == "ask-if", perf


def test_envelope_format():
    msg = envelope("ask-one", "aegis", "bdi-fsm", "pool status")
    assert msg.startswith("(ask-one :sender aegis :receiver bdi-fsm")
    assert ":content" in msg


def test_parse_roundtrip():
    msg = envelope("achieve", "aegis", "bdi-fsm", "build bridge")
    d = parse(msg)
    assert d["performative"] == "achieve", d
    assert d["sender"] == "aegis", d
    assert d["receiver"] == "bdi-fsm", d
    assert "build" in d["content"] and "bridge" in d["content"], d


def test_parse_content_tokens():
    msg = envelope("insert", "aegis", "bdi-fsm", "port is 5000")
    d = parse(msg)
    assert d["content"] == ["port", "is", "5000"], d


def test_render_english_templates():
    assert "attempt to" in render_english("achieve", "build bridge")
    assert "recorded" in render_english("insert", "x is y")
    assert "Declined" in render_english("deny", "never")


def test_render_reply():
    r = render_reply("achieve", "build bridge")
    assert "Done" in r, r


def test_talk_full_loop():
    r = talk("what is the pool status")
    assert r["performative"] == "ask-one"
    assert r["kqml"].startswith("(ask-one")
    assert r["parsed"]["performative"] == "ask-one"
    assert "asked about" in r["english"]


def test_talk_with_lexicon_binding():
    from bdi_fsm.lexicon import Lexicon
    import tempfile, os
    with tempfile.TemporaryDirectory() as td:
        lx = Lexicon(os.path.join(td, "lexicon.json"))
        lx.bind("pool", "check_pool")
        r = talk("what is the pool status", lexicon=lx)
        assert r["tool"] == "check_pool", r
        assert "check_pool" in r["english"], r


def test_talk_deny_english():
    r = talk("no never do that")
    assert r["performative"] == "deny"
    assert "Declined" in r["english"]


ALL = [v for k, v in sorted(globals().items()) if k.startswith("test_")]


def run_all():
    passed = 0
    for t in ALL:
        t()
        passed += 1
        print(f"  ok {t.__name__}")
    print(f"\n{passed}/{len(ALL)} kqml tests passed")
    return passed


if __name__ == "__main__":
    raise SystemExit(0 if run_all() == len(ALL) else 1)
