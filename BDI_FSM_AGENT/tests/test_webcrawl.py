#!/usr/bin/env python3
"""Deterministic tests for WebCrawl self-training (fake fetcher, no net)."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bdi_fsm.webcrawl import CrawlTrainer, extract_text
from bdi_fsm.lexicon import Lexicon


def _fake_fetch(text):
    def _f(url):
        return text
    return _f


def test_extract_text_strips_markup():
    html = ('<html><script>var x=1;</script><style>a{}</style>'
            '<p>One sentence here.</p><p>Second sentence.</p></html>')
    t = extract_text(html)
    assert "One sentence" in t and "Second sentence" in t
    assert "var x" not in t and "a{}" not in t


def test_append_and_read_corpus():
    with tempfile.TemporaryDirectory() as td:
        ct = CrawlTrainer(td)
        ct.append_corpus("https://x.test/1", "This is a long enough piece of prose to keep. It has plenty of words and punctuation to satisfy the minimum length requirement for the corpus quality gate.")
        ct.append_corpus("https://x.test/2", "Another sufficiently long prose document with many words and full sentences so that it also passes the minimum length requirement without being dropped.")
        texts = ct.corpus_texts()
        assert len(texts) == 2
        assert "prose" in texts[0]


def test_short_text_rejected():
    with tempfile.TemporaryDirectory() as td:
        ct = CrawlTrainer(td)
        assert ct.append_corpus("u", "short") == 0  # 5 chars < 80 -> rejected
        assert ct.corpus_stats()["docs"] == 0


def test_crawl_learns_lexicon_and_corpus():
    with tempfile.TemporaryDirectory() as td:
        lx = Lexicon(os.path.join(td, "lexicon.json"))
        ct = CrawlTrainer(td, seeds=["https://a.test/1", "https://a.test/2"],
                          fetcher=_fake_fetch(
                              "Quantum entanglement is a fascinating phenomenon. "
                              "Entanglement correlates distant particles."))
        r = ct.crawl(max_pages=2, learn=lambda t, s: {"added": len(lx.mirror(t))})
        assert r["fetched"] == 2, r
        assert r["tokens_new"] > 0
        assert r["chars_learned"] > 0
        assert ct.corpus_stats()["docs"] == 2
        assert lx.is_known("quantum") or lx.is_known("entanglement")


def test_crawl_cooldown_skips():
    with tempfile.TemporaryDirectory() as td:
        ct = CrawlTrainer(td, seeds=["https://a.test/1"],
                          fetcher=_fake_fetch("A sufficiently long prose document with plenty of words and full sentences so it passes the minimum length gate for the corpus and counts as a fetched page when the trainer runs its paced crawl loop."))
        r1 = ct.crawl(max_pages=1, cooldown_s=10**9)
        r2 = ct.crawl(max_pages=1, cooldown_s=10**9)
        assert r1["fetched"] == 1
        assert r2["skipped_cooldown"] == 1
        assert r2["fetched"] == 0


def test_crawl_failure_recorded():
    def _boom(url):
        raise OSError("network down")
    with tempfile.TemporaryDirectory() as td:
        ct = CrawlTrainer(td, seeds=["https://a.test/1"], fetcher=_boom)
        r = ct.crawl(max_pages=1)
        assert r["fetched"] == 0
        assert len(r["failed"]) == 1
        assert "network down" in r["failed"][0]["error"]


def test_crawl_state_persists():
    with tempfile.TemporaryDirectory() as td:
        ct = CrawlTrainer(td, seeds=["https://a.test/1"],
                          fetcher=_fake_fetch("Long enough prose for the corpus please with plenty of words and punctuation to satisfy the minimum length requirement so the page counts as fetched and its state is recorded."))
        ct.crawl(max_pages=1, cooldown_s=10**9)
        ct2 = CrawlTrainer(td, seeds=["https://a.test/1"],
                           fetcher=_fake_fetch("Long enough prose for the corpus please with plenty of words and punctuation to satisfy the minimum length requirement so the page counts as fetched and its state is recorded."))
        r = ct2.crawl(max_pages=1, cooldown_s=10**9)
        assert r["skipped_cooldown"] == 1  # state survived reload


def test_corpus_stats():
    with tempfile.TemporaryDirectory() as td:
        ct = CrawlTrainer(td)
        ct.append_corpus("u", "This is a sufficiently long piece of prose with enough words and punctuation to pass the minimum length gate and be stored in the corpus file.")
        s = ct.corpus_stats()
        assert s["docs"] == 1 and s["chars"] > 0


ALL = [v for k, v in sorted(globals().items()) if k.startswith("test_")]


def run_all():
    passed = 0
    for t in ALL:
        t()
        passed += 1
        print(f"  ok {t.__name__}")
    print(f"\n{passed}/{len(ALL)} webcrawl tests passed")
    return passed


if __name__ == "__main__":
    raise SystemExit(0 if run_all() == len(ALL) else 1)
