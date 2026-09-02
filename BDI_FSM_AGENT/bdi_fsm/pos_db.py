"""pos_db.py — nouns/verbs/adverbs/adjectives databases + proximity relations.

Chris 2026-08-15: "nouns are the key symbolic databases, verbs will be another
database... verbs modify nouns... adverbs modify modifiers... if close by in
sentence or paragraph it is probably related, log all related relations.
Contextual appropriateness should never matter on how it sounds — the data
vectors and algorithms and data flow will be correct."

Deterministic POS tagging (suffix heuristics), partitioned word databases, and
proximity-weighted relation logging ("close by = related"). Zero-LLM, stdlib.
Imperfect tags are FINE — "its ok to repeat, ban will correct": the deciban
scoring downstream separates signal from noise.

The directional pattern: relations are logged as (modifier -> head) so the
verb->noun and adverb->modifier directions are explicit — that is the "clear
directional pattern" to learn from.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Dict, List, Tuple

_STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "for", "on", "with",
    "is", "are", "was", "were", "be", "been", "being", "this", "that",
    "these", "those", "it", "its", "i", "you", "he", "she", "we", "they",
    "my", "your", "his", "her", "their", "as", "at", "by", "from", "not",
    "but", "so", "if", "then", "than", "too", "very", "have", "has", "had",
    "do", "does", "did", "will", "would", "can", "could", "should", "shall",
    "may", "might", "must", "just", "only", "also", "more", "most", "less",
}

_NOUN_SUFFIX = ("tion", "sion", "ment", "ness", "ity", "ance", "ence", "ism",
                "ship", "hood", "age", "er", "or", "ist", "ing")
_VERB_SUFFIX = ("ize", "ise", "ify", "ate", "en")
_ADJ_SUFFIX = ("ous", "ious", "ful", "less", "ive", "able", "ible", "al",
               "ic", "ical", "ary", "ent", "ant", "y")


def tokenize(text: str) -> List[str]:
    return [t for t in re.findall(r"[a-z0-9_+-]+", text.lower()) if len(t) > 2]


def tag(word: str) -> str:
    """Deterministic POS: noun / verb / adjective / adverb."""
    w = word.lower()
    if w.endswith("ly") and len(w) > 4:
        return "adverb"
    if w.endswith(_NOUN_SUFFIX):
        return "noun"
    if w.endswith(_VERB_SUFFIX):
        return "verb"
    if w.endswith(_ADJ_SUFFIX):
        return "adjective"
    return "noun"  # nouns are the default "key symbolic database"


class PosDB:
    """Partitioned word databases + proximity-weighted relation log."""

    def __init__(self):
        self.nouns: Dict[str, float] = defaultdict(float)
        self.verbs: Dict[str, float] = defaultdict(float)
        self.adverbs: Dict[str, float] = defaultdict(float)
        self.adjectives: Dict[str, float] = defaultdict(float)
        self.relations: Dict[Tuple[str, str], float] = defaultdict(float)
        self.typed: Dict[Tuple[str, str], List[str]] = defaultdict(list)
        self.by_pos: Dict[str, Dict[str, float]] = {
            "noun": self.nouns, "verb": self.verbs,
            "adverb": self.adverbs, "adjective": self.adjectives,
        }

    def _bump(self, pos: str, word: str, weight: float = 1.0) -> None:
        self.by_pos[pos][word] += weight

    def _rel(self, src: str, dst: str, weight: float, kind: str) -> None:
        self.relations[(src, dst)] += weight
        if kind not in self.typed[(src, dst)]:
            self.typed[(src, dst)].append(kind)

    def ingest(self, text: str, window: int = 5) -> Dict[str, int]:
        """Proximity-weighted relation logging. 'close by = related'."""
        words = [(w, tag(w)) for w in tokenize(text) if w not in _STOP]
        for w, pos in words:
            self._bump(pos, w)
        added = 0
        for i in range(len(words)):
            w1, pos1 = words[i]
            for j in range(i + 1, min(i + window + 1, len(words))):
                w2, pos2 = words[j]
                weight = 1.0 / (j - i)
                self._rel(w1, w2, weight, "proximity")
                added += 1
                if pos1 == "verb" and pos2 == "noun":
                    self._rel(w1, w2, weight, "verb->noun")
                elif pos1 == "adverb" and pos2 in ("verb", "adjective"):
                    self._rel(w1, w2, weight, "adverb->modifier")
                elif pos1 == "noun" and pos2 == "verb":
                    self._rel(w1, w2, weight, "noun->verb")
        return {"relations": added, "words": len(words)}

    def top_relations(self, n: int = 10) -> List[Tuple[Tuple[str, str], float]]:
        return sorted(self.relations.items(), key=lambda kv: kv[1], reverse=True)[:n]

    def stats(self) -> Dict[str, int]:
        return {"noun": len(self.nouns), "verb": len(self.verbs),
                "adverb": len(self.adverbs), "adjective": len(self.adjectives),
                "relations": len(self.relations)}
