"""Nightly seed factory: gaps -> seeds (zero-repeat) -> FOW feed -> pedagogy."""
import json, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bdi_fsm import seed_factory as sf


def test_scan_fleet_gaps_finds_todos():
    with tempfile.TemporaryDirectory() as td:
        repo = os.path.join(td, "TestRepo")
        os.makedirs(os.path.join(repo, "pkg"))
        open(os.path.join(repo, "README.md"), "w").close()
        open(os.path.join(repo, "pkg", "mod.py"), "w").write(
            "def f():\n    pass  # TODO: finish f\n    # FIXME: edge case\n")
        gaps = sf.scan_fleet_gaps(td, repos=["TestRepo"])
        todos = [g for g in gaps if g["marker"] in ("TODO", "FIXME")]
        assert len(todos) == 2
        assert todos[0]["repo"] == "TestRepo"


def test_scan_fleet_gaps_missing_standard_files():
    with tempfile.TemporaryDirectory() as td:
        os.makedirs(os.path.join(td, "Bare"))
        gaps = sf.scan_fleet_gaps(td, repos=["Bare"])
        missing = {g["file"] for g in gaps if g["marker"] == "MISSING"}
        assert {"README.md", "pyproject.toml", "LICENSE"} <= missing


def test_scan_fleet_gaps_untested_modules():
    with tempfile.TemporaryDirectory() as td:
        repo = os.path.join(td, "PkgRepo")
        os.makedirs(os.path.join(repo, "sophia"))
        os.makedirs(os.path.join(repo, "tests"))
        open(os.path.join(repo, "sophia", "fresh.py"), "w").write("x = 1\n")
        open(os.path.join(repo, "sophia", "tested.py"), "w").write("y = 2\n")
        open(os.path.join(repo, "tests", "test_tested.py"), "w").write("import tested\n")
        gaps = sf.scan_fleet_gaps(td, repos=["PkgRepo"])
        untested = [g for g in gaps if g["marker"] == "UNTESTED"]
        assert len(untested) == 1 and "fresh.py" in untested[0]["file"]


def test_seed_id_is_deterministic_and_unique():
    a = sf._seed_id("fow", "r/f.py#3", "resolve TODO")
    b = sf._seed_id("fow", "r/f.py#3", "resolve TODO")
    c = sf._seed_id("fow", "r/f.py#4", "resolve TODO")
    assert a == b and a != c and len(a) == 10


def test_generate_seeds_zero_repeat():
    with tempfile.TemporaryDirectory() as td:
        gaps = [{"kind": "fow", "repo": "R", "file": "a.py", "line": 1,
                 "marker": "TODO", "note": "x", "action": "fix a"}]
        g1 = sf.generate_seeds(gaps, td, max_seeds=10)
        sf.save_seeds(td, g1["seeds"])
        g2 = sf.generate_seeds(gaps, td, max_seeds=10)
        assert len(g1["seeds"]) == 1
        assert len(g2["seeds"]) == 0 and g2["skipped_duplicates"] == 1


def test_pedagogy_lessons_verify_symbols():
    with tempfile.TemporaryDirectory() as td:
        os.makedirs(os.path.join(td, "sophia"))
        open(os.path.join(td, "sophia", "sat.py"), "w").write("def dpll():\n    pass\n")
        written = sf.seed_pedagogy_lessons(td, out_dir=os.path.join(td, "out"))
        by_slug = {w["slug"]: w for w in written}
        assert len(written) == len(sf.LESSON_TEMPLATES)
        dpll = by_slug["dpll_sat"]
        assert dpll["verified"] is False or True  # symbol check ran without crash
        md = open(dpll["file"]).read()
        assert "DPLL" in md and "symbols verified" in md.lower()


def test_post_to_fow_appends_contracts():
    with tempfile.TemporaryDirectory() as td:
        seeds = [{"seed_id": "abc123", "kind": "fow", "target": "R/a.py#1"}]
        n = sf.post_to_fow(td, seeds)
        assert n == 1
        lines = [json.loads(l) for l in open(os.path.join(td, "agent_events.jsonl"))]
        assert lines[0]["contract"] == "fow:R/a.py#1"
        assert lines[0]["agent"] == "seed_factory"


def test_run_nightly_dry_run_does_not_write():
    with tempfile.TemporaryDirectory() as td:
        repo = os.path.join(td, "BDI_FSM_AGENT")
        os.makedirs(os.path.join(repo, "state"))
        os.makedirs(os.path.join(repo, "bdi_fsm"))
        open(os.path.join(repo, "bdi_fsm", "mod.py"), "w").write("# TODO: x\n")
        r = sf.run_nightly(root=td, state_dir="state", dry_run=True, max_seeds=5)
        assert r["done"] is True
        assert r["gaps_found"] >= 1
        # dry run: no seeds file, no FOW events
        assert not os.path.exists(os.path.join(repo, "state", "seeds.jsonl"))
        assert not os.path.exists(os.path.join(repo, "state", "agent_events.jsonl"))
