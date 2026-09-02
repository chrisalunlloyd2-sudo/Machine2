"""learning_loop.py — multi-trace pattern mining -> SOP promotion (hourly).

Chris 2026-08-15: "collate all the real asks' guards, let meaning.py's 4-axis
detector score which guards are stable across varied asks, and promote only
those crossing 0.7 to SOPs. One correction = a rule; many consistent corrections
= an SOP." And: "have them in a learning loop paced 1 time an hour to facilitate
the connection and troubleshoot entry and exit points."

This module is that loop. It turns accumulated code-ask traces into token
sequences, mines candidate guards (intent -> layout -> outcome), scores each
with meaning.py's 4-axis detector, and promotes the ones that cross the
threshold into a persistent SOP store. It also reports ENTRY stats (which
intents were recognized) and EXIT stats (which outcomes were good/bad) — the
"troubleshoot entry and exit points" view.

Deterministic, zero-LLM.
"""

from __future__ import annotations

import json
import os
from collections import Counter
from typing import Any, Dict, List, Optional, Sequence

from .layout import load_traces
from .meaning import compute_meaning_score


def encode_trace(trace: Dict[str, Any]) -> List[str]:
    """A trace -> a token sequence the 4-axis detector can score.

    e.g. {intent: comparison, strategy: table, judgment: good}
         -> ["intent:comparison", "layout:table", "ok"]
    """
    feats = trace.get("features", {})
    seq: List[str] = []
    intent = feats.get("intent")
    if intent:
        seq.append(f"intent:{intent}")
    seq.append(f"layout:{trace.get('strategy', 'list')}")
    seq.append("ok" if trace.get("judgment") == "good" else "bad")
    return seq


def mine_patterns(traces: List[Dict[str, Any]]) -> List[List[str]]:
    """Candidate guards = contiguous subsequences of encoded traces.

    A guard is intent->layout or intent->layout->outcome (length >= 2)."""
    patterns = set()
    for t in traces:
        seq = encode_trace(t)
        for i in range(len(seq)):
            for j in range(i + 2, len(seq) + 1):
                patterns.add(tuple(seq[i:j]))
    return [list(p) for p in patterns]


def score_and_promote(patterns: List[Sequence], history: List[Sequence],
                      sops: List[Sequence],
                      config: Optional[Dict] = None) -> List[Dict[str, Any]]:
    """Score each candidate; return the promoted ones (score >= threshold)."""
    promoted = []
    for p in patterns:
        r = compute_meaning_score(p, history, list(sops), config)
        if r["promote"]:
            promoted.append({"pattern": list(p), "score": r["score"],
                             "axes": r["axes"]})
    promoted.sort(key=lambda x: -x["score"])
    return promoted


def load_sops(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f)


def save_sops(sops: List[Dict[str, Any]], path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(sops, f, indent=2)


def run_learning_loop(trace_path: str, sop_path: str,
                      config: Optional[Dict] = None,
                      demotion_threshold: float = 0.5) -> Dict[str, Any]:
    """One hourly pass: mine -> score -> promote -> demote -> report entry/exit.

    Promotion is the ENTRY point (a guard crosses 0.7 -> SOP). Demotion is the
    EXIT point (a stale SOP whose pattern stopped explaining good outcomes, or
    whose score decayed below demotion_threshold, is dropped). "Nothing lives
    forever" applied to SOPs: they are re-scored every pass and fall out when
    they stop earning their keep.
    """
    traces = load_traces(trace_path)
    if not traces:
        return {"traces": 0, "patterns": 0, "promoted": 0, "demoted": 0,
                "new_sops": [], "entry": {}, "exit": {}}
    history = [encode_trace(t) for t in traces]
    patterns = mine_patterns(traces)
    sops = load_sops(sop_path)
    existing_patterns = [s["pattern"] for s in sops]
    promoted = score_and_promote(patterns, history, existing_patterns, config)

    # accumulate: add promoted patterns not already stored
    have = set(tuple(s["pattern"]) for s in sops)
    new_sops = []
    for p in promoted:
        if tuple(p["pattern"]) not in have:
            have.add(tuple(p["pattern"]))
            new_sops.append({"pattern": p["pattern"], "score": p["score"]})
    sops.extend(new_sops)

    # demotion: re-score every SOP against the updated history; drop stale ones
    kept, demoted = [], []
    all_pats = [s["pattern"] for s in sops]
    for s in sops:
        r = compute_meaning_score(s["pattern"], history, all_pats, config)
        if r["promote"] or (not r["veto"] and r["score"] >= demotion_threshold):
            s["score"] = r["score"]
            kept.append(s)
        else:
            demoted.append(s["pattern"])
    sops = kept
    save_sops(sops, sop_path)

    # entry/exit troubleshooting
    entry = Counter()
    exitc = Counter()
    for t in traces:
        entry[t.get("features", {}).get("intent") or "none"] += 1
        exitc[t.get("judgment", "bad")] += 1

    return {"traces": len(traces), "patterns": len(patterns),
            "promoted": len(promoted), "demoted": len(demoted),
            "new_sops": new_sops, "entry": dict(entry), "exit": dict(exitc)}

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
