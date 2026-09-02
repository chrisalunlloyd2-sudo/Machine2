"""Tests for the Exhaustive Task Tree Engine (bdi_fsm/exhaustive_tree.py)."""
import json, os, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bdi_fsm.exhaustive_tree import (
    TaskDAG, TaskTree, TaskTreeRunner, state_fp, sig_of)

# ---------------------------------------------------------------------------
# DAG: merge + statistical selection
# ---------------------------------------------------------------------------

def test_dag_merge_and_best():
    dag = TaskDAG()
    dag.merge("taskA|1|ctx", "save_code", "ok")
    dag.merge("taskA|1|ctx", "save_code", "ok")
    dag.merge("taskA|1|ctx", "save_code", "ok")
    dag.merge("taskA|1|ctx", "save_code", "ok")
    dag.merge("taskA|1|ctx", "save_code", "ok")
    dag.merge("taskA|1|ctx", "run_tests", "ok")
    dag.merge("taskA|1|ctx", "run_tests", "ok")
    dag.merge("taskA|1|ctx", "run_tests", "fail")
    # save_code: 5w/0f -> (5+1)/(5+2)=0.857  beats  run_tests: 2w/1f -> 3/5=0.6
    a, st = dag.best("taskA|1|ctx")
    assert a == "save_code", a
    assert st["w"] == 5 and st["f"] == 0
    s = dag.stats()
    assert s["states"] == 1 and s["actions"] == 2 and s["trials"] == 8, s


def test_dag_ask_filter():
    dag = TaskDAG()
    for act in ["save_code", "run_tests", "deploy"]:
        dag.merge("t|1|x", act, "ok")
    # ask=deploy filters to deploy only
    a, _ = dag.best("t|1|x", ask="deploy")
    assert a == "deploy", a
    # ask=run filters run_tests
    a, _ = dag.best("t|1|x", ask="run")
    assert a == "run_tests", a


def test_dag_blocked_never_reexpands():
    dag = TaskDAG()
    dag.merge("t|1|x", "deploy", "fail")
    dag.merge("t|1|x", "deploy", "fail")
    dag.merge("t|1|x", "save", "ok")
    a, _ = dag.best("t|1|x", blocked=["deploy"])
    assert a == "save", a


def test_dag_persistence():
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "dag.json")
        dag = TaskDAG(p)
        dag.merge("t|1|x", "act", "ok")
        dag.save()
        dag2 = TaskDAG(p)
        assert dag2.stats()["trials"] == 1
        a, _ = dag2.best("t|1|x")
        assert a == "act"


def test_statistical_learning_dominates():
    """After many trials, the winning action beats the noisy one."""
    dag = TaskDAG()
    for i in range(20):
        dag.merge("s|1|", "good_action", "ok")
    for i in range(20):
        dag.merge("s|1|", "noisy_action", "ok" if i % 2 == 0 else "fail")
    a, st = dag.best("s|1|")
    assert a == "good_action", a
    assert st["w"] >= 20


# ---------------------------------------------------------------------------
# Tree: exhaustive expansion + selection
# ---------------------------------------------------------------------------

def test_tree_expands_all_candidates():
    dag = TaskDAG()
    def cands(sig):
        return ["a1", "a2", "a3", "a4", "a5"]
    t = TaskTree("task", 1, dag, cands)
    n = t.expand()
    assert n == 5, n
    assert len(t.leaves) == 5
    assert len(t.nodes) == 6  # root + 5


def test_tree_ask_filters_candidates():
    dag = TaskDAG()
    def cands(sig):
        return ["save_code", "run_tests", "deploy", "heal_server"]
    t = TaskTree("task", 1, dag, cands, ask="save")
    n = t.expand()
    assert n == 1, n
    assert t.leaves[0].action == "save_code"


def test_tree_blocked_filtered():
    dag = TaskDAG()
    def cands(sig):
        return ["save", "deploy", "heal"]
    t = TaskTree("task", 1, dag, cands)
    n = t.expand(blocked=["deploy"])
    assert n == 2
    actions = {c.action for c in t.leaves}
    assert "deploy" not in actions


def test_tree_select_prefers_proven():
    dag = TaskDAG()
    dag.merge("task|1|", "proven", "ok")
    dag.merge("task|1|", "proven", "ok")
    dag.merge("task|1|", "proven", "ok")
    dag.merge("task|1|", "untried", "ok")  # single trial
    def cands(sig):
        return ["proven", "untried", "random"]
    t = TaskTree("task", 1, dag, cands)
    t.expand()
    chosen = t.select()
    assert chosen.action == "proven", chosen.action


def test_tree_select_prefer_hint():
    dag = TaskDAG()
    def cands(sig):
        return ["run_tests", "save_code", "deploy"]
    t = TaskTree("task", 1, dag, cands, ask="save")
    t.expand()
    chosen = t.select()
    assert chosen.action == "save_code"


# ---------------------------------------------------------------------------
# Runner: full loop with compare-and-rebuild
# ---------------------------------------------------------------------------

def test_runner_completes_on_quality_gate():
    dag = TaskDAG()
    calls = []
    def cands(sig):
        return ["save_code", "run_tests"]
    def exec(action, sig):
        calls.append(action)
        return {"ok": True, "result": "saved ok", "quality": 0.9}
    r = TaskTreeRunner("write_file", dag, cands, exec, quality_gate=0.5,
                       max_steps=3)
    out = r.run()
    assert out["completed"] is True, out
    assert len(r.steps) == 1  # one step, quality gate hit
    assert calls == ["run_tests"]  # both untried: deterministic tie -> alpha
    assert dag.stats()["trials"] == 1


def test_runner_continues_on_failure_new_tree_each_step():
    """Fail step 1 -> new tree rooted at carried result -> succeed step 2."""
    dag = TaskDAG()
    calls = []
    def cands(sig):
        return ["fix_a", "fix_b"]
    def exec(action, sig):
        calls.append(action)
        if action == "fix_a":
            return {"ok": False, "result": "compile error", "quality": 0.1}
        return {"ok": True, "result": "fixed", "quality": 0.9}
    r = TaskTreeRunner("build", dag, cands, exec, max_steps=4, quality_gate=0.5)
    out = r.run()
    assert out["completed"] is True, out
    assert len(r.steps) == 2, out["steps"]  # fail then success
    assert calls == ["fix_a", "fix_b"], calls  # NMTD: fix_a blocked after fail
    # DAG recorded both outcomes
    assert dag.stats()["trials"] == 2
    assert dag.stats()["actions"] == 2  # fix_a (fail) + fix_b (ok)


def test_runner_blocks_never_retry():
    dag = TaskDAG()
    calls = []
    def cands(sig):
        return ["fix_a", "fix_b"]
    def exec(action, sig):
        calls.append(action)
        return {"ok": True, "result": "done", "quality": 0.9}
    r = TaskTreeRunner("build", dag, cands, exec, blocked=["fix_a"], max_steps=2)
    out = r.run()
    assert calls == ["fix_b"], calls


def test_runner_no_candidates_stops():
    dag = TaskDAG()
    def cands(sig):
        return []
    r = TaskTreeRunner("empty", dag, cands, lambda a, s: {"ok": False},
                       max_steps=3)
    out = r.run()
    assert out["completed"] is False
    assert out["steps"][0]["status"] == "no-candidates"


def test_runner_max_steps_bounded():
    dag = TaskDAG()
    def cands(sig):
        return ["attempt"]
    def exec(action, sig):
        return {"ok": False, "result": "still failing", "quality": 0.0}
    r = TaskTreeRunner("hard", dag, cands, exec, max_steps=3, quality_gate=0.5)
    out = r.run()
    assert out["completed"] is False
    # NMTD: first fail blocks "attempt" -> step 2 finds no candidates -> stops
    assert len(r.steps) == 2, r.steps
    assert r.steps[1]["status"] == "no-candidates"


def test_runner_persists_trees():
    with tempfile.TemporaryDirectory() as td:
        dag = TaskDAG()
        def cands(sig):
            return ["act"]
        def exec(action, sig):
            return {"ok": True, "result": "ok", "quality": 0.9}
        r = TaskTreeRunner("persist_me", dag, cands, exec,
                           tree_dir=td, max_steps=2)
        r.run()
        files = os.listdir(td)
        assert any("task_tree_" in f for f in files), files
        assert "task_tree_latest.txt" in files


def test_render_ascii_contains_chosen():
    dag = TaskDAG()
    def cands(sig):
        return ["save_code", "run_tests", "deploy"]
    t = TaskTree("task", 1, dag, cands, ask="save")
    t.expand()
    r = t.render_ascii()
    assert "CHOSEN: save_code" in r, r
    assert "├─" in r


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
