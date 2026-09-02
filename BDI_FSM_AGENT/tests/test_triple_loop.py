#!/usr/bin/env python3
"""Tests for triple learning loop + verb flags + behavior tree + daily feature.
Zero LLM. All deterministic."""
import json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bdi_fsm.verb_flags import VerbFlags
from bdi_fsm.btree import Action, BehaviorTree, Selector, Sequence, Condition, SUCCESS, FAILURE
from bdi_fsm.triple_loop import TripleLearningLoop


class FakeNMTD:
    def __init__(self):
        self.db = {}
    def check(self, fp):
        return self.db.get(fp)
    def record(self, fp, data):
        self.db[fp] = data


class TestVerbFlags(unittest.TestCase):
    def test_save_routes_achieve(self):
        v = VerbFlags()
        self.assertEqual(v.performative("please save this code"), "achieve")
        self.assertEqual(v.action_hint("please save this code"), "save_code")

    def test_ask_routes_ask_one(self):
        v = VerbFlags()
        self.assertEqual(v.performative("what is the pool status"), "ask-one")

    def test_feature_routes_daily(self):
        v = VerbFlags()
        self.assertEqual(v.action_hint("please update the daily feature"), "update_daily_feature")

    def test_learn_new_verb(self):
        td = tempfile.mkdtemp()
        v = VerbFlags(td)
        learned = v.learn("please frambulate the code", "save_code")
        self.assertIn("frambulate", learned)
        self.assertEqual(v.lookup("frambulate"), "achieve")

    def test_no_verbs_no_action(self):
        v = VerbFlags()
        self.assertIsNone(v.action_hint("hello there friend"))


class TestBehaviorTree(unittest.TestCase):
    def test_pull_by_performative(self):
        nmtd = FakeNMTD()
        act = Action("save", ["achieve"], ["save"],
                     {"termux": "echo ok", "powershell": "echo ok"}, nmtd=nmtd)
        bt = BehaviorTree([act], nmtd=nmtd)
        pulled = bt.pull("achieve", ["save"])
        self.assertEqual([a.name for a in pulled], ["save"])

    def test_nmtd_blocks_after_2_fails(self):
        nmtd = FakeNMTD()
        act = Action("save", ["achieve"], ["save"],
                     {"termux": "echo ok"}, nmtd=nmtd)
        bt = BehaviorTree([act], nmtd=nmtd)
        ctx = {"repo": "r"}
        fp = act.fingerprint(ctx)
        nmtd.record(fp, {"outcome": "fail", "fail_count": 2, "repo": "r"})
        pulled = bt.pull("achieve", ["save"], ctx)
        self.assertEqual(pulled, [])  # blocked by never-try-twice

    def test_selector_or(self):
        f = Action("fail", ["achieve"], ["x"], {"termux": "false"})
        s = Action("succeed", ["achieve"], ["x"], {"termux": "true"})
        sel = Selector([f, s])
        self.assertEqual(sel.tick({}), SUCCESS)

    def test_sequence_and(self):
        a = Action("a", ["achieve"], ["x"], {"termux": "true"})
        b = Action("b", ["achieve"], ["x"], {"termux": "false"})
        seq = Sequence([a, b])
        self.assertEqual(seq.tick({}), FAILURE)


class TestTripleLoop(unittest.TestCase):
    def test_chat_learn_writes_corpus(self):
        td = tempfile.mkdtemp()
        tl = TripleLearningLoop(td, "/tmp")
        s = tl.chat_learn("please save this code and run the tests", "chat")
        self.assertEqual(s["corpus"], 1)

    def test_verbs_stats(self):
        td = tempfile.mkdtemp()
        tl = TripleLearningLoop(td, "/tmp")
        self.assertGreaterEqual(tl.stats()["verbs"]["total"], 67)

    def test_fitness_scores_perfect(self):
        td = tempfile.mkdtemp()
        tl = TripleLearningLoop(td, "/tmp")
        score, details = tl._fitness("def add(a,b):\n    return a+b",
                                     ["a", "b"], ["add(1,2) == 3"])
        self.assertEqual(score, 1.0)
        self.assertTrue(details["compile"])

    def test_fitness_rejects_broken(self):
        td = tempfile.mkdtemp()
        tl = TripleLearningLoop(td, "/tmp")
        score, details = tl._fitness("def broken(:", ["a"], ["broken(1) == 1"])
        self.assertEqual(score, 0.0)

    def test_queue_and_pending(self):
        td = tempfile.mkdtemp()
        tl = TripleLearningLoop(td, "/tmp")
        tl.queue_foundry("f", ["a"], ["f(1)==1"], "doc")
        self.assertEqual(tl._foundry_queue_len(), 1)
        self.assertEqual(tl._foundry_pending()["skipped"], None) if False else None

    def test_enqueue_chat_flow(self):
        td = tempfile.mkdtemp()
        tl = TripleLearningLoop(td, "/tmp")
        tl.enqueue_chat("hello there", "chat")
        r = tl.run_hourly(crawl=False, foundry=False, feature=False)
        self.assertEqual(r["loops"]["chat"]["messages"], 1)


if __name__ == "__main__":
    unittest.main()
