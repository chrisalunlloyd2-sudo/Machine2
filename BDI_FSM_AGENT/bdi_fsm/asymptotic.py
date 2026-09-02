"""ASYMPTOTIC DREAM-CYCLE — prune every day/DB to its OPTIMAL size.

Chris 2026-08-15: "the key to keep it up is having a specialized dream cycle
that prunes all days and dbs to the optimal size where we see asymptotic
relationship to effectiveness... if done correctly we won't lose anything good."

The mechanism: rank every item by its marginal VALUE (information/utility),
form the cumulative effectiveness-vs-retained curve, and cut at the KNEE —
the point where additional retention stops paying off (diminishing returns =
the asymptote). Items past the knee are ARCHIVED, never deleted. Because the
curve flattens at the knee, archiving the tail loses ~no effectiveness: we
keep the value, shed the redundancy.

Pure stdlib, deterministic, zero-LLM, ADD-only.
"""

from __future__ import annotations

import json
import os
import re
import time
from collections import Counter
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

_MIN_GAIN = 0.05
_MIN_CORPUS_LINES = 500  # floor: keep at least this many corpus lines (training diversity)
_PRUNE_COOLDOWN_HOURS = 24  # skip prune if one happened recently (anti compound-prune)
_MIN_RETAINED_VALUE = 0.50  # knee validity: a prune must keep >= half the remaining info value; below this the knee is an artifact, not an asymptote


def effectiveness_curve(values: Sequence[float]) -> Dict[str, Any]:
    """Normalized effectiveness-vs-retained curve (Kneedle difference curve).

    values must be marginal utilities in DESCENDING order (best first).
    Returns {n, points:[{x,y,diff}], knee_i, knee_gain, retained_value}.
    """
    n = len(values)
    total = sum(values)
    if n == 0 or total <= 0:
        return {"n": n, "points": [], "knee_i": 0,
                "knee_gain": 0.0, "retained_value": 1.0}
    cum = 0.0
    points: List[Dict[str, float]] = []
    diffs: List[float] = []
    for i, v in enumerate(values):
        cum += v
        x = (i + 1) / n
        y = cum / total
        d = y - x
        points.append({"x": round(x, 4), "y": round(y, 4), "diff": round(d, 4)})
        diffs.append(d)
    knee_i = max(range(n), key=lambda i: diffs[i])
    return {"n": n, "points": points, "knee_i": knee_i,
            "knee_gain": round(diffs[knee_i], 4),
            "retained_value": round(points[knee_i]["y"], 4)}


def find_knee(values: Sequence[float], min_gain: float = _MIN_GAIN) -> int:
    """Return the cut index: keep values[:k], archive values[k:].

    Returns len(values) when no meaningful knee exists (curve ~linear /
    uniform) — nothing to prune. Deterministic.
    """
    n = len(values)
    if n < 3:
        return n
    c = effectiveness_curve(values)
    if c["knee_gain"] < min_gain:
        return n
    return c["knee_i"] + 1


def prune_to_knee(items: Sequence[Any], value_of: Callable[[Any], float],
                  min_gain: float = _MIN_GAIN) -> Dict[str, Any]:
    """Generic knee-pruner. Ranks items by value desc, keeps through the knee,
    archives the rest (never deletes). Returns {kept, archived, knee, ...}."""
    if not items:
        return {"kept": [], "archived": [], "knee": 0, "curve": None,
                "retained_value": 1.0, "retained_fraction": 1.0}
    ranked = sorted(items, key=value_of, reverse=True)
    values = [max(0.0, value_of(it)) for it in ranked]
    curve = effectiveness_curve(values)
    k = find_knee(values, min_gain)
    return {"kept": ranked[:k], "archived": ranked[k:], "knee": k,
            "curve": curve, "retained_value": curve["retained_value"],
            "retained_fraction": round(k / len(ranked), 4) if ranked else 1.0,
            "n": len(ranked)}


# --- value functions -------------------------------------------------------

def _tokens(text: str) -> List[str]:
    return [t for t in re.findall(r"[a-z0-9_+-]+", text.lower()) if len(t) > 2]


def corpus_line_values(lines: Sequence[str]) -> List[float]:
    """Information value per corpus line: sum of inverse token frequency.
    Lines with rarer tokens (novel content) score higher; boilerplate/repeats
    score low. Deterministic."""
    freq: Counter = Counter()
    for line in lines:
        freq.update(_tokens(line))
    values: List[float] = []
    for line in lines:
        toks = _tokens(line)
        values.append(sum(1.0 / freq[t] for t in toks) if toks else 0.0)
    return values


def node_values(nodes: Sequence[Dict], utility: Callable[[Dict], float]) -> List[float]:
    return [max(0.0, utility(n)) for n in nodes]


# --- corpus pruning --------------------------------------------------------

def prune_corpus(corpus_path: str, dry_run: bool = False,
                 min_gain: float = _MIN_GAIN,
                 min_lines: int = _MIN_CORPUS_LINES,
                 cooldown_hours: float = _PRUNE_COOLDOWN_HOURS) -> Dict[str, Any]:
    """Knee-prune the chat corpus. Archived lines -> <corpus>.archive.jsonl.
    ADD-only: archive, never delete.

    Anti compound-prune: if an archive already exists and was written within
    ``cooldown_hours``, skip the prune entirely — a knee found on an already
    knee-pruned set is a degenerate knee (retained_value drops below ~0.6 and
    the floor becomes the only guard). Repeated pruning re-finds a knee on any
    distribution; the cooldown is the stability check."""
    archive_path = corpus_path + ".archive.jsonl"
    if os.path.exists(archive_path):
        age_h = (time.time() - os.path.getmtime(archive_path)) / 3600.0
        if age_h < cooldown_hours:
            with open(corpus_path) as f:
                n = len([ln for ln in f if ln.strip()])
            return {"reason": "cooldown_skip", "ts": time.time(), "count": n,
                    "kept": n, "archived": 0, "knee": n,
                    "retained_value": 1.0, "retained_fraction": 1.0,
                    "archive_path": archive_path, "dry_run": dry_run,
                    "archive_age_hours": round(age_h, 2)}
    try:
        with open(corpus_path) as f:
            raw = [ln for ln in f if ln.strip()]
    except FileNotFoundError:
        return {"reason": "no_corpus", "kept": 0, "archived": 0}
    texts = []
    for ln in raw:
        try:
            texts.append(json.loads(ln).get("text", ""))
        except json.JSONDecodeError:
            texts.append(ln)
    values = corpus_line_values(texts)
    ranked_idx = sorted(range(len(texts)), key=lambda i: values[i], reverse=True)
    ordered_values = [values[i] for i in ranked_idx]
    k = find_knee(ordered_values, min_gain)
    # floor: never compound-prune below viable training diversity
    k = max(k, min(min_lines, len(raw)))
    # knee-validity check (heartbeat 2026-08-16): a real asymptotic knee must
    # retain at least half the remaining information value. Re-pruning an
    # already knee-pruned set finds a spurious knee at the head whose floor-
    # rescued cut keeps < 0.50 of remaining value (degenerate 0.492 vs good
    # 0.668) — the floor alone is insufficient. Skip the prune in that case.
    # Evaluated at the FLOORED k (what would actually be kept), not the
    # natural knee: the floor only ever raises k, so floored retention is the
    # honest bound for the cut that would really happen.
    if k < len(raw):
        total_v = sum(ordered_values)
        rv = sum(ordered_values[:k]) / total_v if total_v > 0 else 1.0
        if rv < _MIN_RETAINED_VALUE:
            return {"reason": "degenerate_knee", "ts": time.time(),
                    "count": len(raw), "kept": len(raw), "archived": 0,
                    "knee": k, "retained_value": 1.0, "retained_fraction": 1.0,
                    "would_keep": k, "would_retain": round(rv, 4),
                    "archive_path": corpus_path + ".archive.jsonl",
                    "dry_run": dry_run}
    keep_idx = set(ranked_idx[:k])
    kept_lines = [raw[i] for i in range(len(raw)) if i in keep_idx]
    archived_lines = [raw[i] for i in range(len(raw)) if i not in keep_idx]
    curve = effectiveness_curve(ordered_values)
    report = {
        "reason": "asymptotic_knee", "ts": time.time(),
        "count": len(raw), "kept": len(kept_lines), "archived": len(archived_lines),
        "knee": k, "retained_value": curve["retained_value"],
        "retained_fraction": round(len(kept_lines) / len(raw), 4) if raw else 1.0,
        "archive_path": corpus_path + ".archive.jsonl",
    }
    if dry_run or not archived_lines:
        report["dry_run"] = dry_run
        return report
    with open(corpus_path + ".archive.jsonl", "a") as f:
        f.write(json.dumps({"dream_ts": time.time(),
                            "reason": "asymptotic knee (diminishing returns)",
                            "count": len(archived_lines)}) + "\n")
        f.writelines(archived_lines)
    tmp = corpus_path + ".tmp"
    with open(tmp, "w") as f:
        f.writelines(kept_lines)
    os.replace(tmp, corpus_path)
    return report


# --- orchestrator ----------------------------------------------------------

def dream_asymptotic(agent, *, corpus: bool = True, world: bool = True,
                     dry_run: bool = True, min_gain: float = _MIN_GAIN) -> Dict[str, Any]:
    """Run the asymptotic dream across every day/DB. Failure-isolated stages."""
    report: Dict[str, Any] = {}
    if corpus:
        try:
            cp = os.path.join(agent.state_dir, "corpus", "chat_corpus.jsonl")
            report["corpus"] = prune_corpus(cp, dry_run=dry_run, min_gain=min_gain)
        except Exception as exc:
            report["corpus"] = {"error": f"{type(exc).__name__}: {exc}"}
    if world:
        try:
            wm = getattr(agent, "world", None)
            if wm is not None and hasattr(wm, "prune_to_optimum"):
                report["world"] = wm.prune_to_optimum(dry_run=dry_run)
            else:
                report["world"] = {"reason": "no_world_model"}
        except Exception as exc:
            report["world"] = {"error": f"{type(exc).__name__}: {exc}"}
    report["done"] = True
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
