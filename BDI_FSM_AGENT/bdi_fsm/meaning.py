"""meaning.py — meaning detection: stable + compressive + predictive + integrated.

Chris 2026-08-15: meaning = a pattern that is
    stable      (repeats under variation)
    compressive (explains many events with few rules)
    predictive  (improves next-step accuracy)
    integrated  (fits into existing flows without breaking constraints)

A candidate pattern is promoted to SOP/heuristic only if its weighted
meaning_score >= promotion_threshold and it is non-conflicting (hard veto).
Deterministic, zero-LLM.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Sequence, Tuple

DEFAULT_CONFIG: Dict[str, Any] = {
    "stability": {"min_occurrences": 5, "min_consistency": 0.8},
    "compression": {"min_events_explained": 20, "max_description_bits": 512},
    "predictive_utility": {"min_error_reduction": 0.1, "min_latency_improvement": 0.05},
    "integration": {"max_conflicts_with_sops": 0, "max_added_complexity_score": 0.2},
    "weights": {"stability": 0.35, "compression": 0.25,
                "predictive_utility": 0.25, "integration": 0.15},
    "promotion_threshold": 0.7,
}


def _occurrences(pattern: Sequence, history: Sequence[Sequence]) -> List[int]:
    """Indices of events containing the pattern as a contiguous subsequence."""
    p = tuple(pattern)
    if not p:
        return []
    idx = []
    for i, ev in enumerate(history):
        e = tuple(ev)
        if any(e[j:j + len(p)] == p for j in range(len(e) - len(p) + 1)):
            idx.append(i)
    return idx


def _next_tokens(pattern: Sequence, history: Sequence[Sequence]) -> List:
    """The token(s) that follow each occurrence of the pattern."""
    p = tuple(pattern)
    out = []
    for i in _occurrences(pattern, history):
        e = tuple(history[i])
        for j in range(len(e) - len(p) + 1):
            if e[j:j + len(p)] == p:
                if j + len(p) < len(e):
                    out.append(e[j + len(p)])
                break
    return out


def measure_stability(pattern, history, config) -> Tuple[float, Dict]:
    occ = len(_occurrences(pattern, history))
    if occ == 0:
        return 0.0, {"occurrences": 0, "consistency": 0.0}
    nxt = _next_tokens(pattern, history)
    consistency = (Counter(nxt).most_common(1)[0][1] / len(nxt)) if nxt else 0.0
    occ_score = min(1.0, occ / config["stability"]["min_occurrences"])
    score = 0.5 * occ_score + 0.5 * consistency
    return score, {"occurrences": occ, "consistency": consistency}


def measure_compression(pattern, history, config) -> Tuple[float, Dict]:
    events_explained = len(_occurrences(pattern, history))
    saved = events_explained * max(1, len(pattern) - 1)
    ev_score = min(1.0, events_explained / config["compression"]["min_events_explained"])
    bit_score = min(1.0, saved / config["compression"]["max_description_bits"])
    return 0.5 * ev_score + 0.5 * bit_score, \
        {"events_explained": events_explained, "bits_saved": saved}


def measure_predictive_utility(pattern, history, config) -> Tuple[float, Dict]:
    nxt = _next_tokens(pattern, history)
    if not nxt:
        return 0.0, {"accuracy": 0.0, "baseline": 0.0, "reduction": 0.0}
    accuracy = Counter(nxt).most_common(1)[0][1] / len(nxt)
    all_tokens = [t for ev in history for t in ev]
    baseline = (Counter(all_tokens).most_common(1)[0][1] / len(all_tokens)) if all_tokens else 0.0
    reduction = max(0.0, accuracy - baseline)  # error-reduction proxy
    score = min(1.0, reduction / max(config["predictive_utility"]["min_error_reduction"], 1e-9))
    return score, {"accuracy": accuracy, "baseline": baseline, "reduction": reduction}


def measure_integration(pattern, sops, config) -> Tuple[float, Dict]:
    p = tuple(pattern)
    conflicts = 0
    for sop in sops:
        sp = tuple(sop)
        if p == sp:
            continue
        # a strict-prefix of an existing SOP is a competing/ambiguous rule
        if len(p) < len(sp) and sp[:len(p)] == p:
            conflicts += 1
    complexity = min(1.0, len(p) / 20.0)
    if conflicts > config["integration"]["max_conflicts_with_sops"]:
        score = 0.0  # hard veto (handled by caller too)
    else:
        score = 1.0 - complexity
    return score, {"conflicts": conflicts, "complexity": complexity}


def compute_meaning_score(pattern, history, sops=None, config=None) -> Dict[str, Any]:
    """Weighted meaning score + diagnostics + promote flag. Non-conflicting only."""
    config = config or DEFAULT_CONFIG
    sops = list(sops or [])
    w = config["weights"]
    stab, sd = measure_stability(pattern, history, config)
    comp, cd = measure_compression(pattern, history, config)
    pred, pd = measure_predictive_utility(pattern, history, config)
    integ, idd = measure_integration(pattern, sops, config)
    veto = idd["conflicts"] > config["integration"]["max_conflicts_with_sops"]
    score = 0.0 if veto else (
        w["stability"] * stab + w["compression"] * comp +
        w["predictive_utility"] * pred + w["integration"] * integ)
    return {
        "score": round(score, 4),
        "veto": veto,
        "promote": (not veto) and score >= config["promotion_threshold"],
        "axes": {"stability": round(stab, 4), "compression": round(comp, 4),
                 "predictive_utility": round(pred, 4), "integration": round(integ, 4)},
        "diagnostics": {"stability": sd, "compression": cd,
                        "predictive_utility": pd, "integration": idd},
        "threshold": config["promotion_threshold"],
    }
