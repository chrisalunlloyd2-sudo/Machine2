"""Tests for the training program.

The two properties worth pinning are the ones that silently stop working:

  1. the cursor ROTATES. Without it the walk restarts at the top and stops at the cap, so the same
     files are read forever and the curriculum plateaus on pass two while reporting healthy zeros.
  2. a sealed skill MATCHES a template. Skills are keyed by flattened path and templates by
     callable name, so the link between "we proved this works" and "this is on the tape" is a
     small piece of string handling — and if it breaks, the tape simply never advances and looks
     exactly like an agent that has never succeeded.
"""
import json
import os
import tempfile

import pytest

from bdi_fsm import pedagogy
from bdi_fsm.code_templates import CodeTape


def test_cursor_advances_and_wraps():
    d = tempfile.mkdtemp(prefix="ped_cur_")
    # total 10, step 4 -> 0, 4, 8, then wraps to 2
    assert pedagogy._cursor(d, "c.json", 10, 4) == 0
    assert pedagogy._cursor(d, "c.json", 10, 4) == 4
    assert pedagogy._cursor(d, "c.json", 10, 4) == 8
    assert pedagogy._cursor(d, "c.json", 10, 4) == 2


def test_cursor_survives_a_corrupt_file():
    d = tempfile.mkdtemp(prefix="ped_cur2_")
    path = pedagogy._state_path(d, "c.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("{ not json")
    # Losing your place costs one repeated pass, never a crash.
    assert pedagogy._cursor(d, "c.json", 10, 4) == 0


def test_cursor_handles_an_empty_fleet():
    d = tempfile.mkdtemp(prefix="ped_cur3_")
    assert pedagogy._cursor(d, "c.json", 0, 4) == 0


def test_callable_name_comes_from_the_doc_not_the_flattened_key():
    # "set_vocab in scripts/convert_lora_to_gguf.py" -> set_vocab
    names = pedagogy._callable_names(
        "scripts_convert_lora_to_gguf_py",
        {"doc": "set_vocab in scripts/convert_lora_to_gguf.py",
         "name": "scripts_convert_lora_to_gguf_py"})
    assert names[0] == "set_vocab"


def test_callable_name_handles_the_signature_form():
    # "is_even(n) returns True when..." -> is_even
    names = pedagogy._callable_names(
        "is_even_py", {"doc": "is_even(n) returns True when n is divisible by two"})
    assert names[0] == "is_even"


def test_callable_name_always_offers_the_key_as_a_fallback():
    names = pedagogy._callable_names("bare_key", {})
    assert "bare_key" in names


def test_reward_floats_a_proven_template_toward_the_head():
    tape = CodeTape(os.path.join(tempfile.mkdtemp(prefix="ped_tape_"), "tape.json"))
    tape.learn([
        {"lang": "python", "kind": "function", "name": "unproven_a", "signature": "()"},
        {"lang": "python", "kind": "function", "name": "is_even", "signature": "(n)"},
        {"lang": "python", "kind": "function", "name": "unproven_b", "signature": "()"},
    ])
    assert tape.stats()["successes"] == 0
    assert tape.reward(name="is_even") is True
    assert tape.stats()["successes"] == 1
    # the winner is now at the front of the ranked candidates
    assert tape.candidates(limit=1)[0]["name"] == "is_even"


def test_reward_reports_unmatched_skills_rather_than_a_silent_zero():
    state = tempfile.mkdtemp(prefix="ped_sk_")
    skills = os.path.join(state, "skills", "skills")
    os.makedirs(skills, exist_ok=True)
    with open(os.path.join(state, "skills", "skills_index.json"), "w", encoding="utf-8") as f:
        json.dump({"nothing_matches_py": {"doc": "ghost_fn in nowhere.py"}}, f)
    tape = CodeTape(os.path.join(state, "tape.json"))
    tape.learn([{"lang": "python", "kind": "function", "name": "real_fn", "signature": "()"}])
    r = pedagogy.reward_from_skills(tape, state)
    assert r["rewarded"] == 0
    assert r["skills"] == 1
    # An unmatched skill must be NAMED. A reward signal that quietly matches nothing is
    # indistinguishable from an agent that has never succeeded.
    assert r["unmatched"] == ["nothing_matches_py"]


def test_no_sealed_skills_is_reported_honestly():
    state = tempfile.mkdtemp(prefix="ped_sk2_")
    tape = CodeTape(os.path.join(state, "tape.json"))
    r = pedagogy.reward_from_skills(tape, state)
    assert r["rewarded"] == 0
    assert "why" in r


def test_progress_reads_both_halves_without_training():
    state = tempfile.mkdtemp(prefix="ped_prog_")
    p = pedagogy.progress(state)
    assert "english" in p and "code" in p
    assert p["code"]["cells"] == 0      # empty is a real answer, not an error


def test_train_isolates_the_two_halves():
    # A broken root must not stop the pass; each half reports its own outcome.
    state = tempfile.mkdtemp(prefix="ped_iso_")
    out = pedagogy.train(state, roots=(os.path.join(state, "does_not_exist"),))
    assert "english" in out and "code" in out
    assert "error" not in out["code"]


def test_a_seal_is_credited_only_once():
    """Re-rewarding the same seal every pass turns `successes` into a pass counter.

    The tape's success count is the only evidence that a template shape works. If it grows on
    every pass regardless of whether anything new was proven, it is a number that cannot go down
    and does not correspond to anything.
    """
    state = tempfile.mkdtemp(prefix="ped_once_")
    os.makedirs(os.path.join(state, "skills", "skills"), exist_ok=True)
    with open(os.path.join(state, "skills", "skills_index.json"), "w", encoding="utf-8") as f:
        json.dump({"is_even_py": {"doc": "is_even(n) returns True", "sha256": "abc"}}, f)

    tape = CodeTape(os.path.join(state, "tape.json"))
    tape.learn([{"lang": "python", "kind": "function", "name": "is_even", "signature": "(n)"}])

    first = pedagogy.reward_from_skills(tape, state)
    assert first["rewarded"] == 1
    assert tape.stats()["successes"] == 1

    second = pedagogy.reward_from_skills(tape, state)
    assert second["rewarded"] == 0, "same seal must not be credited twice"
    assert second["new_seals"] == 0
    assert tape.stats()["successes"] == 1, "success count must not drift upward on a quiet pass"


def test_resealing_changed_code_counts_again():
    # A skill re-sealed with different content is a NEW success, not the old one.
    state = tempfile.mkdtemp(prefix="ped_reseal_")
    os.makedirs(os.path.join(state, "skills", "skills"), exist_ok=True)
    idx_path = os.path.join(state, "skills", "skills_index.json")
    tape = CodeTape(os.path.join(state, "tape.json"))
    tape.learn([{"lang": "python", "kind": "function", "name": "is_even", "signature": "(n)"}])

    with open(idx_path, "w", encoding="utf-8") as f:
        json.dump({"is_even_py": {"doc": "is_even(n) returns True", "sha256": "v1"}}, f)
    assert pedagogy.reward_from_skills(tape, state)["rewarded"] == 1

    with open(idx_path, "w", encoding="utf-8") as f:
        json.dump({"is_even_py": {"doc": "is_even(n) returns True", "sha256": "v2"}}, f)
    assert pedagogy.reward_from_skills(tape, state)["rewarded"] == 1
    assert tape.stats()["successes"] == 2
