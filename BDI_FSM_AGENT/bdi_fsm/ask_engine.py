"""ask_engine.py — definitive, exhaustive TELL answers from cross-correlated evidence.

The #1 demo: input a question like "which github will be best for robotic
implementation of llm" -> the engine:

  1. parses the question (intent + topic + explicit candidates),
  2. gathers local evidence (repo facts + corpus) AND web evidence
     (Wikipedia opensearch, deterministic stdlib),
  3. scores every candidate in DECIBANS (the "eerie bans"), ranked above the
     Nash threshold,
  4. renders a definitive, semi-human, 100%-exhaustive TELL listing every
     variable and data point in the FORM of the answer.

Deterministic, zero-LLM. Text is a rendered view of the scored state.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any, Callable, Dict, List, Optional, Tuple

from .digest import repo_facts
from .search_fallback import _wikipedia_search

_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "for", "on", "with",
    "is", "are", "was", "were", "be", "been", "which", "what", "who", "whom",
    "whose", "how", "why", "when", "where", "best", "better", "worst", "good",
    "bad", "would", "will", "should", "could", "can", "my", "me", "about",
    "said", "projects", "project", "github", "repos", "repo", "vs", "versus",
    "ask", "compare", "rank", "do", "does",
    "you", "your", "i", "it", "this", "that", "these", "those",
}
_QUESTION_WORDS = {"which", "what", "who", "how", "why", "when", "where", "is",
                   "are", "best", "better", "vs", "versus", "compare", "rank"}


def tokenize(text: str) -> List[str]:
    toks = re.findall(r"[a-z0-9_+-]+", text.lower())
    return [t for t in toks if t not in _STOPWORDS and len(t) > 2]



def _components(text: str) -> set:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _topic_match(topic: str, text: str) -> bool:
    """True if topic is a whole word/component (underscore/hyphen split), not a
    substring — so 'agent' matches 'bdi_fsm_agent' but not 'manager'/'agents'."""
    return topic in _components(text)


def parse_query(q: str) -> Dict[str, Any]:
    """Parse a question -> {intent, candidates, topic, raw}."""
    ql = q.lower()
    # explicit candidates via vs/versus
    candidates: List[str] = []
    if " vs " in ql or " versus " in ql:
        parts = re.split(r"\s+vs\s+|\s+versus\s+", ql)
        for p in parts:
            toks = [t for t in tokenize(p) if t not in _QUESTION_WORDS]
            if toks:
                candidates.append(toks[0])
        intent = "compare" if len(candidates) >= 2 else "best"
    else:
        intent = "best"
    # topic: words after 'for'/'about', else non-question content words
    m = re.search(r"\b(?:for|about)\s+(.+)$", ql)
    topic_src = m.group(1) if m else ql
    topic = [t for t in tokenize(topic_src) if t not in _QUESTION_WORDS]
    return {"intent": intent, "candidates": candidates,
            "topic": topic, "raw": q}


def score_repo(name: str, facts: List[Dict[str, str]], topic: List[str],
               corpus_lines: List[str], web_hits: List[Tuple[str, str, str]],
               theta_ban: float = 0.0) -> Dict[str, Any]:
    """Score one repo against the topic. Returns {repo, score, ban, evidence, verdict}."""
    evidence: List[str] = []
    score = 0.0
    nt = set(topic)
    low = name.lower()
    for t in topic:
        if _topic_match(t, low):
            score += 10.0
            evidence.append(f"name contains '{t}'")
    for f in facts:
        if f["subject"].lower() != low:
            continue
        rel, obj = f["relation"], f["object"]
        txt = f"{rel} {obj}"
        hit = sum(1 for t in nt if _topic_match(t, txt))
        if hit:
            w = {"language": 8, "extension count": 8, "key file": 7,
                 "top dir": 5, "has doc": 4, "file count": 3,
                 "location": 1}.get(rel, 4)
            score += w * hit
            evidence.append(f"{rel}={obj} (matches {hit} topic term(s))")
    corpus_hits = 0
    for line in corpus_lines:
        h = sum(1 for t in nt if _topic_match(t, line))
        if h:
            corpus_hits += 1
            score += min(h, 3)
            if corpus_hits <= 4:
                evidence.append(f"corpus: {line.strip()[:90]}")
    if corpus_hits > 4:
        evidence.append(f"...and {corpus_hits - 4} more corpus lines match")
    web_hit_n = 0
    for title, url, snippet in web_hits:
        blob = f"{title} {snippet}".lower()
        if low in blob or any(t in blob for t in nt):
            web_hit_n += 1
            score += 3.0
            if web_hit_n <= 3:
                evidence.append(f"web: {title} — {snippet[:80]}")
    ban = 10.0 * math.log10(1.0 + score) if score > 0 else 0.0
    verdict = "RELEVANT" if score > 0 and ban >= theta_ban else "below threshold"
    return {"repo": name, "score": score, "ban": round(ban, 2),
            "evidence": evidence, "verdict": verdict,
            "corpus_hits": corpus_hits, "web_hits": web_hit_n}


def _repo_corpus_lines(corpus_path: str, name: str) -> List[str]:
    try:
        import json
        lines = []
        with open(corpus_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                o = json.loads(line)
                txt = o.get("text", "")
                if name.lower() in txt.lower():
                    lines.append(txt)
        return lines
    except Exception:
        return []


def compare(question: str, corpus_path: str,
            searcher: Optional[Callable] = None,
            mirrors: Optional[List[str]] = None,
            theta_ban: float = 0.0) -> Dict[str, Any]:
    """Full pipeline: parse -> gather -> score -> rank -> tell."""
    searcher = searcher or _wikipedia_search
    q = parse_query(question)
    facts = repo_facts(mirrors)
    # group facts by repo name
    by_repo: Dict[str, List[Dict]] = {}
    for f in facts:
        by_repo.setdefault(f["subject"], []).append(f)
    names = sorted(by_repo)
    # web search: query EACH topic token separately (opensearch is prefix
    # match — a full multi-word phrase returns 0 hits), then dedupe by title.
    web_hits: List[Tuple[str, str, str]] = []
    for t in q["topic"][:4]:
        try:
            web_hits.extend(searcher(t, limit=3))
        except Exception:
            pass
    seen_titles = set()
    deduped = []
    for h in web_hits:
        if h[0] not in seen_titles:
            seen_titles.add(h[0])
            deduped.append(h)
    web_hits = deduped
    ranked = []
    for name in names:
        if q["candidates"] and name.lower() not in q["candidates"]:
            continue
        corpus_lines = _repo_corpus_lines(corpus_path, name)
        ranked.append(score_repo(name, by_repo[name], q["topic"],
                                 corpus_lines, web_hits, theta_ban))
    ranked.sort(key=lambda r: r["ban"], reverse=True)
    tell = render_tell(question, q, ranked, web_hits, theta_ban)
    return {"question": question, "intent": q["intent"], "topic": q["topic"],
            "candidates": q["candidates"], "ranked": ranked,
            "web_hits": [(t, u) for t, u, _ in web_hits],
            "tell": tell}


def render_tell(question: str, q: Dict, ranked: List[Dict],
                web_hits: List[Tuple[str, str, str]],
                theta_ban: float) -> str:
    out: List[str] = []
    out.append(f"QUESTION: {question}")
    out.append(f"TOPIC: {', '.join(q['topic']) or '(none extracted)'}")
    out.append(f"NASH THRESHOLD (theta*): {theta_ban} ban")
    out.append(f"WEB EVIDENCE: {len(web_hits)} hits" +
               (f" — {web_hits[0][0]}" if web_hits else " (none)"))
    out.append("")
    if not ranked:
        out.append("ANSWER: no repositories matched the query.")
        return "\n".join(out)
    for i, r in enumerate(ranked, 1):
        out.append(f"{i}. {r['repo']} — ban {r['ban']} (score {r['score']:.1f}) "
                   f"[{r['verdict']}]")
        for e in r["evidence"]:
            out.append(f"   - {e}")
        if not r["evidence"]:
            out.append("   - (no direct evidence)")
        out.append("")
    best = ranked[0]
    if best["ban"] >= theta_ban and theta_ban > 0:
        out.append(f"ANSWER: {best['repo']} is the best match, ranked by "
                   f"{best['ban']} ban against {len(ranked)} repositories.")
    else:
        # exhaustive verdict even when nothing crosses theta
        top = ", ".join(f"{r['repo']} ({r['ban']})" for r in ranked[:3])
        out.append(f"ANSWER: {best['repo']} leads at {best['ban']} ban. "
                   f"Ranked: {top}.")
    return "\n".join(out)

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
