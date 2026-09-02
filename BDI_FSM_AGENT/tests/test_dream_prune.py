#!/usr/bin/env python3
"""Deterministic tests for dream_prune — source coding of the decision journal."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bdi_fsm import dream_prune
from bdi_fsm.journal import DeterministicActionJournal


def _build_journal(path, actions, outcomes=None, agents=None):
    j = DeterministicActionJournal(path)
    for i, a in enumerate(actions):
        j.record(
            agent=(agents[i] if agents else "test-agent"),
            action=a,
            detail=f"step {i}",
            outcome=(outcomes[i] if outcomes else "ok"),
        )
    return j


def test_too_few_records_no_prune():
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "j.jsonl")
        _build_journal(p, ["m1", "d2", "m1", "d2", "m1", "d2", "m1"])
        r = dream_prune.dream_prune(p)
        assert r["archived"] == 0, r
        assert r["kept"] == 7, r
        assert r["reason"] == "too_few_records", r


def test_deterministic_cycle_is_compressible():
    """Alternating m1,d2,m1,d2... is a fully redundant source: keep the code only."""
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "j.jsonl")
        actions = ["m1", "d2"] * 20  # 40 records, 2-symbol cycle
        _build_journal(p, actions)
        r = dream_prune.dream_prune(p)
        assert r["reason"] == "pruned", r
        # first-seen transitions (m1->d2, d2->m1) + order prefix + tail kept
        assert r["kept"] <= 5, r
        assert r["archived"] >= 35, r
        assert r["redundancy"] > 0.8, r
        assert r["compression"] > 5.0, r
        assert r["bits_saved"] > 2.0, r
        assert r["chain_ok"] is True, r


def test_random_stream_is_incompressible():
    """Genuinely random stream (seeded PRNG): decisions are novel, almost
    nothing archived — the source carries real information."""
    import random
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "j.jsonl")
        rng = random.Random(42)
        alphabet = [f"a{i}" for i in range(12)]
        actions = [rng.choice(alphabet) for _ in range(60)]
        _build_journal(p, actions)
        r = dream_prune.dream_prune(p)
        assert r["archived"] <= 12, r  # mostly novel transitions
        assert r["redundancy"] < 0.35, r


def test_failures_never_archived():
    """Non-ok outcomes are learning events — must survive every dream."""
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "j.jsonl")
        actions = ["m1", "d2"] * 12
        outcomes = ["ok", "ok"] * 11 + ["fail", "fail"]  # 2 fails at the end
        _build_journal(p, actions, outcomes=outcomes)
        r = dream_prune.dream_prune(p)
        rows = dream_prune._load(p)
        kept_fails = [x for x in rows if x["outcome"] == "fail"]
        assert len(kept_fails) == 2, kept_fails


def test_chain_links_to_old_tail():
    """New chain's first prev_hash must equal the OLD chain's last hash."""
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "j.jsonl")
        actions = ["m1", "d2"] * 12
        _build_journal(p, actions)
        old_rows = dream_prune._load(p)
        old_last = old_rows[-1]["hash"]
        r = dream_prune.dream_prune(p)
        new_rows = dream_prune._load(p)
        assert new_rows[0]["prev_hash"] == old_last, (
            new_rows[0]["prev_hash"][:16], old_last[:16])
        assert r["prev_chain_tail"] == old_last, r


def test_new_chain_verifies():
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "j.jsonl")
        actions = ["m1", "d2"] * 12
        _build_journal(p, actions)
        old_rows = dream_prune._load(p)
        old_last = old_rows[-1]["hash"]
        dream_prune.dream_prune(p)
        ver = dream_prune._verify(p, anchor=old_last)
        assert ver["ok"] is True, ver
        assert ver["count"] == len(dream_prune._load(p))


def test_archive_preserves_original_hashes():
    """Archived records keep their ORIGINAL hash — the dream is auditable."""
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "j.jsonl")
        actions = ["m1", "d2"] * 12
        _build_journal(p, actions)
        old_rows = dream_prune._load(p)
        old_hashes = {r["hash"] for r in old_rows}
        dream_prune.dream_prune(p)
        arch = os.path.join(td, "j.jsonl.archive.jsonl")
        assert os.path.exists(arch)
        arch_rows = [json.loads(l) for l in open(arch)
                     if l.strip() and "dream_ts" not in l]
        assert len(arch_rows) == len(old_rows) - len(dream_prune._load(p))
        for r in arch_rows:
            assert r["hash"] in old_hashes, r["hash"]
        # every archived hash still verifies against its own body
        for r in arch_rows:
            body = dict(r)
            body.pop("hash", None)
            assert dream_prune._hash(r) == r["hash"]


def test_dry_run_is_non_destructive():
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "j.jsonl")
        actions = ["m1", "d2"] * 12
        _build_journal(p, actions)
        before = open(p).read()
        r = dream_prune.dream_prune(p, dry_run=True)
        after = open(p).read()
        assert before == after
        assert r["dry_run"] is True
        assert r["archived"] > 0  # dry run still reports what WOULD go


def test_appends_to_existing_archive():
    """Second dream appends to the same archive — nothing overwritten."""
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "j.jsonl")
        actions = ["m1", "d2"] * 12
        _build_journal(p, actions)
        dream_prune.dream_prune(p)
        arch = os.path.join(td, "j.jsonl.archive.jsonl")
        n1 = sum(1 for l in open(arch) if l.strip() and "dream_ts" not in l)
        # rebuild a fresh cycle and dream again
        _build_journal(p, actions)
        dream_prune.dream_prune(p)
        n2 = sum(1 for l in open(arch) if l.strip() and "dream_ts" not in l)
        assert n2 > n1, (n1, n2)


def test_report_fields_present():
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "j.jsonl")
        actions = ["m1", "d2"] * 12
        _build_journal(p, actions)
        r = dream_prune.dream_prune(p)
        for k in ("count", "kept", "archived", "redundancy",
                  "compression", "bits_saved", "chain_ok", "archive_path"):
            assert k in r, k
        txt = dream_prune.format_report(r)
        assert "DREAM-PRUNE" in txt
        assert "archived" in txt


def test_keep_threshold_sensitivity():
    """Higher threshold = more aggressive pruning (more archived)."""
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "j.jsonl")
        # partially noisy stream: mostly m1->d2 but with a few surprises
        actions = ["m1", "d2", "m1", "d2", "m1", "x7", "m1", "d2",
                   "m1", "d2", "m1", "d2", "m1", "x7", "m1", "d2",
                   "m1", "d2", "m1", "d2", "m1", "x7", "m1", "d2"] * 2
        _build_journal(p, actions)
        r_loose = dream_prune.dream_prune(p, dry_run=True, keep_threshold=0.1)
        r_tight = dream_prune.dream_prune(p, dry_run=True, keep_threshold=0.9)
        assert r_tight["archived"] >= r_loose["archived"], (r_loose, r_tight)


def test_rechain_consistency():
    """rechain() must produce a valid chain from genesis when prev is genesis."""
    rows = [
        {"seq": 1, "action": "a", "outcome": "ok"},
        {"seq": 2, "action": "b", "outcome": "ok"},
        {"seq": 3, "action": "a", "outcome": "fail"},
    ]
    import hashlib
    genesis = hashlib.sha256(b"GENESIS").hexdigest()
    chained = dream_prune.rechain(rows, genesis)
    assert chained[0]["prev_hash"] == genesis
    for i in range(1, len(chained)):
        assert chained[i]["prev_hash"] == chained[i - 1]["hash"]
    for r in chained:
        assert dream_prune._hash(r) == r["hash"]


ALL = [v for k, v in sorted(globals().items()) if k.startswith("test_")]


def run_all():
    passed = 0
    for t in ALL:
        t()
        passed += 1
        print(f"  ok {t.__name__}")
    print(f"\n{passed}/{len(ALL)} dream-prune tests passed")
    return passed


if __name__ == "__main__":
    raise SystemExit(0 if run_all() == len(ALL) else 1)
