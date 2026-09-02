"""100% certainty gate tests — the doctrine: every step must PASS 100% or step back."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bdi_fsm.certainty import CertaintyGate


def test_pass_when_all_checks_hold():
    g = CertaintyGate()
    r = g.assess({"name": "s", "checks": [("not_empty", None)]}, {"output": "x"})
    assert r["verdict"] == "PASS"
    assert r["confidence"] == 1.0


def test_step_back_on_any_failure():
    g = CertaintyGate()
    r = g.assess({"name": "s", "checks": [("file_exists", "/definitely/missing")]},
                 {"output": "x"})
    assert r["verdict"] == "STEP_BACK"
    assert r["confidence"] == 0.0
    assert r["failing"]


def test_compile_verifier():
    g = CertaintyGate()
    r = g.assess({"name": "s", "checks": [("compile", "bdi_fsm/certainty.py")]},
                 {"output": ""})
    assert r["verdict"] == "PASS"


def test_constraint_uses_step_output_not_arg():
    g = CertaintyGate()
    r = g.assess({"name": "s",
                  "checks": [("constraint", (lambda o: o.get("n") == 42))]},
                 {"output": {"n": 42}})
    assert r["verdict"] == "PASS"
    r2 = g.assess({"name": "s",
                   "checks": [("constraint", (lambda o: o.get("n") == 42))]},
                  {"output": {"n": 7}})
    assert r2["verdict"] == "STEP_BACK"


def test_dependency_verifier():
    g = CertaintyGate()
    r = g.assess({"name": "s", "checks": [("dependency", ["a", "b"])]},
                 {"bb": {"a": 1, "b": 2}})
    assert r["verdict"] == "PASS"
    r2 = g.assess({"name": "s", "checks": [("dependency", ["a", "c"])]},
                  {"bb": {"a": 1}})
    assert r2["verdict"] == "STEP_BACK"


def test_fact_verifier():
    g = CertaintyGate()
    r = g.assess({"name": "s", "checks": [("fact", "ready")]}, {"bb": {"ready": True}})
    assert r["verdict"] == "PASS"


def test_step_back_records_nmtd_and_assessment():
    class FakeNMTD:
        def __init__(self):
            self.records = []

        def record(self, *a):
            self.records.append(a)
            return True

    nmtd = FakeNMTD()
    g = CertaintyGate(nmtd=nmtd)
    a = g.assess({"name": "boom", "checks": [("file_exists", "/missing")]}, {"output": ""})
    sb = g.step_back({"name": "boom"}, a)
    assert sb["nmtd_recorded"] is True
    assert "boom" in nmtd.records[0]
    assert "redo" in sb["assessment"]["redo_instruction"].lower()
