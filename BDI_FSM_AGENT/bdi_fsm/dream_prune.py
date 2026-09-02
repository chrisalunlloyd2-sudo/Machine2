"""DREAM-PRUNE — source coding for the decision journal.

Correlate with source theory: the journal is a message from the decision
source. High redundancy R = 1 - H/Hmax means the stream is COMPRESSIBLE —
repeated decision paths carry ~zero new information (the source is
habitual). Source coding says: keep the code (the distinct patterns),
discard the redundancy (the repeats).

This module implements that as DREAM-PRUNING:

* KEEP  — novel transitions (first occurrence of each action->next pair),
          every non-ok outcome (fail/block/defer are learning events —
          they feed NMTD guardrails and must never vanish), and the last
          record (so the chain tail stays live).
* ARCHIVE — pure repeats of already-known transitions with ok outcomes:
          redundancy, not information.

ADD-ONLY DOCTRINE: pruning never DELETES. Archived records are moved
verbatim (original hashes) into <journal>.archive.jsonl. The rewritten
journal is a NEW chain whose first record's prev_hash links to the OLD
chain's last hash — provably continuous, provably "forgotten" (like a
dream: the trace compresses, the meaning persists).

Pure stdlib, deterministic, zero LLM.
"""

import hashlib
import json
import math
import os
import time
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple


def _log2(p: float) -> float:
    return math.log2(p) if p > 0 else 0.0


def _hash(record: Dict[str, Any]) -> str:
    body = dict(record)
    body.pop("hash", None)
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _load(path: str) -> List[Dict[str, Any]]:
    rows = []
    if os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def novelty_scores(rows: List[Dict[str, Any]], order: int = 1) -> Dict[int, float]:
    """Per-record novelty = 1 - P(action_i | action history).

    Learned from the journal's OWN Markov transition table (the source's
    empirical statistics — exactly how source coding estimates a code).
    Novelty ~ 0 = perfectly predicted = pure redundancy.
    """
    actions = [r.get("action", "?") for r in rows]
    table: Dict[Tuple[str, ...], Counter] = defaultdict(Counter)
    for i in range(order, len(rows)):
        ctx = tuple(actions[i - order:i])
        table[ctx][actions[i]] += 1
    scores: Dict[int, float] = {}
    for i in range(order, len(rows)):
        ctx = tuple(actions[i - order:i])
        row = table[ctx]
        p = row[actions[i]] / sum(row.values())
        scores[i] = 1.0 - p
    return scores


def classify(rows: List[Dict[str, Any]], keep_threshold: float = 0.3,
             order: int = 1) -> Tuple[List[bool], Dict[str, Any]]:
    """Return per-record keep/archive mask + statistics.

    keep_threshold: a record with novelty < threshold is a redundant repeat
    and gets archived UNLESS it is a first-seen transition, a learning
    event (non-ok), or the chain tail.
    """
    n = len(rows)
    if n < 8:
        return [True] * n, {"reason": "too_few_records", "count": n}
    scores = novelty_scores(rows, order=order)
    # first-seen transitions are the CODE — always keep
    seen_trans: set = set()
    first_seen: set = set()
    for i in range(order, n):
        ctx = tuple(r.get("action", "?") for r in rows[i - order:i])
        nxt = rows[i].get("action", "?")
        key = ctx + (nxt,)
        if key not in seen_trans:
            first_seen.add(i)
            seen_trans.add(key)
    keep = [False] * n
    for i in range(n):
        if i < order:
            keep[i] = True          # no history to predict from — keep
            continue
        if rows[i].get("outcome", "ok") != "ok":
            keep[i] = True          # learning event — never archive
            continue
        if i in first_seen:
            keep[i] = True          # the code
            continue
        if i == n - 1:
            keep[i] = True          # chain tail stays live
            continue
        nov = scores.get(i, 1.0)
        keep[i] = nov >= keep_threshold
    stats = {
        "reason": "pruned",
        "count": n,
        "kept": sum(keep),
        "archived": n - sum(keep),
        "novelty_floor": min(scores.values()) if scores else 1.0,
        "redundancy": 1.0 - (sum(keep) / n) if n else 0.0,
    }
    return keep, stats


def rechain(rows: List[Dict[str, Any]], prev_hash: str) -> List[Dict[str, Any]]:
    """Rebuild the hash chain over kept records, linking to prev_hash."""
    out = []
    ph = prev_hash
    for r in rows:
        rec = dict(r)
        rec["prev_hash"] = ph
        rec["hash"] = _hash(rec)
        out.append(rec)
        ph = rec["hash"]
    return out


def dream_prune(journal_path: str, dry_run: bool = False,
                keep_threshold: float = 0.3, order: int = 1,
                archive_suffix: str = ".archive.jsonl") -> Dict[str, Any]:
    """Prune the journal. Returns a dream report. ADD-only: archives, never deletes.

    Returns report with: kept, archived, redundancy, compression,
    bits_saved, archive_path, chain_ok.
    """
    rows = _load(journal_path)
    if not rows:
        return {"reason": "empty_journal", "count": 0, "kept": 0, "archived": 0}
    keep_mask, stats = classify(rows, keep_threshold=keep_threshold, order=order)
    old_last = rows[-1].get("hash", "")
    kept_rows = [r for r, k in zip(rows, keep_mask) if k]
    archived_rows = [r for r, k in zip(rows, keep_mask) if not k]

    comp_ratio = (len(rows) / len(kept_rows)) if kept_rows else 1.0
    bits_saved = math.log2(comp_ratio) if comp_ratio > 1 else 0.0

    report = {
        "reason": stats.get("reason", "pruned"),
        "ts": time.time(),
        "count": len(rows),
        "kept": len(kept_rows),
        "archived": len(archived_rows),
        "redundancy": round(stats.get("redundancy", 0.0), 4),
        "compression": round(comp_ratio, 3),
        "bits_saved": round(bits_saved, 3),
        "novelty_floor": round(stats.get("novelty_floor", 1.0), 4),
        "threshold": keep_threshold,
        "archive_path": journal_path + archive_suffix,
    }
    if dry_run or not archived_rows:
        report["dry_run"] = dry_run
        report["chain_ok"] = True
        return report

    # 1. archive the pruned records verbatim (original hashes preserved)
    with open(journal_path + archive_suffix, "a") as f:
        f.write(json.dumps({
            "dream_ts": time.time(),
            "reason": "redundant decision path (source coding)",
            "count": len(archived_rows),
            "kept_count": len(kept_rows),
        }) + "\n")
        for r in archived_rows:
            f.write(json.dumps(r) + "\n")

    # 2. rewrite journal as a new chain linked to the OLD last hash
    new_chain = rechain(kept_rows, old_last)
    tmp = journal_path + ".dreamtmp"
    with open(tmp, "w") as f:
        for r in new_chain:
            f.write(json.dumps(r) + "\n")
    os.replace(tmp, journal_path)

    # 3. verify the new chain
    ver = _verify(journal_path, anchor=old_last)
    report["chain_ok"] = ver.get("ok", False)
    report["chain_count"] = ver.get("count", 0)
    report["prev_chain_tail"] = old_last
    return report


def _verify(path: str, anchor: Optional[str] = None) -> Dict[str, Any]:
    """Verify a chain. A virgin chain anchors at GENESIS; a dream-pruned
    chain anchors at the OLD chain's tail (provable continuity)."""
    rows = _load(path)
    prev = anchor or hashlib.sha256(b"GENESIS").hexdigest()
    for e in rows:
        if e.get("prev_hash") != prev:
            return {"ok": False, "broken_at": e.get("seq"), "reason": "prev_hash_mismatch"}
        if e.get("hash") != _hash(e):
            return {"ok": False, "broken_at": e.get("seq"), "reason": "hash_mismatch"}
        prev = e.get("hash", "")
    return {"ok": True, "count": len(rows)}


def format_report(report: Dict[str, Any]) -> str:
    lines = [
        "  DREAM-PRUNE REPORT (source coding)",
        f"  journal: {report.get('count', 0)} records -> kept {report.get('kept', 0)}"
        f" / archived {report.get('archived', 0)}",
        f"  redundancy R={report.get('redundancy', 0):.3f}  "
        f"compression {report.get('compression', 1):.2f}x  "
        f"bits saved {report.get('bits_saved', 0):.3f}",
    ]
    if report.get("reason") == "too_few_records":
        lines.append("  - too few records to dream-prune (need >= 8)")
    elif not report.get("archived"):
        lines.append("  - nothing redundant — every decision carries novelty")
    else:
        lines.append(f"  - archived {report.get('archived')} redundant records -> "
                     f"{report.get('archive_path')} (ADD-only, never deleted)")
        lines.append(f"  - new chain links to old tail {str(report.get('prev_chain_tail'))[:12]}... "
                     f"chain ok={report.get('chain_ok')}")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Dream-prune a decision journal (source coding)")
    ap.add_argument("--journal", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--threshold", type=float, default=0.3)
    ap.add_argument("--order", type=int, default=1)
    args = ap.parse_args(argv)
    report = dream_prune(args.journal, dry_run=args.dry_run,
                         keep_threshold=args.threshold, order=args.order)
    print(format_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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
