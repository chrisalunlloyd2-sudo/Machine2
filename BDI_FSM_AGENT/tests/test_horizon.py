"""Horizon long-horizon execution tests — block stringing, 100% gate, course change."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bdi_fsm.horizon import Horizon, HorizonBlock


def mk(name, val, checks=None):
    return HorizonBlock(name, lambda bb, v=val: v,
                        checks=checks or [("not_empty", None)])


def test_clean_chain_all_pass():
    blocks = [
        mk("a", 1),
        mk("b", {"n": 42}, [("constraint", (lambda o: o.get("n") == 42))]),
        mk("c", "done"),
    ]
    r = Horizon().run("demo", blocks)
    assert r["verdict"] == "DONE"
    assert r["blocks_run"] == 3
    assert r["redoes"] == 0
    assert not r["course_changes"]


def test_flaky_block_steps_back_and_redoes():
    count = {"n": 0}

    def flaky(bb, **kw):
        count["n"] += 1
        return {} if count["n"] < 2 else {"ok": True}

    blocks = [mk("a", 1),
              HorizonBlock("b", flaky, checks=[("not_empty", None)]),
              mk("c", "done")]
    r = Horizon().run("demo2", blocks)
    assert r["verdict"] == "DONE"
    assert r["redoes"] == 1
    assert [x["verdict"] for x in r["results"]] == ["PASS", "PASS", "PASS"]


def test_exhausted_redo_causes_course_change():
    def always_bad(bb, **kw):
        return {}

    blocks = [mk("a", 1),
              HorizonBlock("b", always_bad, checks=[("not_empty", None)]),
              mk("c", "done")]
    r = Horizon(max_redo=2).run("demo3", blocks)
    assert r["verdict"] == "COURSE_CHANGED"
    assert any(x["verdict"] == "STEP_BACK" for x in r["results"])
    assert r["course_changes"]


def test_integrated_output_course_change():
    blocks = [
        mk("a", {"mode": "fast"}),
        mk("b", {"mode": "slow"}),
        HorizonBlock("c", lambda bb: "never", precondition="mode=fast"),
    ]
    r = Horizon().run("demo4", blocks)
    assert any("c" in cc["block"] for cc in r["course_changes"])


def test_precondition_gate_skips_inapplicable():
    blocks = [HorizonBlock("c", lambda bb: "never", precondition="mode=fast")]
    r = Horizon().run("demo5", blocks)
    assert r["course_changes"]
    assert r["blocks_run"] == 0


def test_integrate_callback_receives_output():
    seen = {}

    def integrate(bb, block, out):
        seen[block.name] = out
        return {**bb, block.name: out}

    blocks = [mk("a", "A"), mk("b", "B")]
    Horizon().run("demo6", blocks, integrate=integrate)
    assert seen == {"a": "A", "b": "B"}
