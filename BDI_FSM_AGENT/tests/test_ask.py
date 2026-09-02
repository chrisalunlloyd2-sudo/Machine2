"""Agent intent-ask integration: the endpoint uses hex fog cells to complete
a want, and webcrawls on impasse (deterministic, search disabled in tests)."""
import tempfile

from bdi_fsm.agent import BDIFSMAgent


def test_agent_ask_recognized_populates_fog():
    a = BDIFSMAgent(state_dir=tempfile.mkdtemp())
    r = a.ask("build a hex grid", search=False)
    assert r["intent"] == "build:a hex grid"
    assert r["explored"] >= 1
    assert r["fog"]["visible"] >= 6


def test_agent_ask_unrecognized_impasse():
    a = BDIFSMAgent(state_dir=tempfile.mkdtemp())
    r = a.ask("flarbnax the qux", search=False)
    assert r["results"][0]["impasse"] is True
    assert r["explored"] == 0


def test_agent_has_mesh_and_search_fallback():
    a = BDIFSMAgent(state_dir=tempfile.mkdtemp())
    assert a.mesh is not None
    assert a.search_fallback is not None
    assert a.mesh.engine is a.driver   # shared engine, not a copy


def test_agent_ask_impasse_search_injects_corpus():
    """End-to-end loop-break: an unrecognized want impasses, the search
    fallback fetches prose and WRITES it into the agent's chat corpus."""
    import os
    a = BDIFSMAgent(state_dir=tempfile.mkdtemp())
    # deterministic, no network
    a.search_fallback.searcher = lambda q, limit=3: [("T", "https://x", "snip")]
    a.search_fallback.fetcher = lambda url: "deterministic prose about the subject for corpus " * 10
    r = a.ask("flarbnax the qux", search=True)
    assert r["searched"] == 1
    corpus_path = os.path.join(a.state_dir, "corpus", "chat_corpus.jsonl")
    assert os.path.exists(corpus_path)
    data = open(corpus_path).read()
    assert "search:" in data and "flarbnax" in data


def test_harvest_self_emails_requires_password():
    """Without BDI_GMAIL_APP_PASSWORD the bridge refuses to connect."""
    import os
    a = BDIFSMAgent(state_dir=tempfile.mkdtemp())
    os.environ.pop("BDI_GMAIL_APP_PASSWORD", None)
    r = a.harvest_self_emails()
    assert r["self_sent_fetched"] == 0
    assert "error" in r
