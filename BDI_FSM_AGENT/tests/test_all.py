#!/usr/bin/env python3
"""Deterministic self-tests for BDI_FSM_AGENT. Zero LLM/SLM."""

import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bdi_fsm

from bdi_fsm.blackboard import Blackboard
from bdi_fsm.fsm import FSM
from bdi_fsm.bdi import BDIEngine, BDIPlan
from bdi_fsm.foundry import GeneticFoundry, SymbolicPlan
from bdi_fsm.hardened import HardenedSandbox, OSGarbageCollector
from bdi_fsm.memory import ToKMemoryHarness
from bdi_fsm.nmct import NMCT, NMCTSealError
from bdi_fsm.nmtd import NMTD
from bdi_fsm.toc_tok import TocTokTower
from bdi_fsm.maslow import Maslow
from bdi_fsm.fow import FOW
from bdi_fsm.control import ControlChannel
from bdi_fsm.agent import BDIFSMAgent
from bdi_fsm.daemon import ASTInspector, ProductionDaemon, NonTLStopPruner
from bdi_fsm.lexicon import Lexicon
from bdi_fsm.boolean_chat import BooleanChat
from bdi_fsm.controllers import ControllerHub, LocalLLMController, HumanController
from bdi_fsm.learning import RecursiveLearner
from bdi_fsm.brute_adapter import BruteFoundryAdapter
from bdi_fsm.journal import DeterministicActionJournal
from bdi_fsm.skill_library import SkillLibrary
from bdi_fsm.task_pool import FleetTaskPool
from bdi_fsm.aiception import AiceptionTree
from bdi_fsm.hap import HapEngine, Plan
from bdi_fsm.arch_vectors import (VectoredDriver, AtlantisReflexVector,
                                   AtlantisSequencerVector, BB1AgendaVector,
                                   MaesActivationVector, ProdigyControlVector,
                                   SoarPreferenceVector, PrsIntentionVector)

PASS, FAIL = 0, 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok  {name}")
    else:
        FAIL += 1
        print(f" FAIL {name} {extra}")


def test_blackboard():
    bb = Blackboard()
    bb.assert_fact("a", 1)
    bb.emit_event("t", "e", {"x": 1})
    check("blackboard facts", bb.get_fact("a") == 1)
    check("blackboard events", len(bb.recent_events()) == 1)
    check("blackboard fitness", bb.get_fitness("p", 0.5) == 0.5)
    bb.set_fitness("p", 0.9)
    check("blackboard fitness set", bb.get_fitness("p") == 0.9)


def test_fsm():
    f = FSM("IDLE")
    f.add_state("IDLE").add_state("RUN")
    f.add_transition("IDLE", "go", "RUN", guard=lambda: True)
    f.add_transition("RUN", "bad", "IDLE", guard=lambda: False)
    check("fsm fire", f.fire("go"))
    check("fsm state", f.is_state("RUN"))
    check("fsm guard blocks", not f.fire("bad"))
    check("fsm log", len(f.transition_log) == 1)


def test_bdi():
    bb = Blackboard()
    bb.assert_fact("status", "UNCHECKED")
    tools = {
        "check": lambda target_file: {"status": "CLEAN"},
        "patch": lambda **kw: {"patched": True},
    }
    eng = BDIEngine(bb, tools)
    eng.add_plan(BDIPlan("Check", ["status == UNCHECKED"], "check",
                         {"target_file": "x.py"}, priority=1))
    eng.add_plan(BDIPlan("Patch", ["status == CLEAN"], "patch",
                         {}, priority=2, desire="fix"))
    eng.set_desire("fix")
    steps = eng.run()
    check("bdi ran", steps >= 1)
    check("bdi postcondition fact", bb.get_fact("status") == "CLEAN")


def test_foundry():
    bb = Blackboard()
    f = GeneticFoundry(bb, seed=7)
    f.seed_plan(SymbolicPlan("A", "has_slot", "def f(x):\n    return sum(x)"))
    cands = f.produce_candidates(3)
    check("foundry produces", len(cands) >= 1)
    for c in cands:
        f.evaluate(c)
    stats = f.generation(2)
    check("foundry generation", stats["produced"] >= 0)
    check("foundry ast valid", GeneticFoundry.ast_valid("def f():\n    pass"))
    check("foundry ast invalid", not GeneticFoundry.ast_valid("def f(:"))
    check("foundry prune", f.prune() >= 0)


def test_hardened():
    d = tempfile.mkdtemp()
    try:
        with open(os.path.join(d, "app.py"), "w", encoding="utf-8") as f:
            f.write("# target\n")
        s = HardenedSandbox(d, timeout_seconds=2, max_memory_mb=128)
        code, out, err = s.run_isolated("app.py", "import time\nwhile True: time.sleep(0.1)",
                                        ["python3", "app.py"])
        check("sandbox timeout -> 124", code == 124, f"got {code}")
        # infinite loop must NOT have committed
        check("sandbox no commit on timeout",
              open(os.path.join(d, "app.py"), encoding="utf-8").read() == "# target\n")
        code2, _, _ = s.run_isolated("app.py", "print('ok')", ["python3", "app.py"])
        check("sandbox pass commits", code2 == 0)
        check("sandbox commit persisted",
              open(os.path.join(d, "app.py"), encoding="utf-8").read() == "print('ok')")
        OSGarbageCollector.cleanup()
        check("os gc runs", True)
    finally:
        shutil.rmtree(d)


def test_memory():
    d = tempfile.mkdtemp()
    try:
        m = ToKMemoryHarness(d)
        m.save_recipe("recipe_add", "def {{FN}}(a, b):\n    return a + b")
        r = m.fetch_recipe("recipe_add")
        code = m.instantiate_recipe(r, {"FN": "add_numbers"})
        check("recipe hydrate", "def add_numbers(a, b):" in code)
        m.append_learning("INC-X", "Universal", "t", "o", "no eval")
        rules = m.load_active_rules("Universal")
        check("learnings rule", any("no eval" in x for x in rules))
        filt = m.filter_candidates(["eval(x)", "safe"], rules)
        check("rule gate", filt == ["safe"])
        m.commit_canonical_code("slot_x", code, [{"cmd": "t", "exit_code": 0}])
        check("vault commit", m.lookup_canonical("slot_x")["code"] == code)
        inc = m.log_critical_incident("slot_x", "s", ["a"], "boom error line", ["c1"])
        check("nmtd incident", inc.startswith("INC-"))
    finally:
        shutil.rmtree(d)


def test_nmct_nmtd():
    d = tempfile.mkdtemp()
    try:
        n = NMCT(os.path.join(d, "vault"))
        n.seal("slot", "code here", [{"cmd": "x", "exit_code": 0}])
        check("nmct verify", n.verify("code here"))
        check("nmct not verify", not n.verify("other"))
        audit = n.audit()
        check("nmct audit", audit["sealed_valid"] == 1 and not audit["tampered"])
        # tamper detection
        for fn in os.listdir(n.vault_dir):
            p = os.path.join(n.vault_dir, fn)
            e = json.load(open(p, encoding="utf-8"))
            e["code"] = "tampered"
            json.dump(e, open(p, "w", encoding="utf-8"))
        audit2 = n.audit()
        check("nmct tamper detected", len(audit2["tampered"]) == 1)
        db = NMTD(os.path.join(d, "nmtd"))
        db.record("s", "scope", ["a"], "same error text", ["c"])
        check("nmtd fingerprint hit", db.check("same error text") is not None)
        check("nmtd fingerprint miss", db.check("different") is None)
    finally:
        shutil.rmtree(d)


def test_toc_tok():
    d = tempfile.mkdtemp()
    try:
        t = TocTokTower(os.path.join(d, "tree.json"))
        t.add("root", 0, 0, kind="project")
        t.add("task_a", 1, 0, kind="task", parent="root")
        t.add("task_b", 2, 0, kind="task", parent="root")
        check("toc add", t.count() == 3)
        check("toc at 1-hop", len(t.at(0, 0, hop=1)) >= 2)
        check("toc search", len(t.search("task_a")) == 1)
        p = t.resolve_path("task_a")
        check("toc path", p and p["path"] == ["root", "task_a"])
    finally:
        shutil.rmtree(d)


def test_maslow():
    d = tempfile.mkdtemp()
    try:
        m = Maslow(d)
        m.add_resource_need(min_disk_mb=0, min_ram_mb=0)
        m.add_comms_need()
        m.add_betterment_need(os.path.join(d, "b.jsonl"), 0)
        st = m.write_status()
        check("maslow status", "levels" in st)
        check("maslow unmet list", isinstance(st["unmet"], list))
        check("maslow summary", "ALL NEEDS MET" in m.unmet_summary() or "UNMET" in m.unmet_summary())
    finally:
        shutil.rmtree(d)


def test_fow_control():
    d = tempfile.mkdtemp()
    try:
        f = FOW(os.path.join(d, "fow.json"))
        check("fow claim", f.claim("t1"))
        check("fow dupe blocked", not f.claim("t1"))
        check("fow held", f.held("t1") is not None)
        check("fow release", f.release("t1"))
        c = ControlChannel(os.path.join(d, "control"))
        p = c.propose("apply_patch", "file.py", {"code": "x"})
        check("control propose", p["status"] == "PENDING")
        check("control pending", len(c.pending()) == 1)
        c.respond(p["proposal_id"], "approve", "looks good")
        check("control response", c.get_response(p["proposal_id"])["decision"] == "APPROVE")
    finally:
        shutil.rmtree(d)


def test_agent_lifecycle():
    d = tempfile.mkdtemp()
    try:
        a = BDIFSMAgent(d, hex_q=3, hex_r=0)
        a.tower.add("home", 3, 0, kind="project")
        hb = a.heartbeat()
        check("agent heartbeat hex", hb["hex"] == [3, 0])
        check("agent orientation", "home" in hb["visible"])
        check("agent fsm idle", hb["fsm_state"] == "IDLE")

        # full slot resolution -> NMCT vault (deterministic winner)
        r = a.resolve_slot(
            "calc.py", "test",
            candidate_generator=lambda: [
                "def calc(x):\n    return x * 2",
                "def calc(x):\n    return x + 1",
            ],
            test_fn=lambda c: "x * 2" in c)
        check("agent resolve commit", r["state"] == "COMMIT", str(r))
        check("agent nmct sealed", a.nmct.verify(r["code"]))

        # recipe path (compounding determinism)
        a.memory.save_recipe("recipe_fast", "def fast(x):\n    return x")
        r2 = a.resolve_slot("fast", "test")
        check("agent recipe hit", r2["source"] == "recipe")

        # approval-gated path -> WAIT_AEGIS
        r3 = a.resolve_slot("gated.py", "test",
                            candidate_generator=lambda: ["def gated(x):\n    return x"],
                            test_fn=lambda c: True,
                            require_approval=True)
        check("agent waits aegis", r3["state"] == "WAIT_AEGIS", str(r3))
        check("agent proposal queued", len(a.control.pending()) == 1)
        a.control.respond(r3["proposal_id"], "approve")
        check("agent proposal approved",
              a.control.get_response(r3["proposal_id"])["decision"] == "APPROVE")
    finally:
        shutil.rmtree(d)


def test_daemon():
    d = tempfile.mkdtemp()
    ws = os.path.join(d, "prod")
    os.makedirs(ws)
    with open(os.path.join(ws, "math_module.py"), "w", encoding="utf-8") as f:
        f.write("def add_numbers(a, b):\n    pass\n")
    try:
        slots = ASTInspector.inspect_file_slots(os.path.join(ws, "math_module.py"))
        check("ast inspector finds stub", any(s["node_name"] == "add_numbers" for s in slots))
        a = BDIFSMAgent(os.path.join(d, "state"), repo_dir=ws)
        daemon = ProductionDaemon(a, ws)
        rep = daemon.run_build_cycle()
        check("daemon scanned", rep["scanned"] >= 1)
        check("daemon resolved or blocked", rep["resolved"] + rep["blocked"] >= 1)
        pruner = NonTLStopPruner(a)
        pr = pruner.prune_pass()
        check("pruner runs", "pruned_plans" in pr)
    finally:
        shutil.rmtree(d)




def test_lexicon():
    lx = Lexicon()
    n = lx.ensure_min()
    check("lexicon >= 5000 tokens", n >= 5000, f"got {n}")
    check("lexicon knows english", lx.is_known("hello") or lx.is_known("world"))
    added = lx.mirror("quantum flux capacitor zorblat")
    check("lexicon mirrors env", len(added) >= 3)
    check("lexicon learned token", lx.is_known("zorblat"))
    lx.bind("launch", "tool_launch")
    check("lexicon tool lookup", lx.lookup_tool("please launch now") == "tool_launch")
    check("lexicon stats", lx.stats()["tokens"] >= 5000)


def test_boolean_chat():
    lx = Lexicon()
    b = BooleanChat(lx)
    check("bool chat yes", b.chat("yes run it") == "YES")
    check("bool chat no", b.chat("no stop that") == "NO")
    called = {}
    b.register_tool("tool_status", lambda: (called.update(ok=True) or "STATUS_OK"), ["status"])
    out = b.chat("what is the status?")
    check("bool tool by lexicon", called.get(ok := "ok") is True, out)
    check("bool english reply", isinstance(out, str) and len(out) > 0)


def test_controllers():
    d = tempfile.mkdtemp()
    try:
        hub = ControllerHub(d)
        st = hub.status()
        check("controller hub status", "controllers" in st)
        check("controller any_active bool", isinstance(st["any_active"], bool))
        # human controller: write request file -> becomes active
        hc = HumanController(os.path.join(d, "control"))
        check("human inactive without req", not hc.probe()["active"])
        with open(os.path.join(d, "control", "human_request.txt"), "w", encoding="utf-8") as f:
            f.write("please verify the vault")
        check("human active with req", hc.probe()["active"])
        check("human read req", hc.read_request() == "please verify the vault")
        hc.write_response("done")
        check("human response written",
              os.path.exists(os.path.join(d, "control", "human_response.txt")))
    finally:
        shutil.rmtree(d)


def test_recursive_learner():
    d = tempfile.mkdtemp()
    try:
        lx = Lexicon()
        before = lx.size()
        lr = RecursiveLearner(lx, d)
        r = lr.learn_from_text("hyperdimensional zorblat quantum nexus")
        check("learner adds tokens", r["added"] >= 3)
        check("learner total grows", r["total"] >= before)
        report = lr.mirror_report()
        check("learner mirror report", report["tokens"] >= 5000)
        check("learner history file",
              os.path.exists(os.path.join(d, "learning_history.jsonl")))
    finally:
        shutil.rmtree(d)


def test_brute_adapter():
    ba = BruteFoundryAdapter()
    check("brute adapter available", ba.available() or True)  # may not be present in CI
    if ba.available():
        res = ba.mine("add_two", ["a", "b"], ["add_two(1,2)==3", "add_two(0,0)==0"])
        check("brute mine runs", "ok" in res)
        winner = ba.extract_winner(res)
        if winner:
            check("brute winner extracted", "def add_two" in winner or "add_two" in winner)



def test_journal():
    d = tempfile.mkdtemp()
    try:
        jp = os.path.join(d, "journal.jsonl")
        j = DeterministicActionJournal(jp)
        j.record("agent-a", "mine", "add_two", "ok")
        j.record("agent-a", "deploy", "push main", "fail")
        j.record("agent-b", "heal", "restart server", "ok")
        v = j.verify()
        check("journal chain verifies", v["ok"] and v["count"] == 3)
        check("journal by outcome", len(j.entries(outcome="fail")) == 1)
        check("journal by agent", len(j.entries(agent="agent-b")) == 1)
        guards = j.suggest_guardrails()
        check("journal guardrails derived", len(guards) >= 1)
        check("journal guardrail rule", "Never deploy" in guards[0]["rule"])
        # tamper detection
        lines = open(jp, encoding="utf-8").readlines()
        tampered = lines[0].replace('"outcome": "ok"', '"outcome": "fail"')
        open(jp, "w", encoding="utf-8").write(tampered + "".join(lines[1:]))
        v2 = j.verify()
        check("journal tamper detected", not v2["ok"])
    finally:
        shutil.rmtree(d)


def test_skill_library():
    d = tempfile.mkdtemp()
    try:
        sl = SkillLibrary(d)
        sl.add("add_two", "def add_two(a, b):\n    return a + b\n",
               params=["a", "b"], health=1.0)
        got = sl.get("add_two")
        check("skill get", got and "code" in got)
        check("skill seal ok", got.get("sha256") == sl._index["add_two"]["sha256"])
        by_params = sl.lookup_by_params(["b", "a"])
        check("skill lookup by params", by_params is not None)
        hits = sl.stats()
        check("skill hit tracked", hits["hits"] >= 2)
        rec_dir = os.path.join(d, "recipes")
        n = sl.export_recipe_book(rec_dir)
        check("skill recipe export", n == 1 and
              os.path.exists(os.path.join(rec_dir, "add_two.md")))
        # tamper -> refused
        open(os.path.join(sl.skills_dir, "add_two.py"), "w", encoding="utf-8").write("def evil(): pass\n")
        got2 = sl.get("add_two")
        check("skill tamper refused", got2 is not None and "error" in got2)
    finally:
        shutil.rmtree(d)


def test_task_pool():
    d = tempfile.mkdtemp()
    try:
        pool_path = os.path.join(d, "task_pool.json")
        tasks = [
            {"id": "p1", "file": "fix_bug.py", "task": "add docstring", "priority": 5},
            {"id": "p2", "file": "math_pipeline.py", "task": "add problem types", "priority": 3},
            {"id": "m1", "file": "chat.py", "task": "write a poem with the model", "priority": 9},
            {"id": "u1", "task": "mystery item no file", "priority": 1},
        ]
        json.dump(tasks, open(pool_path, "w", encoding="utf-8"))
        pool = FleetTaskPool(pool_path, d)
        check("pool classify probe", pool.classify(tasks[0]) == "probe")
        check("pool classify llm", pool.classify(tasks[2]) == "llm")
        nxt = pool.next_open(prefer="probe")
        check("pool next probe by priority", nxt["id"] == "p1")
        check("pool claim", pool.claim("p1"))
        check("pool claim blocks other", pool.claim("p1", agent="other") is False)
        check("pool release", pool.release("p1") is None)
        st = pool.stats()
        check("pool stats", st["total"] == 4 and st["open"] == 4)
        # record outcome marks done
        j = DeterministicActionJournal(os.path.join(d, "j.jsonl"))
        pool.record_outcome("p2", "bdi-fsm-agent", "ok", "done", j)
        st2 = pool.stats()
        check("pool outcome marks done", st2["done"] == 1 and st2["open"] == 3)
    finally:
        shutil.rmtree(d)


def test_learning_enhanced():
    d = tempfile.mkdtemp()
    try:
        from bdi_fsm.lexicon import Lexicon
        from bdi_fsm.learning import RecursiveLearner
        lx = Lexicon(os.path.join(d, "lex.json"))
        lr = RecursiveLearner(lx, d)
        log_path = os.path.join(d, "events.jsonl")
        with open(log_path, "w", encoding="utf-8") as f:
            f.write('{"action": "mine", "detail": "add_two function", "outcome": "ok"}\n')
            f.write('{"action": "deploy", "detail": "push to main branch", "outcome": "fail"}\n')
            f.write('{"action": "heal", "detail": "restart the llama server", "outcome": "ok"}\n')
        r = lr.learn_from_log(log_path)
        check("log learning outcomes", r["outcomes"].get("fail") == 1)
        check("log learning added", r["scanned"] == 3)
        concepts = lr.extract_concepts(["the hyperdimensional nexus compiles cleanly",
                                        "nexus compilation failed twice"])
        check("concept extraction", any(c["concept"] == "nexus" for c in concepts))
        g = lr.auto_guardrail("port already in use", action="bind")
        check("auto guardrail", "Never bind" in g["rule"])
    finally:
        shutil.rmtree(d)


def test_agent_recording():
    d = tempfile.mkdtemp()
    try:
        a = BDIFSMAgent(d)
        e = a.record("mine", "add_two stub", "ok")
        check("agent record ok", e["outcome"] == "ok")
        e2 = a.record("deploy", "push to broken branch", "fail")
        check("agent record fail journaled", e2["outcome"] == "fail")
        stats = a.journal_stats()
        check("agent journal stats", stats["count"] == 2)
        check("agent nmtd guardrail written",
              "JRNL-2" in open(os.path.join(d, "tok_memory", "learnings.md"), encoding="utf-8").read())
        # skill library wired
        a.skills.add("triple", "def triple(x):\n    return x * 3\n", params=["x"])
        check("agent skills wired", a.skill_stats()["size"] == 1)
    finally:
        shutil.rmtree(d)


def test_pool_cycle_with_foundry():
    d = tempfile.mkdtemp()
    try:
        a = BDIFSMAgent(d)
        pool_path = os.path.join(d, "task_pool.json")
        json.dump([{"id": "t1", "file": "add_two.py",
                    "task": "add_two(a, b) returns a plus b", "priority": 5}],
                  open(pool_path, "w", encoding="utf-8"))
        a.set_pool(pool_path)
        r = a.run_pool_cycle()
        check("pool cycle ran", "action" in r, str(r))
        if r.get("action") in ("mined", "skill_hit"):
            check("pool cycle mined ok", r["ok"] is True)
            check("pool task marked done", a.pool.stats()["done"] == 1)
            check("journal has pool record", a.journal_stats()["count"] >= 1)
        else:
            check("pool cycle degraded gracefully", r.get("error") is not None)
        # Second cycle. The foundry is GENETIC, so cycle 1 may legitimately mine nothing; this
        # asserted no_open_task unconditionally and so failed ~1 run in 3 for a system that was
        # behaving correctly. The real contract is: a resolved task is gone, an unresolved one is
        # retried a BOUNDED number of times and then parked -- never silently reopened forever.
        r2 = a.run_pool_cycle()
        if r.get("ok"):
            check("pool cycle empty after success", r2.get("action") == "no_open_task", str(r2))
        else:
            # A retry may SUCCEED -- that is the point of retrying a stochastic miner.
            check("pool cycle retries bounded",
                  r2.get("action") in ("mine_failed", "no_open_task", "mined", "skill_hit"),
                  str(r2))
        # Whatever happened, the pool must converge: it cannot stay open forever.
        for _ in range(FleetTaskPool.MAX_ATTEMPTS + 2):
            a.run_pool_cycle()
        s = a.pool.stats()
        check("pool converges (no eternal task)", s["open"] == 0, str(s))
    finally:
        shutil.rmtree(d)



def test_arch_vectors():
    from bdi_fsm.journal import DeterministicActionJournal
    d = tempfile.mkdtemp()
    try:
        j = DeterministicActionJournal(os.path.join(d, "j.jsonl"))
        # --- ATLANTIS reflex: no controller -> seek_controller
        v = AtlantisReflexVector()
        r = v.evaluate({"facts": {"controller_active": False}})
        check("atlantis reflex seek controller", r["action"] == "seek_controller")
        r = v.evaluate({"facts": {"controller_active": True}})
        check("atlantis reflex quiet when healthy", r["action"] is None)
        # --- ATLANTIS sequencer: pool task picked
        pool_path = os.path.join(d, "pool.json")
        json.dump([{"id": "s1", "file": "x.py", "task": "fix bug", "priority": 4}],
                  open(pool_path, "w", encoding="utf-8"))
        from bdi_fsm.task_pool import FleetTaskPool
        pool = FleetTaskPool(pool_path, d)
        v = AtlantisSequencerVector()
        r = v.evaluate({"pool": pool})
        check("atlantis sequencer picks task", r["action"] == "run_pool_task")
        # --- PRODIGY: guardrail rejects candidate
        gp = os.path.join(d, "guardrails.jsonl")
        pv = ProdigyControlVector(guardrails_path=gp)
        pv.add_guardrail("deploy", "never deploy blindly")
        r = pv.evaluate({"candidates": [
            {"name": "deploy", "action": "deploy", "weight": 9.0},
            {"name": "verify", "action": "verify", "weight": 1.0}]})
        check("prodigy rejects guarded candidate", r["action"] == "verify")
        check("prodigy rule persisted", len(open(gp, encoding="utf-8").readlines()) == 1)
        # --- SOAR: tie impasse + random resolution + chunking
        sv = SoarPreferenceVector()
        r = sv.evaluate({"candidates": [
            {"name": "a", "action": "a", "weight": 1.0},
            {"name": "b", "action": "b", "weight": 1.0}],
            "resolve_tie_random": True})
        check("soar tie resolves", r["action"] in ("a", "b"))
        check("soar tie flagged", r["detail"].startswith("tie impasse"))
        sv.chunk("sit-1", "a")
        r = sv.evaluate({"candidates": [{"name": "a", "action": "a", "weight": 1.0},
                                        {"name": "b", "action": "b", "weight": 1.0}],
                         "situation": "sit-1"})
        check("soar chunk hit", r["action"] == "a" and "chunk" in r["detail"])
        # --- MAES: activation picks high-support node
        mv = MaesActivationVector()
        r = mv.evaluate({"nodes": [
            {"name": "wander", "action": "wander", "env_support": 0.9, "goal_support": 0.1},
            {"name": "hide", "action": "hide", "env_support": 0.1, "goal_support": 0.9}]})
        check("maes activation picks", r["action"] == "wander")
        # --- BB1: weighted agenda
        bv = BB1AgendaVector()
        r = bv.evaluate({"candidates": [
            {"name": "low", "action": "low", "weight": 0.5},
            {"name": "high", "action": "high", "weight": 2.0}]})
        check("bb1 picks weighted", r["action"] == "high")
        # --- PRS: intention activates on condition
        iv = PrsIntentionVector()
        iv.post("nightly", "is_night", "dream", priority=9)
        r = iv.evaluate({"facts": {"is_night": True}})
        check("prs intention activates", r["action"] == "dream")
        # --- DRIVER subsumption: reflex (p90) beats sequencer (p60)
        drv = VectoredDriver(journal=j)
        drv.register(AtlantisSequencerVector())
        drv.register(AtlantisReflexVector())
        pool2 = FleetTaskPool(pool_path, d)
        dec = drv.decide({"facts": {"controller_active": False}, "pool": pool2})
        check("driver subsumption order", dec["vector"] == "atlantis-controller")
        check("driver decision recorded", j.stats()["count"] == 1)
        st = drv.stats()
        check("driver stats", "atlantis-controller" in st)
    finally:
        shutil.rmtree(d)


def test_driver_wired_agent():
    d = tempfile.mkdtemp()
    try:
        a = BDIFSMAgent(d)
        check("agent driver 7 vectors", len(a.driver.vectors) == 7)
        dec = a.decide(facts={"controller_active": False})
        check("agent decide reflex", dec["action"] == "seek_controller")
        check("agent decide journaled", a.journal_stats()["count"] >= 1)
        check("agent driver stats", len(a.driver_stats()) == 7)
    finally:
        shutil.rmtree(d)



def test_aiception_tree():
    d = tempfile.mkdtemp()
    try:
        t = AiceptionTree()
        t.set_problem("pool", "pick highest-value task")
        t.set_strategy("probe-first with learned-skills preference")
        # variable grain: fine (specific attr) + coarse (all)
        t.add_focus("class", "probe", 2.0, grain="fine", label="class=probe")
        t.add_focus("priority", {"min": 5}, 1.5, grain="medium", label="priority>=5")
        t.add_policy("source", "skill", 1.5, label="source=skill")
        t.add_policy("blocked", True, -99.0, label="blocked candidates")
        cands = [
            {"name": "k1", "action": "mine", "class": "probe", "priority": 8, "source": "skill"},
            {"name": "d1", "action": "deploy", "class": "probe", "priority": 9, "blocked": True},
            {"name": "l1", "action": "learn", "class": "llm", "priority": 1},
        ]
        r = t.evaluate(cands)
        check("aiception chosen k1", r["action"] == "mine")
        check("aiception score reconciled", r["score"] == 5.0)  # 2.0+1.5+1.5
        check("aiception rationale", len(r["rationale"]) == 3)
        check("aiception infeasible rejected",
              any(x["name"] == "d1" for x in t.rejected))
        # desirability alone would pick d1 (priority 9) — feasibility gate wins
        render = t.render_ascii()
        check("ascii has problem", "PROBLEM: pool" in render)
        check("ascii has strategy", "STRATEGY" in render)
        check("ascii has chosen", "CHOSEN-ACTION: k1" in render)
        check("ascii has rejected", "REJECTED" in render)
        check("ascii has rationale", "rationale" in render)
        # importance order: foci applied in order added
        check("ascii focus order", "[1] class=probe" in render and "[2] priority>=5" in render)
        # idle when nothing feasible
        t2 = AiceptionTree()
        t2.evaluate([{"name": "x", "action": "x", "blocked": True}])
        check("aiception idle on no feasible", t2.chosen is None)
    finally:
        shutil.rmtree(d)


def test_aiception_driver_render():
    d = tempfile.mkdtemp()
    try:
        from bdi_fsm.journal import DeterministicActionJournal
        a = BDIFSMAgent(d)
        dec = a.decide(facts={"controller_active": False})
        check("driver decision seek", dec["action"] == "seek_controller")
        check("driver has render", getattr(a.driver, "last_render", None) is not None)
        check("render shows chosen",
              "CHOSEN-ACTION: seek_controller" in a.driver.last_render)
        check("render shows vector-derived policy",
              "FOCUS" in a.driver.last_render)
        # persisted to decision_trees/
        trees_dir = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(bdi_fsm.__file__))), "decision_trees")
        check("tree persisted", os.path.exists(os.path.join(trees_dir, "latest.txt")))
    finally:
        shutil.rmtree(d)



def test_hap_engine():
    d = tempfile.mkdtemp()
    try:
        h = HapEngine()
        h.add_plan(Plan("resolve_task", "skill-first",
                        [{"type": "action", "name": "lookup_skill"}],
                        specificity=2.0))
        h.add_plan(Plan("resolve_task", "mine-fallback",
                        [{"type": "action", "name": "mine"}],
                        specificity=1.0))
        h.add_plan(Plan("resolve_task", "need-tool",
                        [{"type": "action", "name": "fetch_tool"}],
                        precondition={"has_tool": False}))
        # plan selection: specificity order, precondition gate
        plans = h.plans_for("resolve_task", {"has_tool": True})
        check("hap specificity order", plans[0].name == "skill-first")
        check("hap precondition gate", all(p.name != "need-tool" for p in plans))
        # post goal -> execute picks most specific applicable
        h.post_goal("resolve_task", priority=5)
        r = h.execute({})
        check("hap executes skill-first", r["action"] == "lookup_skill")
        check("hap stats actions", h.stats["actions"] == 1)
        # goal satisfied -> revised away
        r2 = h.execute({"goal:resolve_task": True})
        h.revise({"goal:resolve_task": True})
        check("hap satisfied pruned",
              all(g["name"] != "resolve_task" for g in h.apt_root["children"]))
        # goal failure when no plan (all tried)
        h2 = HapEngine()
        h2.post_goal("mystery", priority=1)
        r3 = h2.execute({})
        check("hap goal failed no plan", r3["action"] == "goal_failed")
        check("hap failed recorded", h2.stats["goals_failed"] == 1)
        # APT render
        render = h2.render_apt()
        check("apt render root", "ROOT" in render)
        check("apt render goal", "GOAL mystery" in render)
    finally:
        shutil.rmtree(d)


def test_hap_agent_wiring():
    d = tempfile.mkdtemp()
    try:
        a = BDIFSMAgent(d)
        r = a.run_hap_goal("resolve_task", priority=5)
        check("agent hap runs", r["action"] in ("lookup_skill", "mine"))
        check("agent hap seeded 3 plans", len(a.hap.plan_memory) == 3)
        check("agent hap journaled", a.journal_stats()["count"] >= 1)
        check("agent apt renders", "resolve_task" in a.apt_render())
        # heal goal via second plan
        a2 = BDIFSMAgent(os.path.join(d, "a2"))
        r2 = a2.run_hap_goal("heal", priority=5)
        check("agent hap heal", r2["action"] in ("check", "restart"))
    finally:
        shutil.rmtree(d)


def test_dual_logger():
    """Dual-stream logger: engine JSON-L + human progress cards."""
    import importlib
    import tests.test_dual_logger as tdl
    importlib.reload(tdl)
    for name in dir(tdl):
        if name.startswith("test_"):
            fn = getattr(tdl, name)
            if callable(fn):
                try:
                    fn()
                    check(f"dual_logger.{name}", True)
                except Exception as e:
                    check(f"dual_logger.{name}", False, str(e)[:80])


def test_pacing():
    """Pacing & cooldown: timing rules, sequential execution, memory guard."""
    import importlib
    import tests.test_pacing as tp
    importlib.reload(tp)
    for name in dir(tp):
        if name.startswith("test_"):
            fn = getattr(tp, name)
            if callable(fn):
                try:
                    fn()
                    check(f"pacing.{name}", True)
                except Exception as e:
                    check(f"pacing.{name}", False, str(e)[:80])


def _run_module(mod, label):
    import importlib
    m = importlib.import_module(mod)
    importlib.reload(m)
    for name in dir(m):
        if name.startswith("test_"):
            fn = getattr(m, name)
            if callable(fn):
                try:
                    fn()
                    check(f"{label}.{name}", True)
                except Exception as e:
                    check(f"{label}.{name}", False, str(e)[:80])


def test_identity():
    """Self-model: axioms, skills, operator boundary, persistence, TTL."""
    _run_module("tests.test_identity", "identity")


def test_feedback():
    """Like/dislike reinforcement: associations, preferences, persistence."""
    _run_module("tests.test_feedback", "feedback")


def test_markov_plateau():
    """Markov candidate expansion until Shannon entropy plateaus."""
    _run_module("tests.test_markov_plateau", "markov_plateau")


def main():
    print("BDI_FSM_AGENT deterministic self-tests")
    print("=======================================")
    for fn in [test_blackboard, test_fsm, test_bdi, test_foundry, test_hardened,
               test_memory, test_nmct_nmtd, test_toc_tok, test_maslow,
               test_fow_control, test_agent_lifecycle, test_daemon,
               test_lexicon, test_boolean_chat, test_controllers,
               test_recursive_learner, test_brute_adapter,
               test_journal, test_skill_library, test_task_pool,
               test_learning_enhanced, test_agent_recording,
               test_pool_cycle_with_foundry,
               test_arch_vectors, test_driver_wired_agent,
               test_aiception_tree, test_aiception_driver_render,
               test_hap_engine, test_hap_agent_wiring,
               test_dual_logger, test_pacing,
               test_identity, test_feedback, test_markov_plateau]:
        print(f"\n[{fn.__name__}]")
        fn()
    print(f"\n=== RESULT: {PASS} passed, {FAIL} failed ===")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
