"""Cellular mesh: intent routing, fog population, quorum, search fallback."""
from bdi_fsm.intent import parse_intent
from bdi_fsm.mesh import CellularMesh


def _fake_search(injected=1):
    def _search(intent, cell):
        return {"searched": intent.key, "hits": 1, "injected": injected}
    return _search


def test_submit_intent_populates_fog():
    m = CellularMesh(radius=2)
    r = m.submit_intent(parse_intent("build a hex grid"), search=_fake_search())
    assert r["intent"] == "build:a hex grid"
    assert r["explored"] >= 1
    assert r["fog"]["explored"] >= 1
    assert r["fog"]["visible"] >= 6


def test_submit_intent_unrecognized_triggers_search():
    m = CellularMesh(radius=2)
    r = m.submit_intent(parse_intent("flarbnax the qux"), search=_fake_search())
    assert r["results"][0]["impasse"] is True
    assert r["searched"] == 1
    assert r["explored"] == 0


def test_spiral_assignment_starts_at_origin():
    m = CellularMesh(radius=3)
    assert m.assign_cell(0) == (0, 0)
    assert m.assign_cell(1) in [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]


def test_quorum_majority():
    m = CellularMesh(radius=1)
    winner, tally = m.quorum({"a": 3.0, "b": 1.0, "c": 2.0})
    assert winner == "a"


def test_quorum_tie_break_deterministic():
    m = CellularMesh(radius=1)
    winner, tally = m.quorum({"a": 2.0, "c": 2.0})
    assert winner == "c"   # lexicographically largest on tie
    # same input -> same output (determinism)
    w2, _ = m.quorum({"a": 2.0, "c": 2.0})
    assert w2 == winner


def test_snapshot_contains_cells_and_fog():
    m = CellularMesh(radius=1)
    snap = m.snapshot()
    assert snap["origin"] == [0, 0]
    assert "0,0" in snap["cells"]
    assert "0,0" in snap["fog"]
