#!/usr/bin/env python3
"""TRAIN STEP — run by the heartbeat: webcrawl self-training + dream
pruning + training-log append. One deterministic step per heartbeat.

Flow:
  1. WEB CRAWL  — fetch paced seed pages (off cooldown), strip to prose,
     learn tokens into the lexicon (syntax) AND append prose to the
     Markov chat corpus (semantics).  Zero LLM — pure ingestion.
  2. DREAM      — Shannon-driven journal archival (programmatic
     correction: redundant chains archive, fails always kept).
  3. LOG        — append a dated entry to docs/TRAINING_LOG.md so the
     training state is a human-readable document IN the repo.
  4. (heartbeat) commits + pushes the repo — training is the natural
     progression, hot-updated to GitHub every heartbeat.

Usage: python3 scripts/train_step.py [--max-pages N] [--dry-run]
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from bdi_fsm.webcrawl import CrawlTrainer, DEFAULT_SEEDS
from bdi_fsm.lexicon import Lexicon

STATE_DIR = os.path.join(REPO, "state")
LOG_PATH = os.path.join(REPO, "docs", "TRAINING_LOG.md")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-pages", type=int, default=3)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    os.makedirs(STATE_DIR, exist_ok=True)
    os.makedirs(os.path.join(STATE_DIR, "corpus"), exist_ok=True)
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

    lexicon = Lexicon(os.path.join(STATE_DIR, "lexicon.json"))
    ct = CrawlTrainer(STATE_DIR)

    def _learn(text: str, url: str) -> dict:
        added = len(lexicon.mirror(text))
        lexicon.save()
        return {"added": added}

    # ---- 1. webcrawl self-training (paced) ----------------------------
    crawl = ct.crawl(max_pages=args.max_pages, learn=_learn)
    stats = ct.corpus_stats()

    # ---- 2. dream: programmatic correction of the journal ---------------
    dream = {"archived": 0, "kept": 0}
    jpath = os.path.join(STATE_DIR, "journal.jsonl")
    if os.path.exists(jpath) and not args.dry_run:
        try:
            from bdi_fsm.journal import Journal
            j = Journal(jpath)
            d = j.dream_prune()
            dream = {"archived": d.get("archived", 0), "kept": d.get("kept", 0)}
        except Exception as exc:
            dream = {"error": str(exc)[:120]}

    # ---- 3. append training log document --------------------------------
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    entry = [
        f"## {ts}",
        f"- crawl: {crawl['fetched']} fetched / {crawl['skipped_cooldown']} cooldown, "
        f"{crawl['tokens_new']} new tokens, {crawl['chars_learned']} chars",
        f"- corpus: {stats['docs']} docs, {stats['chars']} chars",
        f"- dream: {dream.get('archived', 0)} archived / {dream.get('kept', 0)} kept",
        f"- lexicon: {len(lexicon.tokens) if hasattr(lexicon, 'tokens') else 'n/a'} tokens",
        "",
    ]
    if not args.dry_run:
        with open(LOG_PATH, "a") as f:
            f.write("\n".join(entry))
    else:
        print("DRY-RUN — would append:", "\n".join(entry))

    print(json.dumps({
        "crawl": crawl, "corpus": stats, "dream": dream,
        "log": LOG_PATH, "ts": ts,
    }, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
