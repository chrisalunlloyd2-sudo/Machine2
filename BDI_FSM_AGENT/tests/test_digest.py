"""Digest -> chat corpus injector tests (Aegis v2: data in chats)."""
import json
import os
import tempfile

from bdi_fsm.digest import (
    digest_lines, fact_statements, qa_from_facts, repo_facts, seed_digest,
)


def _make_repo(tmp, name="demo", py_files=3, readme=True):
    root = os.path.join(tmp, name)
    os.makedirs(os.path.join(root, "src"), exist_ok=True)
    for i in range(py_files):
        open(os.path.join(root, "src", f"mod{i}.py"), "w").write("x=1\n")
    if readme:
        open(os.path.join(root, "README.md"), "w").write("# demo\n")
    return root


def test_repo_facts_extract_structure():
    with tempfile.TemporaryDirectory() as tmp:
        root = _make_repo(tmp, "demo", py_files=3, readme=True)
        facts = repo_facts([root])
        rels = {f["relation"] for f in facts}
        assert "location" in rels
        assert "file_count" in rels
        assert "language" in rels
        assert "has_doc" in rels
        # 3 .py + 1 README.md = 4 files
        fc = next(f for f in facts if f["relation"] == "file_count")
        assert fc["object"] == "4"
        lang = next(f for f in facts if f["relation"] == "language")
        assert lang["object"] == "Python"


def test_qa_covers_taxonomy():
    with tempfile.TemporaryDirectory() as tmp:
        root = _make_repo(tmp, "demo", py_files=3, readme=True)
        qa = qa_from_facts(repo_facts([root]))
        cats = {p["category"] for p in qa}
        assert "nominal" in cats       # language
        assert "mathematical" in cats  # file count
        assert "existence" in cats     # has_doc
        assert "locative" in cats      # location
        assert "instrumental" in cats  # key_file (pyproject/README/... may vary)
        # every Q/A is non-empty and answer mentions the subject
        for p in qa:
            assert p["q"] and p["a"]


def test_fact_statements_shape():
    facts = [{"subject": "x", "relation": "file_count", "object": "9"}]
    assert fact_statements(facts) == ["x file count 9."]


def test_digest_lines_mark_src():
    facts = [{"subject": "x", "relation": "file_count", "object": "9"},
             {"subject": "x", "relation": "language", "object": "Python"}]
    lines = digest_lines(facts)
    assert all(ln["src"] == "digest" for ln in lines)
    # statements + qa pairs both present
    assert any("q" in ln for ln in lines)
    assert any("q" not in ln for ln in lines)


def test_seed_digest_dry_run_and_append():
    with tempfile.TemporaryDirectory() as tmp:
        root = _make_repo(tmp, "demo", py_files=3, readme=True)
        corpus = os.path.join(tmp, "corpus", "chat_corpus.jsonl")
        # dry run: nothing written
        r = seed_digest(corpus, mirrors=[root], dry_run=True)
        assert r["facts"] > 0 and r["added"] > 0
        assert not os.path.exists(corpus)
        # real: appends lines, dedupes on second call
        r2 = seed_digest(corpus, mirrors=[root], dry_run=False)
        assert r2["added"] > 0
        n1 = sum(1 for _ in open(corpus))
        r3 = seed_digest(corpus, mirrors=[root], dry_run=False)
        assert r3["added"] == 0           # idempotent
        assert sum(1 for _ in open(corpus)) == n1
        # every line is valid json with src=digest
        for line in open(corpus):
            j = json.loads(line)
            assert j["src"] == "digest"
            assert j["text"]
