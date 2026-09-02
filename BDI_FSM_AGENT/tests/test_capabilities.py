"""Capability router tests — all LLM tasks except English creation."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bdi_fsm.capabilities import CapabilityRouter, classify, safe_math, safe_math_strip


def test_classify_english_deferred():
    assert classify("write an email to Chris about the build") == "english"
    assert classify("compose a poem about hexes") == "english"
    assert classify("draft a letter to the landlord") == "english"


def test_classify_capabilities():
    assert classify("transpile the spec to python") == "transpile"
    assert classify("calculate 2 + 3 * 4") == "math"
    assert classify("decide which task to run") == "decide"
    assert classify("verify quality_gate.py compiles") == "verify"
    assert classify("heal the servers") == "heal"
    assert classify("find where telemetry is used") == "search"


def test_safe_math():
    assert safe_math("2 + 3 * 4") == 14
    assert safe_math("(10 - 2) / 2") == 4.0
    assert safe_math_strip(" 6 * 7 ") == 42


def test_safe_math_blocks_code():
    import pytest
    for bad in ("__import__('os')", "open('/etc/passwd')", "[x for x in range(3)]"):
        with pytest.raises(Exception):
            safe_math(bad)


def test_router_handle_english_defers_to_llm():
    r = CapabilityRouter().handle("write an email to Chris")
    assert r["handled"] is False
    assert r["reason"] == "english"
    assert r["defer"] == "llm"


def test_router_handle_math():
    r = CapabilityRouter().handle("calculate 6 * 7")
    assert r["handled"] is True
    assert r["capability"] == "math"
    assert r["result"]["value"] == 42
