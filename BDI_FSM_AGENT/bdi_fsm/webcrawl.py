"""WEBCRAWL SELF-TRAINING — populate the chat corpus + lexicon from the web.

The bot feeds itself: crawl deterministic text sources (own gists, project
docs, vocabulary pages), extract prose, and learn into BOTH:

1. the LEXICON (syntax): every new token is mirror-learned + morphology-
   expanded (the subjective-English map grows),
2. the CHAT CORPUS (semantics): the text is appended to a JSONL store that
   MarkovChat.build() consumes — so chat_long() gets real prose to stitch
   and entropy-stopping gets real distributions to measure.

Paced + polite: max pages per run, max bytes per page, per-URL crawl-state
dedup (never re-crawl the same page every heartbeat — rotate on a cooldown).
Pure stdlib (urllib + html.parser), deterministic, zero LLM.

NOTE: this is DATA INGESTION, not inference — the no-cloud-LLM hard rule
applies to model calls only. The web is the teacher, the lexicon is the
notebook, the Markov table is the memory.
"""

import html
import json
import os
import re
import time
import urllib.request
from html.parser import HTMLParser
from typing import Any, Callable, Dict, List, Optional, Sequence

UA = "BDI-FSM-AGENT/0.1 (deterministic self-training; polite crawler)"
MAX_BYTES = 250_000          # per page
DEFAULT_COOLDOWN_S = 86_400  # re-crawl a URL at most 1x/day

# default seed manifest: own canonical gists + vocabulary/prose sources
DEFAULT_SEEDS = [
    "https://gist.githubusercontent.com/chrisalunlloyd2-sudo/ed5993a2c8846429f5e9ef2e12b160f1/raw/ONBOARDING.md",
    "https://gist.githubusercontent.com/chrisalunlloyd2-sudo/2f15e314af3246c829b166aa6f5b2d4c/raw/HARVEST_MANIFEST.md",
    "https://en.wikipedia.org/wiki/Shannon_entropy",
    "https://en.wikipedia.org/wiki/Knowledge_Query_and_Manipulation_Language",
    "https://en.wikipedia.org/wiki/Belief%E2%80%93desire%E2%80%93intention_software_model",
    "https://en.wikipedia.org/wiki/Subsumption_architecture",
]


class _TextExtractor(HTMLParser):
    """Minimal HTML -> prose extractor (stdlib, no deps)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: List[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg"):
            self._skip += 1
        if tag in ("p", "div", "br", "li", "h1", "h2", "h3", "pre", "tr"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg"):
            self._skip = max(0, self._skip - 1)
        if tag in ("p", "div", "li", "h1", "h2", "h3", "pre"):
            self.parts.append("\n")

    def handle_data(self, data):
        if self._skip == 0:
            self.parts.append(data)

    def text(self) -> str:
        t = " ".join(self.parts)
        t = re.sub(r"\s+", " ", t)
        return t.strip()


def extract_text(html_text: str) -> str:
    p = _TextExtractor()
    try:
        p.feed(html_text)
    except Exception:
        return ""
    t = p.text()
    # collapse fragments to sentence-ish chunks
    t = re.sub(r"(\S)\s*\n\s*(\S)", r"\1 \2", t)
    return t


def fetch(url: str, timeout: int = 12) -> str:
    """Fetch a URL and return its text (html stripped). Raises on failure."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raw = raw[:MAX_BYTES]
    try:
        decoded = raw.decode("utf-8", errors="replace")
    except Exception:
        decoded = raw.decode("latin-1", errors="replace")
    return extract_text(decoded)


_ASSIGN_RE = re.compile(r'(?m)^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+?)\s*$')
_KV_RE = re.compile(r'(?m)^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.+?)\s*$')
_FN_RE = re.compile(r'(?m)^\s*(?:def|function|fn|func)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(')

# common words excluded from relevance matching (too generic to discriminate)
_STOP = {
    "the", "and", "for", "with", "into", "from", "that", "this", "what",
    "how", "why", "when", "will", "would", "could", "should", "about",
    "have", "has", "had", "not", "are", "was", "were", "been", "your",
    "our", "their", "its", "his", "her", "you", "they", "them", "does",
    "get", "got", "use", "using", "via", "per", "can", "may", "one", "two",
}


def tokenize_query(query: str) -> List[str]:
    """Lowercase word tokens (len>=3, stopword-free) for relevance matching."""
    return [t for t in re.split(r"\W+", query.lower())
            if len(t) >= 3 and t not in _STOP]


def extract_definitions(text: str, lang: str = "text") -> List[Dict[str, str]]:
    """Extract name=value, key:value and def/function signatures from scraped text.

    This is the "data" half of "data + variable definition search": prose goes
    to the Markov corpus, but STRUCTURED definitions go to a queryable store the
    rotor codecs / brute foundry enumerate over when a variable is unknown.
    Language-agnostic (scraped pages mix prose, code blocks, config, markdown).
    """
    defs: List[Dict[str, str]] = []
    seen = set()
    for m in _ASSIGN_RE.finditer(text):
        name, val = m.group(1), m.group(2).strip()
        if not val or len(val) > 160:
            continue
        if (name, val, "=") in seen:
            continue
        seen.add((name, val, "="))
        defs.append({"name": name, "value": val, "kind": "assignment", "lang": lang})
    for m in _KV_RE.finditer(text):
        name, val = m.group(1), m.group(2).strip()
        if not val or val in ("{", "[", "null", "true", "false", "None"):
            continue
        if (name, val, ":") in seen:
            continue
        seen.add((name, val, ":"))
        defs.append({"name": name, "value": val, "kind": "keyvalue", "lang": lang})
    for m in _FN_RE.finditer(text):
        name = m.group(1)
        if ("fn", name) in seen:
            continue
        seen.add(("fn", name))
        defs.append({"name": name, "value": "<callable>", "kind": "function", "lang": lang})
    return defs


class DefinitionStore:
    """Queryable variable-definition store (JSONL, dedup by name+value).

    Scraped definitions land here and are queried by name/kind. This is the
    ingest side of the rotor-codec search: webcrawl fills the store, the rotor
    enumerates candidates against it.
    """

    def __init__(self, path: str):
        self.path = path
        self._seen = self._load_keys()

    def _load_keys(self) -> set:
        if not os.path.exists(self.path):
            return set()
        keys = set()
        for line in open(self.path):
            try:
                rec = json.loads(line)
                keys.add((rec.get("name"), rec.get("value")))
            except (json.JSONDecodeError, AttributeError):
                continue
        return keys

    def append(self, source: str, defs: List[Dict[str, str]]) -> int:
        added = 0
        with open(self.path, "a") as f:
            for d in defs:
                key = (d["name"], d["value"])
                if key in self._seen:
                    continue
                self._seen.add(key)
                rec = {"name": d["name"], "value": d["value"],
                       "kind": d.get("kind", "assignment"),
                       "lang": d.get("lang", "text"), "source": source,
                       "ts": time.time()}
                f.write(json.dumps(rec) + "\n")
                added += 1
        return added

    def search(self, name: Optional[str] = None, kind: Optional[str] = None,
               limit: int = 50) -> List[Dict[str, Any]]:
        out = []
        if not os.path.exists(self.path):
            return out
        for line in open(self.path):
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if name is not None and rec.get("name") != name:
                continue
            if kind is not None and rec.get("kind") != kind:
                continue
            out.append(rec)
        return out[-limit:]

    def search_contains(self, tokens, limit: int = 50) -> List[Dict[str, Any]]:
        """Return records whose name contains any token (case-insensitive).

        Used by the search fallback's LOCAL source: when a subject impasses,
        the agent looks up any variable/function whose name mentions the
        subject tokens before ever touching the network.
        """
        out: List[Dict[str, Any]] = []
        if not tokens or not os.path.exists(self.path):
            return out
        low = [t.lower() for t in tokens]
        for line in open(self.path):
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            name = (rec.get("name") or "").lower()
            if any(t in name for t in low):
                out.append(rec)
        return out[-limit:]

    def stats(self) -> Dict[str, Any]:
        n = 0
        if os.path.exists(self.path):
            n = sum(1 for _ in open(self.path))
        return {"definitions": n, "path": self.path}


class CrawlTrainer:
    """Paced webcrawl -> lexicon + chat corpus. Deterministic, stdlib-only."""

    def __init__(self, state_dir: str, seeds: Optional[Sequence[str]] = None,
                 fetcher: Optional[Callable[[str], str]] = None):
        self.state_dir = state_dir
        os.makedirs(os.path.join(state_dir, "corpus"), exist_ok=True)
        self.corpus_path = os.path.join(state_dir, "corpus", "chat_corpus.jsonl")
        self.state_path = os.path.join(state_dir, "corpus", "crawl_state.json")
        self.defs_path = os.path.join(state_dir, "corpus", "definitions.jsonl")
        self.defs = DefinitionStore(self.defs_path)
        self.seeds = list(seeds or DEFAULT_SEEDS)
        self._fetch = fetcher or fetch          # injectable for tests
        self._state: Dict[str, float] = {}
        if os.path.exists(self.state_path):
            try:
                self._state = json.load(open(self.state_path, encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._state = {}

    def _save_state(self) -> None:
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(self._state, f, indent=1)

    def append_corpus(self, source: str, text: str) -> int:
        """Append one prose document to the chat corpus. Returns chars."""
        text = text.strip()
        if len(text) < 80:
            return 0
        rec = {"source": source, "ts": time.time(), "chars": len(text), "text": text}
        # utf-8 explicitly: the corpus is prose, prose has em dashes and quotes, and the default
        # codec here is cp1252 -- which turns the first interesting document into a crash.
        with open(self.corpus_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        return len(text)

    def corpus_texts(self, limit: Optional[int] = None) -> List[str]:
        """Read back corpus documents for MarkovChat.build()."""
        texts = []
        if not os.path.exists(self.corpus_path):
            return texts
        for line in open(self.corpus_path, encoding="utf-8", errors="replace"):
            line = line.strip()
            if not line:
                continue
            try:
                texts.append(json.loads(line).get("text", ""))
            except json.JSONDecodeError:
                continue
        return texts[-limit:] if limit else texts

    def search_corpus(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Return corpus documents whose text contains any query token.

        The search fallback's LOCAL source: match the subject against prose the
        agent has already crawled/learned (its own memory) before going to the
        network. Deterministic, zero LLM.
        """
        tokens = tokenize_query(query)
        out: List[Dict[str, Any]] = []
        if not tokens or not os.path.exists(self.corpus_path):
            return out
        for line in open(self.corpus_path):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            text = (rec.get("text") or "").lower()
            if any(t in text for t in tokens):
                out.append(rec)
        return out[-limit:]

    def corpus_stats(self) -> Dict[str, Any]:
        texts = self.corpus_texts()
        return {"docs": len(texts), "chars": sum(len(t) for t in texts),
                "path": self.corpus_path}

    def crawl(self, urls: Optional[Sequence[str]] = None, max_pages: int = 3,
              cooldown_s: int = DEFAULT_COOLDOWN_S,
              learn: Optional[Any] = None) -> Dict[str, Any]:
        """Paced crawl: fetch (if off cooldown), train lexicon + corpus."""
        urls = list(urls or self.seeds)[:max_pages]
        now = time.time()
        results = {"fetched": 0, "skipped_cooldown": 0, "failed": [],
                   "tokens_new": 0, "chars_learned": 0, "definitions_new": 0,
                   "pages": []}
        for url in urls:
            last = self._state.get(url, 0)
            if now - last < cooldown_s:
                results["skipped_cooldown"] += 1
                continue
            try:
                text = self._fetch(url)
            except Exception as exc:
                results["failed"].append({"url": url, "error": str(exc)[:120]})
                continue
            if not text:
                results["failed"].append({"url": url, "error": "empty"})
                continue
            chars = self.append_corpus(url, text)
            results["definitions_new"] += self.defs.append(
                url, extract_definitions(text))
            if learn is not None:
                info = learn(text, url)
                results["tokens_new"] += info.get("added", 0)
            if chars:
                self._state[url] = now
                results["fetched"] += 1
                results["chars_learned"] += chars
                results["pages"].append({"url": url, "chars": chars})
        self._save_state()
        return results


# ---- agent-facing convenience -------------------------------------------
def crawl_and_train(state_dir: str, lexicon, max_pages: int = 3,
                    urls: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """One-shot: crawl seeds -> lexicon.mirror() + chat corpus append."""
    ct = CrawlTrainer(state_dir)

    def _learn(text: str, source: str) -> Dict[str, Any]:
        if lexicon is None:
            return {"added": 0}
        added = len(lexicon.mirror(text))
        return {"added": added}

    return ct.crawl(urls=urls, max_pages=max_pages, learn=_learn)
