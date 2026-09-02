"""CORPUS SEED — self-emails + repo mirrors -> chat corpus + lexicon.

Chris roadmap item: "Corpus seed from self-emails + repo mirrors".

Seeds the agent's language model from two rich, free sources:
  1. SELF-EMAILS  — the sovereign memory stream (chrisalunlloyd2@gmail.com
     self-sent summaries, project status, doctrine). Reads the SOV KV store
     directly (self_email.<uid> bodies) — no IMAP needed, already local.
  2. REPO MIRRORS — the local fleet clones (SIMS1337, karoo_gp, mind-palace,
     MatrixWinCE, pipe_ops, hexgame...). Extracts README/docs/prose, not
     code noise.

Output: chat_corpus.jsonl lines (prose) + verb_flags lexicon tokens —
the SAME format triple_loop's webcrawl/chat channels write, so the seed is
indistinguishable from learned material. Paced + deduped by content hash.

Pure stdlib. Zero LLM. ADD-only (never deletes corpus lines).
"""

import hashlib
import json
import os
import re
from typing import Dict, List, Optional, Tuple

SOV_KV = "/root/sov/kv/data.json"
REPO_MIRRORS = [
    "/root/scan_tmp/SIMS1337",
    "/root/scan_tmp/karoo_gp",
    "/root/scan_tmp/mind-palace",
    "/root/MatrixWinCE",
    "/root/pipe_ops",
    "/root/hexgame",
    "/root/scan_tmp/BDI_FSM_AGENT",
]
DOC_GLOBS = ["README*", "*.md", "docs/*.md", "docs/*.txt", "*.txt"]
MIN_CHARS = 20
MAX_LINE_CHARS = 800


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def clean_prose(text: str) -> str:
    """Strip markdown/code cruft -> plain prose lines.

    Tracks fenced code blocks (``` ... ```) so bare lines inside a fence
    are never mistaken for prose. Also skips headings, blockquotes, tables,
    checklist items, comments, and code-ish lines (braces, parens, def,
    import, $, backticks, trailing indentation).
    """
    lines = []
    in_fence = False
    for ln in text.splitlines():
        s = ln.strip()
        if not s:
            continue
        if s.startswith("```"):
            in_fence = not in_fence  # toggle fence state
            continue
        if in_fence:
            continue  # inside a code fence: never prose
        if s.startswith(("#", ">", "|", "- [", "* [", "//", "--", "<!-", "=" * 3)):
            continue
        # skip code-ish lines
        if re.search(r"[\{\}\[\]\(\)=;]|\bdef \b|\bimport \b|\$|`", s):
            continue
        s = re.sub(r"[*_`#>]", "", s)
        s = re.sub(r"\s+", " ", s).strip()
        if MIN_CHARS <= len(s) <= MAX_LINE_CHARS:
            lines.append(s)
    return "\n".join(lines)


def seed_from_self_emails(kv_path: str = SOV_KV, limit: int = 60) -> List[str]:
    """Pull self-email bodies from the SOV KV store."""
    out = []
    try:
        data = json.load(open(kv_path))
        kvs = data.get("kv", data) if isinstance(data, dict) else {}
        bodies = []
        for k, v in kvs.items():
            if isinstance(k, str) and k.startswith("self_email."):
                b = v.get("body") if isinstance(v, dict) else str(v)
                if b:
                    bodies.append(b)
        for b in bodies[:limit]:
            p = clean_prose(b)
            if p:
                out.append(p)
    except Exception:
        pass
    return out


def seed_from_repos(mirrors: Optional[List[str]] = None) -> List[str]:
    """Extract prose from local repo mirrors (README + docs)."""
    out = []
    for root in mirrors or REPO_MIRRORS:
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames
                           if d not in (".git", "node_modules", "__pycache__",
                                        "bin", "obj", "build", "dist")]
            for fn in filenames:
                if not any(fn.startswith(g.rstrip("*").replace("*", ""))
                           or fn.endswith(g.lstrip("*"))
                           or fn == g for g in ["README.md", "README.txt"]):
                    if not fn.endswith(".md"):
                        continue
                fp = os.path.join(dirpath, fn)
                if os.path.getsize(fp) > 200_000:
                    continue
                try:
                    txt = open(fp, encoding="utf-8", errors="replace").read()
                except Exception:
                    continue
                p = clean_prose(txt)
                if p:
                    out.append(p)
    return out


def seed(corpus_path: str, kv_path: str = SOV_KV,
         mirrors: Optional[List[str]] = None,
         dry_run: bool = False) -> Dict[str, int]:
    """Main: seed corpus from emails + repos, deduped, ADD-only."""
    os.makedirs(os.path.dirname(corpus_path) or ".", exist_ok=True)
    seen = set()
    if os.path.exists(corpus_path):
        try:
            for line in open(corpus_path):
                try:
                    j = json.loads(line)
                    seen.add(j.get("h", ""))
                except Exception:
                    continue
        except Exception:
            pass

    added = 0
    sources = seed_from_self_emails(kv_path) + seed_from_repos(mirrors)
    for prose in sources:
        h = _hash(prose)
        if h in seen:
            continue
        seen.add(h)
        added += 1
        if not dry_run:
            rec = {"h": h, "text": prose[:MAX_LINE_CHARS],
                   "src": "seed", "ts": __import__("time").time()}
            with open(corpus_path, "a") as f:
                f.write(json.dumps(rec) + "\n")
    return {"candidates": len(sources), "added": added,
            "corpus_total": len(seen)}
