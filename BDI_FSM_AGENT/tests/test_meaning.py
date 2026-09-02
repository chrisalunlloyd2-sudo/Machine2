from bdi_fsm.meaning import (DEFAULT_CONFIG, compute_meaning_score,
                             measure_stability)

RELAXED = {
    "stability": {"min_occurrences": 3, "min_consistency": 0.5},
    "compression": {"min_events_explained": 5, "max_description_bits": 100},
    "predictive_utility": {"min_error_reduction": 0.05, "min_latency_improvement": 0.01},
    "integration": {"max_conflicts_with_sops": 0, "max_added_complexity_score": 0.5},
    "weights": {"stability": 0.35, "compression": 0.25,
                "predictive_utility": 0.25, "integration": 0.15},
    "promotion_threshold": 0.6,
}


def _history():
    hist = []
    for _ in range(8):
        hist.append(["deploy", "error", "rollback", "fix", "done"])
    hist += [["deploy", "success", "done"]] * 2
    return hist


def test_stable_pattern_scores_high_and_promotes():
    r = compute_meaning_score(("error", "rollback"), _history(), config=RELAXED)
    assert r["score"] >= 0.6
    assert r["promote"] is True and r["veto"] is False


def test_random_pattern_scores_low():
    r = compute_meaning_score(("banana", "pizza"), _history(), config=RELAXED)
    assert r["score"] < 0.3
    assert r["promote"] is False


def test_conflicting_pattern_hard_veto():
    sops = [("error", "rollback", "fix")]  # existing SOP
    # candidate ("error","rollback") is a strict prefix of the SOP -> conflict
    r = compute_meaning_score(("error", "rollback"), _history(),
                              sops=sops, config=RELAXED)
    assert r["veto"] is True and r["score"] == 0.0 and r["promote"] is False


def test_default_config_is_intact():
    assert DEFAULT_CONFIG["weights"]["stability"] == 0.35
    assert DEFAULT_CONFIG["promotion_threshold"] == 0.7
