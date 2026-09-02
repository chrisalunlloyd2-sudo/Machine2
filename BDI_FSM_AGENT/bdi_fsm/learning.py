"""RECURSIVE LEARNING — learns, expands and mirrors the lexical
environment it is in.

The agent continuously:
  LEARN   — mirror new tokens from every file/log/chat it touches
  EXPAND  — derive new morphological forms from the grown domain set
  MIRROR  — keep a frequency map of the environment's lexicon so the
            agent's vocabulary statistically mirrors its surroundings

Recursive: learned tokens feed the domain set, which feeds expansion,
which feeds new bindings. Each pass makes the next pass richer.
"""

import os
import json
import time
from typing import Any, Dict, List, Optional

from .lexicon import Lexicon


class RecursiveLearner:
    def __init__(self, lexicon: Lexicon, state_dir: str):
        self.lexicon = lexicon
        self.state_dir = state_dir
        self.history_path = os.path.join(state_dir, "learning_history.jsonl")
        os.makedirs(state_dir, exist_ok=True)

    def learn_from_text(self, text: str, source: str = "chat") -> Dict[str, Any]:
        added = self.lexicon.mirror(text)
        expanded = self.lexicon.expand()
        self._log(source, added, expanded)
        return {"added": len(added), "expanded": expanded,
                "total": self.lexicon.size()}

    def learn_from_file(self, path: str) -> Dict[str, Any]:
        added = self.lexicon.mirror_file(path)
        expanded = self.lexicon.expand()
        self._log(path, added, expanded)
        return {"added": len(added), "expanded": expanded,
                "total": self.lexicon.size()}

    def learn_from_directory(self, root: str, extensions=(".py", ".md", ".json", ".txt"),
                             max_files: int = 64) -> Dict[str, Any]:
        total_added = 0
        total_expanded = 0
        scanned = 0
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__", ".bdi_state")]
            for fn in filenames:
                if scanned >= max_files:
                    break
                if fn.endswith(extensions):
                    full = os.path.join(dirpath, fn)
                    r = self.learn_from_file(full)
                    total_added += r["added"]
                    total_expanded += r["expanded"]
                    scanned += 1
            if scanned >= max_files:
                break
        self.lexicon.save()
        return {"scanned": scanned, "added": total_added,
                "expanded": total_expanded, "total": self.lexicon.size()}

    def mirror_report(self) -> Dict[str, Any]:
        """Statistical mirror of the environment's lexicon."""
        return self.lexicon.stats()

    def _log(self, source: str, added: int, expanded: int) -> None:
        with open(self.history_path, "a", encoding="utf-8") as f:
            f.write(f'{{"ts": {time.time()}, "source": "{source}", '
                    f'"added": {added}, "expanded": {expanded}, '
                    f'"total": {self.lexicon.size()}}}\n')

    # ---- better learning: structured sources ---------------------------
    def learn_from_log(self, log_path: str, source: str = "log",
                       max_lines: int = 2000) -> Dict[str, Any]:
        """Mirror tokens from a JSONL log AND record outcome patterns.
        Failing entries get their action/detail mirrored preferentially
        so the lexicon learns the vocabulary of mistakes too."""
        if not os.path.exists(log_path):
            return {"added": 0, "expanded": 0, "total": self.lexicon.size(),
                    "outcomes": {}, "scanned": 0}
        outcomes: Dict[str, int] = {}
        scanned = 0
        added_total = 0
        expanded_total = 0
        for line in open(log_path, encoding="utf-8"):
            if scanned >= max_lines:
                break
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                rec = {"detail": line}
            outcome = rec.get("outcome")
            if outcome:
                outcomes[outcome] = outcomes.get(outcome, 0) + 1
            text = " ".join(str(rec.get(k, "")) for k in
                            ("action", "detail", "outcome", "agent", "title"))
            if text.strip():
                r = self.learn_from_text(text, source=f"{source}:{scanned}")
                added_total += r["added"]
                expanded_total += r["expanded"]
            scanned += 1
        self.lexicon.save()
        return {"added": added_total, "expanded": expanded_total,
                "total": self.lexicon.size(), "outcomes": outcomes,
                "scanned": scanned}

    def extract_concepts(self, texts: List[str], top_k: int = 20,
                         stopwords: Optional[set] = None) -> List[Dict[str, Any]]:
        """Deterministic concept extraction: frequency + bigram co-occurrence.
        Returns [(concept, score)] where score rewards frequent, domain-y
        terms that appear across many sources (not in a single one)."""
        import re as _re
        stop = stopwords or {"the", "and", "for", "with", "from", "this",
                             "that", "are", "was", "were", "has", "have",
                             "not", "but", "its", "it's", "into", "than"}
        freq: Dict[str, int] = {}
        docs: Dict[str, int] = {}
        for t in texts:
            toks = set(_re.findall(r"[a-z][a-z0-9_]{2,}", t.lower()))
            seen_doc = set()
            for tok in toks:
                if tok in stop or len(tok) < 4:
                    continue
                freq[tok] = freq.get(tok, 0) + 1
                if tok not in seen_doc:
                    docs[tok] = docs.get(tok, 0) + 1
                    seen_doc.add(tok)
        scored = []
        for tok, f in freq.items():
            d = docs.get(tok, 1)
            score = f * d  # frequent AND spread across sources
            scored.append({"concept": tok, "frequency": f, "sources": d,
                           "score": score})
        scored.sort(key=lambda x: (-x["score"], x["concept"]))
        return scored[:top_k]

    def auto_guardrail(self, fail_text: str, action: str = "act",
                       source: str = "journal") -> Dict[str, str]:
        """Derive a guardrail rule from a failure description."""
        snippet = fail_text.strip().replace("\n", " ")[:160]
        return {
            "trigger": action,
            "rule": f"Never {action} blindly when: {snippet}",
            "source": source,
        }

    def learn_from_journal(self, journal_path: str, source: str = "journal") -> Dict[str, Any]:
        """Convenience: mirror a journal + extract concepts from its details."""
        r = self.learn_from_log(journal_path, source=source)
        entries = []
        if os.path.exists(journal_path):
            for line in open(journal_path, encoding="utf-8"):
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line).get("detail", ""))
                except json.JSONDecodeError:
                    pass
        r["concepts"] = self.extract_concepts(entries, top_k=10)
        return r
