"""SEARCH FALLBACK — when the gate impasses, search instead of looping.

On an intent-ask impasse (no candidate clears the Nash threshold / no vector
recommends an action), the mesh hands the cell here. We build a deterministic
search query from the intent's subject and consult an ORDERED chain of sources:

    1. LOCAL  — the agent's own memory: DefinitionStore (variable defs) and the
                chat corpus. Zero network, zero LLM, instant.
    2. REPOS  — the agent's own project manifests (own gists, and optionally
                own GitHub repos' READMEs). "Subjects pertaining to projects."
    3. WEB    — Wikipedia opensearch (stdlib urllib, zero LLM) as last resort.

Each source's prose is injected into the corpus + registered as evidence in the
cell's ledger. New material -> new candidates -> the gate gains a discriminator
-> the loop breaks. Sources are tried in order (earlier = cheaper + on-topic).

The searcher, fetcher, and repo-URL enumerator are injectable so tests stay
deterministic (no network). Pure stdlib.
"""
import json
import os
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

from .intent import Intent
from .cell import HexCell
from .webcrawl import DEFAULT_SEEDS, tokenize_query

UA = ("Mozilla/5.0 (compatible; BDI-FSM-AGENT/0.3; "
       "+https://github.com/chrisalunlloyd2-sudo/BDI_FSM_AGENT)")

# own gists (project manifests) — the "projects" half of the repos source
PROJECT_SEEDS = [u for u in DEFAULT_SEEDS if "gist" in u]


def _wikipedia_search(query: str, limit: int = 3) -> List[Tuple[str, str, str]]:
    """Deterministic Wikipedia opensearch -> [(title, url, snippet)]."""
    url = ("https://en.wikipedia.org/w/api.php?action=opensearch"
           f"&search={urllib.parse.quote(query)}&limit={limit}&format=json")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=12) as r:
        data = json.loads(r.read().decode("utf-8"))
    titles, descs, urls = data[1], data[2], data[3]
    return list(zip(titles, urls, descs))


def _extract_prose(url: str, timeout: int = 12) -> str:
    """Fetch a URL and strip it to prose (reuses webcrawl's extractor)."""
    from .webcrawl import fetch, extract_text
    return extract_text(fetch(url, timeout=timeout))


def _default_repo_urls(owner: str = "chrisalunlloyd2-sudo",
                       token: str = "", timeout: int = 8) -> List[str]:
    """Own gists + own repos' README raw URLs (project-specific sources)."""
    urls = list(PROJECT_SEEDS)
    if not owner:
        return urls
    headers = {"User-Agent": UA}
    if token:
        headers["Authorization"] = f"token {token}"
    try:
        req = urllib.request.Request(
            f"https://api.github.com/users/{owner}/repos?per_page=100",
            headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            repos = json.loads(r.read().decode("utf-8"))
    except Exception:
        return urls
    for repo in repos:
        if not isinstance(repo, dict):
            continue
        name = repo.get("name")
        if not name:
            continue
        branch = repo.get("default_branch", "main")
        urls.append(
            f"https://raw.githubusercontent.com/{owner}/{name}/{branch}/README.md")
    return urls


class SearchFallback:
    """Deterministic anti-loop: local -> repos -> web, inject corpus, re-evaluate."""

    def __init__(self, state_dir: str, trainer=None,
                 searcher: Optional[Callable] = None,
                 fetcher: Optional[Callable] = None,
                 repo_urls: Optional[Union[Sequence[str],
                                           Callable[[], Sequence[str]]]] = None,
                 list_repos: bool = False,
                 owner: str = "chrisalunlloyd2-sudo",
                 token: Optional[str] = None):
        self.state_dir = state_dir
        self.trainer = trainer          # CrawlTrainer (webcrawl) or None
        self.searcher = searcher or _wikipedia_search
        self.fetcher = fetcher or _extract_prose
        self.repo_urls = repo_urls      # None -> default (gists, +repos if list_repos)
        self.list_repos = list_repos
        self.owner = owner
        self.token = token or os.environ.get("GITHUB_TOKEN", "")

    def query_for(self, intent: Intent) -> str:
        return f"{intent.verb} {intent.object}".strip()

    # ---- source resolution ------------------------------------------------
    def _repo_candidates(self) -> List[str]:
        if self.repo_urls is None:
            if self.list_repos:
                return _default_repo_urls(self.owner, self.token)
            return list(PROJECT_SEEDS)
        if callable(self.repo_urls):
            return list(self.repo_urls())
        return list(self.repo_urls)

    def _local_hits(self, query: str) -> List[Tuple[str, str, str]]:
        """Local memory: definition store + corpus (no network)."""
        if self.trainer is None:
            return []
        tokens = tokenize_query(query)
        hits: List[Tuple[str, str, str]] = []
        for rec in self.trainer.defs.search_contains(tokens, limit=20):
            prose = f"{rec.get('name', '')} = {rec.get('value', '')}"
            if len(prose) >= 8:
                hits.append((f"def:{rec.get('name', '')}", "", prose))
        for doc in self.trainer.search_corpus(query, limit=5):
            prose = doc.get("text", "")
            if len(prose) >= 40:
                hits.append((f"corpus:{str(doc.get('source', ''))[:40]}", "",
                             prose))
        return hits

    def _repo_hits(self, query: str) -> List[Tuple[str, str, str]]:
        """Own project manifests / repos, filtered by token relevance."""
        tokens = tokenize_query(query)
        hits: List[Tuple[str, str, str]] = []
        for url in self._repo_candidates():
            try:
                text = self.fetcher(url)
            except Exception:
                continue
            if not text:
                continue
            low = text.lower()
            if tokens and not any(t in low for t in tokens):
                continue
            title = url.rstrip("/").split("/")[-1] if url else "project"
            hits.append((title, "", text))
        return hits

    def _chain(self, query: str):
        return [
            ("local", lambda: self._local_hits(query)),
            ("repos", lambda: self._repo_hits(query)),
            ("web", lambda: self.searcher(query)),
        ]

    # ---- injection --------------------------------------------------------
    def _inject(self, query: str, hits: List[Tuple[str, str, str]],
                cell: HexCell) -> int:
        injected = 0
        for title, url, snippet in hits:
            if url:
                try:
                    prose = self.fetcher(url)
                except Exception:
                    continue
            else:
                prose = snippet
            if len(prose) < 40:
                continue
            if self.trainer is not None:
                injected += self.trainer.append_corpus(f"search:{query}", prose)
            else:
                injected += 1
            if "subject_match" not in cell.ledger.scores:
                cell.register_hypothesis("subject_match", prior_prob=0.5)
            cell.observe("subject_match", p_h=0.7, p_not_h=0.3)
        return injected

    # ---- public -----------------------------------------------------------
    def search_on_impasse(self, intent: Intent, cell: HexCell) -> Dict[str, Any]:
        """Search the intent's subject across local -> repos -> web; inject prose
        + evidence; return a report. Preserves the flat 'hits'/'injected' keys
        and adds a per-source 'sources' breakdown."""
        query = self.query_for(intent)
        report: Dict[str, Any] = {"searched": query, "hits": 0,
                                  "injected": 0, "sources": {}}
        errors: List[str] = []
        for name, source in self._chain(query):
            try:
                hits = source()
            except Exception as exc:
                errors.append(f"{name}: {exc}")
                report["sources"][name] = {"error": str(exc)[:120]}
                continue
            injected = self._inject(query, hits, cell)
            report["sources"][name] = {"hits": len(hits), "injected": injected}
            report["hits"] += len(hits)
            report["injected"] += injected
            if injected > 0:
                break  # first source that actually injected wins (cheap + on-topic)
        if errors and report["injected"] == 0 and report["hits"] == 0:
            report["error"] = "; ".join(errors)[:160]
        return report

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
