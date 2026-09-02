"""Search fallback: deterministic anti-loop on impasse (no network in tests).

Chain order: LOCAL (defs + corpus) -> REPOS (own projects) -> WEB (Wikipedia).
A source that actually injects prose stops the chain (cheap + on-topic wins).
"""
import tempfile

from bdi_fsm.cell import HexCell
from bdi_fsm.intent import parse_intent
from bdi_fsm.search_fallback import SearchFallback
from bdi_fsm.webcrawl import CrawlTrainer


def test_query_for_intent():
    sf = SearchFallback("/tmp/sf_test")
    i = parse_intent("build a hex grid")
    assert sf.query_for(i) == "build a hex grid"


def test_search_on_impasse_injects_evidence_and_corpus():
    sf = SearchFallback(
        "/tmp/sf_test",
        searcher=lambda q, limit=3: [("T", "https://x", "snippet")],
        fetcher=lambda url: "This is a sufficiently long prose snippet about the subject " * 3,
        repo_urls=[],
    )
    cell = HexCell(0, 0)
    i = parse_intent("build a hex grid")
    report = sf.search_on_impasse(i, cell)
    assert report["hits"] == 1
    assert report["injected"] == 1
    # the cell's ledger now carries lifted evidence for subject_match
    assert "subject_match" in cell.ledger.scores
    assert cell.ledger.scores["subject_match"] > 0.0


def test_search_on_impasse_survives_fetch_failure():
    sf = SearchFallback(
        "/tmp/sf_test",
        searcher=lambda q, limit=3: [("T", "https://x", "snippet")],
        fetcher=lambda url: (_ for _ in ()).throw(RuntimeError("down")),
        repo_urls=[],
    )
    cell = HexCell(0, 0)
    report = sf.search_on_impasse(parse_intent("build a hex grid"), cell)
    assert report["injected"] == 0


def test_search_on_impasse_survives_searcher_failure():
    sf = SearchFallback(
        "/tmp/sf_test",
        searcher=lambda q, limit=3: (_ for _ in ()).throw(RuntimeError("down")),
        fetcher=lambda url: "offline fetcher returns prose " * 3,
        repo_urls=[],
    )
    cell = HexCell(0, 0)
    report = sf.search_on_impasse(parse_intent("build a hex grid"), cell)
    assert report.get("error")
    assert report["injected"] == 0


# ---- chain order ----------------------------------------------------------

def test_local_source_hit_skips_web():
    """A corpus hit in local memory injects and stops the chain — no web call."""
    tmp = tempfile.mkdtemp()
    trainer = CrawlTrainer(tmp)
    trainer.append_corpus("seed", "the hex grid indexes fog of war cells for routing " * 3)
    called = {"web": 0}

    def _searcher(q, limit=3):
        called["web"] += 1
        raise RuntimeError("web must not be reached")

    sf = SearchFallback(tmp, trainer=trainer, repo_urls=[], searcher=_searcher)
    cell = HexCell(0, 0)
    report = sf.search_on_impasse(parse_intent("build a hex grid"), cell)
    assert report["injected"] > 0
    assert "web" not in report["sources"]
    assert called["web"] == 0


def test_repo_source_hit_skips_web():
    """A project-manifest hit injects and stops the chain — no web call."""
    sf = SearchFallback(
        "/tmp/sf_test",
        repo_urls=["https://example/grid.md"],
        fetcher=lambda url: "hex grid implementation notes and routing " * 5,
        searcher=lambda q, limit=3: (_ for _ in ()).throw(RuntimeError("web must not be reached")),
    )
    cell = HexCell(0, 0)
    report = sf.search_on_impasse(parse_intent("build a hex grid"), cell)
    assert report["injected"] > 0
    assert "web" not in report["sources"]
    assert report["sources"]["repos"]["hits"] == 1


def test_all_empty_falls_to_web():
    """Local + repos both empty -> Wikipedia is the last-resort loop-break."""
    sf = SearchFallback(
        "/tmp/sf_test",
        repo_urls=[],
        searcher=lambda q, limit=3: [("Hex grid", "https://x", "snippet")],
        fetcher=lambda url: "wikipedia prose about the hex grid subject " * 5,
    )
    cell = HexCell(0, 0)
    report = sf.search_on_impasse(parse_intent("build a hex grid"), cell)
    assert report["injected"] > 0
    assert report["sources"]["web"]["hits"] == 1


def test_repo_source_without_token_match_falls_through():
    """Repos source returns nothing relevant -> chain continues to web."""
    sf = SearchFallback(
        "/tmp/sf_test",
        repo_urls=["https://example/unrelated.md"],
        fetcher=lambda url: "completely unrelated prose about something else " * 5,
        searcher=lambda q, limit=3: [("T", "https://x", "snippet")],
    )
    # fetcher is shared: repos call returns irrelevant prose, web call returns
    # the same prose (which IS >= 40 chars) -> web injects.
    cell = HexCell(0, 0)
    report = sf.search_on_impasse(parse_intent("build a hex grid"), cell)
    assert report["injected"] > 0
    assert report["sources"]["repos"]["hits"] == 0
    assert report["sources"]["web"]["hits"] == 1


# ---- new query methods ----------------------------------------------------

def test_definition_store_search_contains():
    tmp = tempfile.mkdtemp()
    trainer = CrawlTrainer(tmp)
    trainer.defs.append("seed", [
        {"name": "hex_grid_size", "value": "6", "kind": "assignment", "lang": "text"},
        {"name": "nash_threshold", "value": "20", "kind": "assignment", "lang": "text"},
    ])
    hits = trainer.defs.search_contains(["hex", "grid"])
    names = {h["name"] for h in hits}
    assert "hex_grid_size" in names
    assert "nash_threshold" not in names


def test_search_corpus_token_match():
    tmp = tempfile.mkdtemp()
    trainer = CrawlTrainer(tmp)
    trainer.append_corpus("a", "the fog of war cells reveal neighbours on reveal " * 3)
    trainer.append_corpus("b", "unrelated financial repayment plan text " * 3)
    hits = trainer.search_corpus("fog of war", limit=10)
    assert len(hits) == 1
    assert hits[0]["source"] == "a"


def test_search_corpus_stopwords_excluded():
    """'the' must not be a relevance token (would match everything)."""
    tmp = tempfile.mkdtemp()
    trainer = CrawlTrainer(tmp)
    trainer.append_corpus("a", "unrelated prose " * 10)
    assert trainer.search_corpus("the") == []
