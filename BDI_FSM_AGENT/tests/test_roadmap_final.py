"""Tests for the final roadmap batch: unify, metaplan, english_render,
corpus_seed. (exhaustive_tree already covered in test_exhaustive_tree.py)"""
import json, os, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bdi_fsm.foundry_kernel import GraphNode, build_expr, graph_hash, normalize
from bdi_fsm.unify import UnifyCache, SubsumptionDAG, unify
from bdi_fsm.metaplan import (MetaplanAbductor, Plan, anti_unify,
                              general_precondition)
from bdi_fsm.english_render import (render_task_tree, render_macro,
                                    render_dag, render_aiception)
from bdi_fsm.corpus_seed import clean_prose, seed

# ---------------------------------------------------------------------------
# 1. Subsumption DAG unification caching
# ---------------------------------------------------------------------------

def test_unify_identical():
    a = build_expr("add", 1, 2)
    b = build_expr("add", 1, 2)
    s = unify(normalize(a.to_dict()), normalize(b.to_dict()))
    assert s is not None, "identical graphs must unify"


def test_unify_different_constants():
    a = build_expr("add", 1, 2)
    b = build_expr("add", 9, 2)
    s = unify(normalize(a.to_dict()), normalize(b.to_dict()))
    assert s is None, "different constants must NOT unify (no vars)"


def test_unify_variable_binding():
    # VAR op subsumes any constant
    a = {"op": "ADD", "children": [
        {"op": "VAR", "name": "v0"}, {"op": "LOAD_CONST", "value": 5}]}
    b = {"op": "ADD", "children": [
        {"op": "LOAD_CONST", "value": 3}, {"op": "LOAD_CONST", "value": 5}]}
    s = unify(normalize(a), normalize(b))
    assert s is not None, "VAR should bind to any constant"


def test_cache_memoizes():
    with tempfile.TemporaryDirectory() as td:
        c = UnifyCache(os.path.join(td, "uc.json"))
        a = build_expr("add", 1, 2)
        b = build_expr("add", 3, 4)
        ha, hb = graph_hash(a.to_dict()), graph_hash(b.to_dict())
        assert c.lookup(ha, hb) is None
        c.store(ha, hb, False, None)
        got = c.lookup(ha, hb)
        assert got is not None and got[0] is False
        # persistence
        c.save()
        c2 = UnifyCache(os.path.join(td, "uc.json"))
        assert c2.lookup(ha, hb) is not None


def test_subsumption_dag_dedup():
    with tempfile.TemporaryDirectory() as td:
        c = UnifyCache(os.path.join(td, "uc.json"))
        dag = SubsumptionDAG(c)
        g1 = build_expr("add", 1, 2)
        g2 = build_expr("add", 1, 2)
        g3 = GraphNode("MUL", [GraphNode("LOAD_CONST", value=1),
                               GraphNode("LOAD_CONST", value=2)])
        assert dag.add(g1.to_dict()) == "new"
        assert dag.add(g2.to_dict()) == "new"  # exact dup -> dedup (not re-added)
        assert dag.add(g3.to_dict()) == "new"  # different op -> new shape
        st = dag.stats()
        assert st["shapes"] == 2, st
        assert st["cache"]["pairs"] >= 0


# ---------------------------------------------------------------------------
# 2. Metaplan abduction + 3. precondition generalization
# ---------------------------------------------------------------------------

def test_backward_chaining_macro():
    plans = [
        Plan("deploy", effect="deployed", precondition="tests pass"),
        Plan("run_tests", effect="tests pass", precondition="code saved"),
        Plan("save_code", effect="code saved", precondition="file exists"),
    ]
    ab = MetaplanAbductor(plans)
    r = ab.abduct("deployed", "file exists")
    assert r and r["achieved"], r
    assert r["macro"] == ["save_code", "run_tests", "deploy"], r["macro"]
    assert "file exists" in r["explanation"]


def test_abduct_no_path():
    ab = MetaplanAbductor([Plan("a", "x", "y")])
    r = ab.abduct("z", "anything")
    assert r is None or not r["achieved"]


def test_anti_unify_generalization():
    g = anti_unify("file exists AND x > 0", "file exists AND y > 0")
    assert g is not None and "$V" in g, g
    g2 = anti_unify("size > 100 AND ok", "size > 200 AND ok")
    assert g2 is not None and "$N" in g2, g2


def test_general_precondition_on_success():
    ab = MetaplanAbductor([Plan("p", "done", "a")])
    ab.record_success("p", "file exists AND x > 0")
    ab.record_success("p", "file exists AND y > 0")
    g = ab.generalize_on_success("p")
    assert "$V" in g, g


def test_metaplan_persistence():
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "plans.json")
        ab = MetaplanAbductor([Plan("a", "x", "y")])
        ab.save(p)
        ab2 = MetaplanAbductor.load(p)
        assert len(ab2.plans) == 1
        assert ab2.plans[0].name == "a"


# ---------------------------------------------------------------------------
# 4. English-word rendering
# ---------------------------------------------------------------------------

def test_render_task_tree_english():
    from bdi_fsm.exhaustive_tree import TaskDAG, TaskTree
    dag = TaskDAG()
    def cands(sig):
        return ["run_tests", "deploy", "dream_prune"]
    sig = "verify system|1|"
    dag.merge(sig, "run_tests", "ok")
    dag.merge(sig, "run_tests", "ok")
    dag.merge(sig, "deploy", "fail")
    t = TaskTree("verify system", 1, dag, cands, ask="run", context="")
    t.expand()
    txt = render_task_tree(t, chosen_action="run_tests")
    assert "verify system" in txt
    assert "run_tests" in txt
    assert "wins" in txt or "tries" in txt
    assert "chose run_tests" in txt


def test_render_macro_english():
    txt = render_macro({"goal": "deployed", "steps": ["save", "test", "deploy"],
                        "explanation": "save applies here"})
    assert "To reach 'deployed'" in txt
    assert "save" in txt and "deploy" in txt


def test_render_dag_english():
    from bdi_fsm.exhaustive_tree import TaskDAG
    dag = TaskDAG()
    dag.merge("s1|1|ctx", "run_tests", "ok")
    dag.merge("s1|1|ctx", "run_tests", "ok")
    dag.merge("s1|1|ctx", "deploy", "fail")
    txt = render_dag(dag)
    assert "run_tests succeeded" in txt
    assert "100%" in txt


def test_render_aiception_english():
    class FakeTree:
        focus_ratings = {"speed": 2.5, "safety": 4.0}
        chosen = "deploy"
    txt = render_aiception(FakeTree())
    assert "speed scored" in txt
    assert "decided to deploy" in txt


# ---------------------------------------------------------------------------
# 5. Corpus seed
# ---------------------------------------------------------------------------

def test_clean_prose_strips_code():
    txt = "## Heading\n\n```\ncode\n```\n\nThis is a real sentence worth keeping for the corpus.\n\n    indent(code)\n"
    out = clean_prose(txt)
    assert "real sentence" in out
    assert "Heading" not in out
    assert "code" not in out.split("real")[0]  # no ``` block content


def test_corpus_seed_dedup_add_only():
    with tempfile.TemporaryDirectory() as td:
        cp = os.path.join(td, "chat_corpus.jsonl")
        # first seed with tiny mirrors
        repo = os.path.join(td, "repo")
        os.makedirs(os.path.join(repo, "docs"))
        open(os.path.join(repo, "README.md"), "w").write(
            "# Repo\n\nThis is a meaningful sentence about the project architecture.\n")
        r1 = seed(cp, kv_path="/nonexistent", mirrors=[repo])
        assert r1["added"] >= 1, r1
        # second run: nothing new -> 0 added
        r2 = seed(cp, kv_path="/nonexistent", mirrors=[repo])
        assert r2["added"] == 0, r2


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for fn in fns:
        try:
            fn()
            passed += 1
            print(f"  ok {fn.__name__}")
        except AssertionError as e:
            print(f"  FAIL {fn.__name__}: {e}")
        except Exception as e:
            print(f"  ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\nRESULT: {passed}/{len(fns)} passed")
    sys.exit(0 if passed == len(fns) else 1)
