"""Deterministic want -> intent parsing tests."""
from bdi_fsm.intent import Intent, decompose, parse_intent


def test_parse_recognized_verb():
    i = parse_intent("build a hex grid")
    assert i.verb == "build"
    assert "hex" in i.object
    assert i.confidence > 0.0


def test_parse_unknown_verb_confidence_zero():
    i = parse_intent("flarbnax the qux")
    assert i.confidence == 0.0
    assert i.verb == "flarbnax"   # falls back to first token as a topic


def test_parse_empty_want():
    i = parse_intent("")
    assert i.verb == ""
    assert i.confidence == 0.0


def test_intent_key_is_stable():
    i = parse_intent("build a hex grid")
    assert i.key == "build:a hex grid"


def test_parse_listing_verb():
    """Chris 2026-08-14: 'list all details' must register the verb."""
    i = parse_intent("list all details")
    assert i.verb == "list"
    assert i.confidence > 0.0
    for v in ("show", "display", "enumerate", "get", "report", "status", "read"):
        assert parse_intent(v + " everything").verb == v


def test_decompose_primary_goal():
    i = parse_intent("build a hex grid")
    goals = decompose(i)
    assert len(goals) >= 1
    assert goals[0]["verb"] == "build"
    assert goals[0]["object"] == i.object
