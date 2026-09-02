"""Tests for the symbolic registry: tokens, bans, composition, fuzzy edges.

The properties that matter, and why each is here:

  TOKENS      stable across restarts, or a saved transition table stops meaning anything.
  BANS        measure the DIFFERENCE a pressure makes. A pressure that leads somewhere 80% of the
              time is worthless if that place happens 80% of the time anyway.
  COMPOSITION bans ADD, which is the whole reason the unit is a ban and not a probability. Three
              steps is a sum of three readable numbers rather than a product that underflows.
  FUZZY       an edge seen twice is uncertain, not absent. A crisp threshold both discards partial
              evidence AND makes n=2 and n=200 identical the instant they both pass.
"""
import math
import os
import sys
import tempfile

sys.path.insert(0, r"C:\Viper\projects\BDI_FSM_AGENT")

from bdi_fsm.symbolic import EDGE_K, SymbolicRegistry, membership


def _reg():
    return SymbolicRegistry(tempfile.mkdtemp(prefix="sym_"))


# ── tokens ───────────────────────────────────────────────────────────────────
def test_tokens_are_stable_and_unique():
    r = _reg()
    a = r.token("node", "hive")
    b = r.token("place", "hive")          # same key, different type -> different symbol
    assert a != b
    assert r.token("node", "hive") == a, "re-registering must return the same token"


def test_tokens_survive_a_save_and_reload():
    d = tempfile.mkdtemp(prefix="sym_p_")
    r1 = SymbolicRegistry(d)
    t = r1.token("thing", "email.db", weight=0.9)
    r1.observe("a", "x", "b")
    r1.save()
    r2 = SymbolicRegistry(d)
    assert r2.lookup("thing", "email.db")["token"] == t
    assert r2.transitions.get("a|x") == {"b": 1}


def test_facts_merge_rather_than_replace():
    r = _reg()
    r.token("repo", "viper", files=10)
    r.token("repo", "viper", remote="github")
    f = r.lookup("repo", "viper")["facts"]
    assert f["files"] == 10 and f["remote"] == "github"


# ── bans ─────────────────────────────────────────────────────────────────────
def test_a_pressure_that_changes_nothing_scores_about_zero():
    """If `end` happens just as often without the pressure, the pressure taught us nothing."""
    r = _reg()
    for _ in range(50):
        r.observe("s", "x", "e")
        r.observe("s", "y", "e")
    out = r.apply("s", "x")
    assert out["ok"]
    assert abs(out["bans_raw"]) < 0.05, out


def test_a_pressure_that_determines_the_outcome_scores_positive():
    r = _reg()
    for _ in range(40):
        r.observe("s", "x", "e1")     # x always -> e1
        r.observe("s", "y", "e2")     # y always -> e2
    out = r.apply("s", "x")
    assert out["end"] == "e1"
    assert out["bans_raw"] > 0.25, out


def test_unobserved_pressure_is_refused_not_guessed():
    r = _reg()
    r.observe("s", "x", "e")
    out = r.apply("s", "never_seen")
    assert not out["ok"]
    assert out["observations"] == 0


# ── fuzzy edges ──────────────────────────────────────────────────────────────
def test_membership_rises_smoothly_and_never_reaches_one():
    prev = -1.0
    for n in (1, 2, 3, 5, 10, 100, 1000):
        m = membership(n)
        assert 0 < m < 1, (n, m)
        assert m > prev, "membership must increase with evidence"
        prev = m
    assert membership(0) == 0.0
    assert abs(membership(EDGE_K) - 0.5) < 1e-9, "n == k is the half-way point"


def test_evidence_discounts_a_thinly_observed_edge():
    # The two pressures must lead to DIFFERENT ends, or neither carries information and both raw
    # scores are correctly zero — which is a true statement about the data and a useless fixture.
    r = _reg()
    for _ in range(2):
        r.observe("s", "thin", "rare_end")
    for _ in range(200):
        r.observe("s", "thick", "common_end")
    thin, thick = r.apply("s", "thin"), r.apply("s", "thick")
    assert thin["bans_raw"] > 0 and thick["bans_raw"] > 0, (thin, thick)
    assert thin["support"] < thick["support"]
    assert thin["bans"] < thin["bans_raw"], "a thin edge must be discounted"
    assert abs(thick["bans"] - thick["bans_raw"]) < 0.05, "a thick edge is barely touched"


def test_raw_score_is_always_reported_so_the_discount_cannot_hide_it():
    r = _reg()
    r.observe("s", "x", "e")
    out = r.apply("s", "x")
    assert "bans_raw" in out and "support" in out and "bans" in out


def test_a_lucky_thin_edge_cannot_outrank_a_solid_one():
    """The inversion a crisp threshold allowed: past the line, n=3 counted like n=300."""
    r = _reg()
    # thin edge, perfectly predictive, seen 3 times
    for _ in range(3):
        r.observe("s", "lucky", "rare")
    # solid edge, strongly predictive, seen 100 times
    for _ in range(100):
        r.observe("s", "solid", "common")
    for _ in range(40):
        r.observe("s", "other", "common")
        r.observe("s", "other2", "rare")
    lucky, solid = r.apply("s", "lucky"), r.apply("s", "solid")
    assert lucky["support"] < solid["support"]


# ── composition: a + b + c = d ───────────────────────────────────────────────
def _abc(r):
    for _ in range(30):
        r.observe("a", "x", "b")
        r.observe("b", "y", "c")
        r.observe("c", "z", "d")
    return r


def test_bans_add_across_a_chain():
    r = _abc(_reg())
    ch = r.chain("a", ["x", "y", "z"])
    assert ch["ok"] and ch["end"] == "d"
    assert abs(ch["bans"] - sum(s["bans"] for s in ch["steps"])) < 1e-6, "bans must sum"


def test_a_path_never_observed_as_a_path_still_composes():
    """The compression: store small steps, answer about paths nobody walked."""
    r = _abc(_reg())
    assert "a|x" in r.transitions and "b|y" in r.transitions
    assert not any(k.startswith("a|") and "z" in k for k in r.transitions)
    assert r.chain("a", ["x", "y", "z"])["end"] == "d"


def test_chain_support_is_the_weakest_link_not_the_average():
    r = _reg()
    for _ in range(200):
        r.observe("a", "x", "b")
    for _ in range(2):
        r.observe("b", "y", "c")      # the shaky step
    ch = r.chain("a", ["x", "y"])
    assert ch["ok"]
    weakest = min(s["support"] for s in ch["steps"])
    assert abs(ch["support"] - weakest) < 1e-9
    assert ch["support"] < 0.5, "one thin edge must drag the whole path down"


def test_chain_stops_honestly_and_says_where():
    r = _abc(_reg())
    ch = r.chain("a", ["x", "not_a_real_pressure", "z"])
    assert not ch["ok"]
    assert ch["stopped_at"] == "not_a_real_pressure"
    assert ch["end"] == "b", "it must report how far it actually got"


def test_composed_label_reads_as_the_trail():
    r = _abc(_reg())
    assert r.chain("a", ["x", "y", "z"])["composed"] == "a.x.y.z"


# ── inverse query ────────────────────────────────────────────────────────────
def test_evidence_for_answers_what_should_i_apply():
    r = _reg()
    for _ in range(50):
        r.observe("s", "right", "goal")
        r.observe("s", "wrong", "elsewhere")
    ev = r.evidence_for("s", "goal")
    assert ev and ev[0]["pressure"] == "right"


# ── grounding: measured is not the same as wanted ────────────────────────────
# Chris: "a solution to 'my file isn't loading' can't be 'delete file'. It's a solution, but not
# the one we want." The registry is an optimiser with a target and no grounding, so this is the
# exact shape of answer it would otherwise give — and give confidently, because it is not wrong.
from bdi_fsm.symbolic import is_destructive


def _file_wont_load():
    r = _reg()
    for _ in range(40):
        r.observe("file_wont_load", "delete_file", "resolved")    # works. always.
        r.observe("file_wont_load", "fix_encoding", "resolved")   # also works
        r.observe("file_wont_load", "check_perms", "still_broken")
    return r


def test_delete_is_never_recommended_even_when_it_scores_identically():
    r = _file_wont_load()
    ev = r.evidence_for("file_wont_load", "resolved")
    ranked = [e for e in ev if "pressure" in e]
    assert ranked, ev
    assert all(e["pressure"] != "delete_file" for e in ranked), ranked
    assert ranked[0]["pressure"] == "fix_encoding"


def test_the_withheld_route_is_reported_not_hidden():
    """Silently dropping it would be its own dishonesty — a person asking by name deserves it."""
    ev = _file_wont_load().evidence_for("file_wont_load", "resolved")
    held = [e for e in ev if "withheld_count" in e]
    assert held and held[0]["withheld_count"] == 1
    assert held[0]["withheld"][0]["pressure"] == "delete_file"


def test_it_scored_just_as_well_which_is_the_whole_point():
    """The constraint is not a score. If it were, evidence could out-argue it."""
    r = _file_wont_load()
    ev = r.evidence_for("file_wont_load", "resolved", allow_destructive=True)
    ranked = {e["pressure"]: e["bans"] for e in ev if "pressure" in e}
    assert abs(ranked["delete_file"] - ranked["fix_encoding"]) < 1e-9


def test_destructive_routes_are_still_recorded():
    # Hiding the observation would corrupt the baseline every other edge is measured against.
    r = _file_wont_load()
    assert r.transitions["file_wont_load|delete_file"] == {"resolved": 40}


def test_the_heuristic_catches_the_usual_suspects():
    for p in ("delete_file", "rm_cache", "purge_db", "wipe_state", "force_push_main",
              "reset_hard", "truncate_table", "revert_commit"):
        assert is_destructive(p), p
    for p in ("fix_encoding", "check_perms", "build", "run_tests", "wire_bridge"):
        assert not is_destructive(p), p


def test_an_explicit_fact_overrides_the_name_in_both_directions():
    # Heuristics are wrong sometimes; a declared fact must win either way.
    assert is_destructive("delete_file", {"destructive": False}) is False
    assert is_destructive("build", {"destructive": True}) is True


# ── resource pressures: the transition cannot see what they did ──────────────
# Chris: "like 'please mmap this' — do mem options trigger instant test thoughts?"
# Yes, and it is a different class from destructive. Destructive is REFUSED. A resource pressure
# is allowed; it just cannot be judged by bans, because its consequence arrives minutes later and
# lands on some other cell's deadline.
from bdi_fsm.symbolic import needs_immediate_test


def test_memory_options_demand_an_immediate_measurement():
    for p in ("use_mmap", "no_mmap", "num_thread_1", "set_num_ctx", "max_loaded_models",
              "keep_alive", "batch_size", "rlimit_as", "cpu_affinity"):
        assert needs_immediate_test(p), p


def test_ordinary_work_does_not():
    for p in ("fix_encoding", "run_tests", "build_gui", "wire_bridge", "restart_server"):
        assert not needs_immediate_test(p), p


def test_the_flag_rides_on_the_result_where_a_caller_must_step_over_it():
    """A caller that reads `bans` and acts is the whole risk; a log line would not reach it."""
    r = _reg()
    for _ in range(30):
        r.observe("llm_slow", "use_mmap", "llm_ok")
        r.observe("llm_slow", "restart_server", "llm_ok")
    mem, plain = r.apply("llm_slow", "use_mmap"), r.apply("llm_slow", "restart_server")
    assert mem.get("verify_now") is True
    assert "why_verify" in mem
    assert "verify_now" not in plain


def test_bans_genuinely_cannot_tell_them_apart_which_is_the_point():
    r = _reg()
    for _ in range(30):
        r.observe("llm_slow", "use_mmap", "llm_ok")
        r.observe("llm_slow", "restart_server", "llm_ok")
    mem, plain = r.apply("llm_slow", "use_mmap"), r.apply("llm_slow", "restart_server")
    assert abs(mem["bans"] - plain["bans"]) < 1e-9, "identical evidence, different class"


def test_a_declared_fact_overrides_the_name():
    assert needs_immediate_test("build", {"resource": True}) is True
    assert needs_immediate_test("use_mmap", {"resource": False}) is False


def test_a_pressure_can_be_both_destructive_and_resource():
    assert is_destructive("clear_cache") and needs_immediate_test("clear_cache")
