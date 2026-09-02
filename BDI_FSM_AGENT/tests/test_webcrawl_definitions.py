"""Variable-definition injector tests — the 'data' half of webcrawl."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bdi_fsm.webcrawl import (CrawlTrainer, DefinitionStore, extract_definitions)


def test_extract_assignment():
    d = extract_definitions("x = 42\nname = alice\nlong = " + "a" * 200)
    names = {r["name"]: r for r in d}
    assert "x" in names and names["x"]["value"] == "42"
    assert "name" in names and names["name"]["value"] == "alice"
    assert names["x"]["kind"] == "assignment"
    # over-long value (>160) is dropped
    assert "long" not in names


def test_extract_keyvalue():
    d = extract_definitions("port: 8080\nhost: localhost\nempty:")
    names = {r["name"]: r["value"] for r in d}
    assert names.get("port") == "8080"
    assert names.get("host") == "localhost"
    assert "empty" not in names


def test_extract_function():
    d = extract_definitions("def foo(x):\nfunction bar() {}\nfn baz(a)")
    kinds = {r["name"]: r["kind"] for r in d}
    assert kinds == {"foo": "function", "bar": "function", "baz": "function"}


def test_definition_store_dedup_and_search():
    with tempfile.TemporaryDirectory() as td:
        st = DefinitionStore(os.path.join(td, "defs.jsonl"))
        n1 = st.append("u1", [{"name": "x", "value": "1", "kind": "assignment", "lang": "text"}])
        n2 = st.append("u2", [{"name": "x", "value": "1", "kind": "assignment", "lang": "text"}])  # dup
        n3 = st.append("u3", [{"name": "y", "value": "2", "kind": "keyvalue", "lang": "text"}])
        assert n1 == 1 and n2 == 0 and n3 == 1
        assert st.stats()["definitions"] == 2
        hits = st.search(name="x")
        assert len(hits) == 1 and hits[0]["value"] == "1"
        kv = st.search(kind="keyvalue")
        assert len(kv) == 1 and kv[0]["name"] == "y"


def test_crawl_stores_definitions():
    text = ("A prose paragraph long enough to keep with plenty of words.\n"
            "theme = dark\n"
            "max_retries = 5\n"
            "def handler(event):\n"
            "some more prose to reach minimum length for the corpus gate.")
    def fake(url):
        return text
    with tempfile.TemporaryDirectory() as td:
        ct = CrawlTrainer(td, seeds=["https://a.test/1"], fetcher=fake)
        r = ct.crawl(max_pages=1)
        assert r["definitions_new"] >= 3  # theme, max_retries, handler
        hits = ct.defs.search(name="max_retries")
        assert hits and hits[0]["value"] == "5"
        assert any(h["kind"] == "function" for h in ct.defs.search())
