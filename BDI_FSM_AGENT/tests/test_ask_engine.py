import os, tempfile, json
from bdi_fsm.ask_engine import (parse_query, score_repo, compare,
                                _topic_match)


def test_parse_best_topic():
    q = parse_query("which github will be best for robotic implementation of llm")
    assert q["intent"] == "best"
    assert "robotic" in q["topic"] and "llm" in q["topic"]


def test_parse_vs_candidates():
    q = parse_query("ask BDI_FSM_AGENT vs MasterLogs vs mind-palace about agent dev")
    assert q["intent"] == "compare"
    assert q["candidates"] == ["bdi_fsm_agent", "masterlogs", "mind-palace"]


def test_component_matching_not_substring():
    assert _topic_match("agent", "bdi_fsm_agent") is True
    assert _topic_match("agent", "manager") is False
    assert _topic_match("agent", "agents") is False


def test_score_name_match_wins():
    a = score_repo("my_agent", [], ["agent"], [], [], 0.0)
    b = score_repo("other", [], ["agent"], [], [], 0.0)
    assert a["ban"] > 0 and a["verdict"] == "RELEVANT"
    assert b["score"] == 0 and b["verdict"] == "below threshold"


def test_no_false_corpus_attribution():
    with tempfile.TemporaryDirectory() as td:
        a = os.path.join(td, "aaa_agent"); os.makedirs(a)
        open(os.path.join(a, "agent.py"), "w").write("x")
        b = os.path.join(td, "bbb"); os.makedirs(b)
        open(os.path.join(b, "readme.md"), "w").write("x")
        corpus = os.path.join(td, "c.jsonl")
        with open(corpus, "w") as f:
            f.write(json.dumps({"text": "aaa_agent language Python",
                                "src": "digest"}) + "\n")
        res = compare("which is best for agent", corpus,
                      searcher=lambda q, limit=3: [], mirrors=[a, b])
        byname = {r["repo"]: r for r in res["ranked"]}
        assert byname["bbb"]["corpus_hits"] == 0
        assert byname["aaa_agent"]["corpus_hits"] >= 1


def test_compare_ranking():
    with tempfile.TemporaryDirectory() as td:
        a = os.path.join(td, "my_agent"); os.makedirs(a)
        open(os.path.join(a, "agent.py"), "w").write("class Agent: pass")
        b = os.path.join(td, "other"); os.makedirs(b)
        open(os.path.join(b, "README.md"), "w").write("some notes")
        corpus = os.path.join(td, "c.jsonl")
        res = compare("which repo is best for agent", corpus,
                      searcher=lambda q, limit=3: [], mirrors=[a, b])
        assert res["ranked"][0]["repo"] == "my_agent"
        assert res["ranked"][0]["ban"] > 0
        assert "ANSWER" in res["tell"]


def test_web_searches_per_token_not_phrase():
    import tempfile
    queries = []
    def fake(q, limit=3):
        queries.append(q)
        return [(f"page:{q}", f"http://x/{q}", "snippet")]
    with tempfile.TemporaryDirectory() as td:
        compare("which repo is best for robotic implementation of llm",
                os.path.join(td, "c.jsonl"), searcher=fake,
                mirrors=["/root/BDI_FSM_AGENT"])
    # must query individual topic tokens, never the raw multi-word phrase
    assert queries == ["robotic", "implementation", "llm"]
    assert "robotic implementation llm" not in queries
