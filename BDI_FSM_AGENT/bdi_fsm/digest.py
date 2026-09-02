"""DIGEST -> CHAT CORPUS injector (Aegis v2 thread, Chris 2026-08-14).

"make sure data makes it in the chats too."

The chat corpus has prose (README/docs/emails) but not DIGESTED data — the
structured facts a content question needs an answer for. This module turns
structured facts about the fleet (repo name/location, file counts, dominant
language, key modules, docs) into:

  1. FACT STATEMENTS      "mind-palace language Python."
  2. QUESTION/ANSWER PAIRS "How many files does mind-palace have? -> it has 42."

...and seeds both into chat_corpus.jsonl with src="digest", so the Markov /
boolean / plateau trainer can actually answer content questions (nominal,
mathematical, locative, existence, instrumental, quantity, ...). The Q&A
templates are the first concrete realization of the token-map taxonomy:
questions over digested content.

Pure stdlib. Zero LLM. Deterministic. ADD-only (deduped by content hash).
"""

import hashlib
import json
import os
import time as _time
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from .corpus_seed import REPO_MIRRORS, _hash, MAX_LINE_CHARS

# directories never counted (repo plumbing)
_SKIP_DIRS = {".git", "node_modules", "__pycache__", "bin", "obj", "build",
              "dist", ".venv", "venv", "target", ".idea", ".vscode",
              ".pytest_cache", "*.egg-info"}

# files that identify a module/entrypoint (instrumental facts)
_KEY_FILES = {"server.py", "agent.py", "main.py", "app.py", "__main__.py",
              "main.go", "main.rs", "main.c", "Cargo.toml", "go.mod",
              "Makefile", "pyproject.toml", "setup.py"}

# extension -> human language name (nominal facts read better)
_LANG = {
    "py": "Python", "js": "JavaScript", "ts": "TypeScript", "go": "Go",
    "rs": "Rust", "c": "C", "h": "C", "cpp": "C++", "cc": "C++", "java": "Java",
    "rb": "Ruby", "pl": "Perl", "pm": "Perl", "xml": "XML", "md": "Markdown",
    "txt": "text", "json": "JSON", "sh": "shell", "html": "HTML", "css": "CSS",
    "yml": "YAML", "yaml": "YAML", "toml": "TOML", "bas": "BASIC", "vb": "BASIC",
    "lang": "Lang", "nix": "Nix",
}

# (category, question, answer) keyed by relation — the token-map taxonomy
QA_TEMPLATES: Dict[str, Tuple[str, str, str]] = {
    "language": (
        "nominal", "What language is {s} written in?", "{s} is written in {o}."),
    "extension_count": (
        "mathematical", "What is the most common file type in {s}?",
        "The most common file type in {s} is {o}."),
    "file_count": (
        "mathematical", "How many files does {s} have?", "{s} has {o} files."),
    "has_doc": (
        "existence", "Does {s} have documentation?", "Yes, {s} has a {o}."),
    "key_file": (
        "instrumental", "What is a key module of {s}?",
        "A key module of {s} is {o}."),
    "location": (
        "locative", "Where is {s} located?", "{s} is located at {o}."),
    "top_dir": (
        "nominal", "What directories make up {s}?",
        "The top directories of {s} include {o}."),
}


def _skip_dir(d: str) -> bool:
    if d in _SKIP_DIRS:
        return True
    return any(g.endswith("*") and d.endswith(g[:-1]) for g in _SKIP_DIRS)


def _discover_repos() -> List[str]:
    """Fallback when REPO_MIRRORS don't exist: find git repos near the agent.

    Always includes the agent's own repo root, then scans the parent dir
    (one level) for siblings containing .git. Deterministic (sorted)."""
    repos: List[str] = []
    agent_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if os.path.isdir(agent_root):
        repos.append(agent_root)
    parent = os.path.dirname(agent_root)
    if os.path.isdir(parent):
        try:
            for entry in sorted(os.listdir(parent)):
                p = os.path.join(parent, entry)
                if os.path.isdir(p) and os.path.isdir(os.path.join(p, ".git")):
                    if p not in repos:
                        repos.append(p)
        except OSError:
            pass
    return repos


def repo_facts(mirrors: Optional[List[str]] = None) -> List[Dict[str, str]]:
    """Extract structured facts about each local repo mirror.

    Returns {subject, relation, object} triples: location, file_count,
    language, extension_count, has_doc, key_file, top_dir.
    """
    facts: List[Dict[str, str]] = []
    if mirrors is None:
        mirrors = [r for r in REPO_MIRRORS if os.path.isdir(r)]
        if not mirrors:
            mirrors = _discover_repos()
    for root in mirrors:
        if not os.path.isdir(root):
            continue
        name = os.path.basename(root.rstrip("/")) or root
        facts.append({"subject": name, "relation": "location", "object": root})

        ext_counts: Dict[str, int] = {}
        file_count = 0
        key_files: List[str] = []
        has_readme = False
        top_dirs: List[str] = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if not _skip_dir(d)]
            if dirpath == root:
                top_dirs = [d for d in dirnames if not _skip_dir(d)]
            for fn in filenames:
                file_count += 1
                ext = os.path.splitext(fn)[1].lstrip(".").lower() or "noext"
                ext_counts[ext] = ext_counts.get(ext, 0) + 1
                low = fn.lower()
                if low in ("readme.md", "readme.txt", "readme"):
                    has_readme = True
                if fn in _KEY_FILES or low == "readme.md":
                    key_files.append(os.path.join(dirpath, fn))

        facts.append({"subject": name, "relation": "file_count",
                      "object": str(file_count)})
        if ext_counts:
            dominant = max(ext_counts, key=lambda e: ext_counts[e])
            facts.append({"subject": name, "relation": "language",
                          "object": _LANG.get(dominant, dominant)})
            facts.append({"subject": name, "relation": "extension_count",
                          "object": f"{dominant} ({ext_counts[dominant]} files)"})
        if has_readme:
            facts.append({"subject": name, "relation": "has_doc", "object": "README"})
        if top_dirs:
            facts.append({"subject": name, "relation": "top_dir",
                          "object": ", ".join(sorted(top_dirs)[:6])})
        for kf in sorted(key_files)[:4]:
            rel = os.path.relpath(kf, root)
            facts.append({"subject": name, "relation": "key_file", "object": rel})
    return facts


def fact_statements(facts: List[Dict[str, str]]) -> List[str]:
    """Render facts as natural-language declarative sentences."""
    out = []
    for f in facts:
        rel = f["relation"].replace("_", " ")
        out.append(f"{f['subject']} {rel} {f['object']}.")
    return out


def qa_from_facts(facts: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Render facts as question/answer pairs per the token-map taxonomy."""
    qa = []
    for f in facts:
        tpl = QA_TEMPLATES.get(f["relation"])
        if not tpl:
            continue
        category, q, a = tpl
        try:
            qa.append({
                "category": category,
                "q": q.format(s=f["subject"], o=f["object"]),
                "a": a.format(s=f["subject"], o=f["object"]),
            })
        except Exception:
            continue
    return qa


def digest_lines(facts: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """Flatten facts into corpus records (statements + Q&A), src='digest'."""
    lines: List[Dict[str, Any]] = []
    for stmt in fact_statements(facts):
        lines.append({"h": _hash(stmt), "text": stmt[:MAX_LINE_CHARS],
                      "src": "digest", "ts": _time.time()})
    for pair in qa_from_facts(facts):
        text = f"{pair['q']} {pair['a']}"
        lines.append({"h": _hash(text), "text": text[:MAX_LINE_CHARS],
                      "src": "digest", "q": pair["q"], "a": pair["a"],
                      "category": pair["category"], "ts": _time.time()})
    return lines


def seed_digest(corpus_path: str, mirrors: Optional[List[str]] = None,
                dry_run: bool = False) -> Dict[str, Any]:
    """Extract repo facts and inject statements + Q&A into the chat corpus.

    ADD-only: deduped by content hash against existing lines. Returns counts
    and a category histogram (the token-map distribution).
    """
    facts = repo_facts(mirrors)
    lines = digest_lines(facts)

    seen = set()
    if os.path.exists(corpus_path):
        try:
            for line in open(corpus_path):
                try:
                    seen.add(json.loads(line).get("h", ""))
                except Exception:
                    continue
        except Exception:
            pass

    added = 0
    if not dry_run:
        os.makedirs(os.path.dirname(corpus_path) or ".", exist_ok=True)
        with open(corpus_path, "a") as f:
            for rec in lines:
                if rec["h"] in seen:
                    continue
                seen.add(rec["h"])
                f.write(json.dumps(rec) + "\n")
                added += 1
    else:
        added = sum(1 for rec in lines if rec["h"] not in seen)

    cats = Counter(p["category"] for p in qa_from_facts(facts))
    return {"facts": len(facts), "statements": len(fact_statements(facts)),
            "qa_pairs": sum(cats.values()), "added": added,
            "categories": dict(cats), "corpus_total": len(seen)}
