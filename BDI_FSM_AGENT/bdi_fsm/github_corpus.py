"""GITHUB CORPUS — self-train the Markov model from the operator's own repos.

Chris directive 2026-08-12:
"41 isn't enough for anything. We need multiple states per programming
language. It needs to self-train off my GitHub."

Strategy: shallow-clone each repo ONCE (fast, no per-file API rate limit),
then walk local files to extract three tiers of material, tagged by language
so the corpus forms one "state" (domain) per programming language:

  tier 1  README / docs prose   -> natural-language domain knowledge
  tier 2  source docstrings     -> what the code *means* (language-aware)
  tier 3  source comments       -> intent + decisions, token-rich

ADD-only, content-hash deduped, threaded (parallel clones), written to the
SAME chat_corpus.jsonl format corpus_seed.py uses — indistinguishable from
learned material. Pure stdlib + git. Zero LLM.
"""
import base64
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from .corpus_seed import clean_prose as _clean_prose, _hash as _chash

API = "https://api.github.com"
DOC_EXTS = {".md", ".txt", ".rst", ".markdown"}
CODE_EXTS = {".py", ".java", ".js", ".ts", ".c", ".cpp", ".h", ".sh",
             ".ps1", ".html", ".css", ".smali", ".kt"}
COMMENT_RE = re.compile(r"^\s*(#|//|/\*|\*|;|<!--|--)\s?(.*)$")
DOCSTRING_RE = re.compile(r'^\s*(r?"""|\'\'\')', re.M)


def _api(pat: str, path: str, timeout: int = 25) -> Optional[Any]:
    import urllib.request
    req = urllib.request.Request(
        API + path,
        headers={"Authorization": f"token {pat}",
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "bdi-fsm-github-corpus"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def list_repos(pat: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for page in range(1, 11):
        d = _api(pat, f"/user/repos?per_page=100&page={page}&sort=updated")
        if not isinstance(d, list) or not d:
            break
        out.extend(d)
        if len(d) < 100:
            break
    return out


def _clone(pat: str, owner: str, repo: str) -> Optional[str]:
    """Shallow-clone one repo into a fresh temp dir; return its path or None."""
    d = tempfile.mkdtemp(prefix=f"gh_{repo}_")
    url = f"https://x-access-token:{pat}@github.com/{owner}/{repo}.git"
    try:
        r = subprocess.run(
            ["git", "clone", "--depth", "1", "--quiet", url, d],
            capture_output=True, timeout=60)
        if r.returncode != 0:
            shutil.rmtree(d, ignore_errors=True)
            return None
        return d
    except Exception:
        shutil.rmtree(d, ignore_errors=True)
        return None


def _docstring_prose(text: str) -> List[str]:
    out = []
    for m in DOCSTRING_RE.finditer(text):
        i = m.end()
        end = text.find(m.group(1), i)
        if end == -1:
            end = min(len(text), i + 500)
        out.extend(_clean_prose(text[i:end]).splitlines())
    return [x for x in out if x.strip()]


def _comment_prose(text: str, cap: int = 60) -> List[str]:
    out = []
    for ln in text.splitlines():
        m = COMMENT_RE.match(ln)
        if m:
            s = m.group(2).strip()
            if 6 <= len(s) <= 200:
                out.append(s)
        if len(out) >= cap:
            break
    return out


def _walk_repo(clone_dir: str, repo: str, language: Optional[str]) -> List[str]:
    """Extract prose lines from a cloned repo, tagged by language."""
    lang = (language or "other").lower()
    lines: List[str] = []
    for root, _, files in os.walk(clone_dir):
        # skip vendored/heavy dirs
        if any(x in root for x in ("/.git", "/node_modules", "/.venv", "/venv",
                                   "/__pycache__", "/.gradle", "/target", "/build")):
            continue
        for fn in sorted(files):
            ext = os.path.splitext(fn)[1].lower()
            fp = os.path.join(root, fn)
            try:
                if os.path.getsize(fp) > 200_000:
                    continue
                text = open(fp, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            if ext in DOC_EXTS or fn.lower().startswith("readme"):
                lines.extend(_clean_prose(text).splitlines())
            elif ext in CODE_EXTS:
                lines.extend(_docstring_prose(text))
                lines.extend(_comment_prose(text))
            if len(lines) >= 900:
                return [x.strip() for x in lines if x.strip()][:900]
    return [x.strip() for x in lines if x.strip()][:900]


def seed(corpus_path: str, pat: str, owner: str,
         limit_repos: Optional[int] = None, dry_run: bool = False,
         workers: int = 8, on_progress=None) -> Dict[str, Any]:
    os.makedirs(os.path.dirname(corpus_path) or ".", exist_ok=True)
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

    repos = list_repos(pat)
    if limit_repos:
        repos = repos[:limit_repos]

    added = 0
    done = 0
    lock_ctx = []  # collect results; write single-threaded for simplicity

    def work(r):
        name = r.get("name")
        lang = r.get("language")
        clone = _clone(pat, owner, name) if name else None
        if not clone:
            return (name, lang, [])
        try:
            lines = _walk_repo(clone, name, lang)
        finally:
            shutil.rmtree(clone, ignore_errors=True)
        return (name, lang, lines)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(work, r): r for r in repos}
        for fut in as_completed(futs):
            name, lang, lines = fut.result()
            done += 1
            repo_added = 0
            for text in lines:
                h = _chash(text)
                if h in seen:
                    continue
                seen.add(h)
                repo_added += 1
                added += 1
                if not dry_run:
                    rec = {"h": h, "text": text[:800], "src": "github",
                           "repo": name, "lang": (lang or "other").lower(),
                           "ts": time.time()}
                    with open(corpus_path, "a") as f:
                        f.write(json.dumps(rec) + "\n")
            if on_progress:
                on_progress(done, len(repos), name, repo_added)

    return {"repos": done, "added": added, "corpus_total": len(seen)}

# LOCATIONS - this file lives in more than one place
#
#   live:  C:\Viper\projects\BDI_FSM_AGENT
#          -> C:\Users\viper\gan-otg-db\BDI_FSM_AGENT
#   mirror: J:\ViperVault\code\projects\BDI_FSM_AGENT
#   mirror: C:\Users\viper\gan-otg-db\BDI_FSM_AGENT
#
#   live detail (freshness, git coverage): docs\LOCATIONS.md
#   regenerate: python location_stamp.py apply
# end LOCATIONS
