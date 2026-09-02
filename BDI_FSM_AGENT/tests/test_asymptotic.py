import json, os, tempfile
from bdi_fsm.asymptotic import (find_knee, effectiveness_curve, prune_to_knee,
                                corpus_line_values, prune_corpus)


def test_knee_steep_then_flat():
    # one dominant item, long low-value tail
    assert find_knee([100, 1, 1, 1, 1]) == 1


def test_knee_uniform_keeps_all():
    # no diminishing returns -> keep everything
    assert find_knee([1, 1, 1, 1, 1]) == 5


def test_curve_retains_most_value():
    c = effectiveness_curve([100, 1, 1, 1, 1])
    # keeping 1 of 5 items retains ~96% of value
    assert c["retained_value"] > 0.9


def test_prune_to_knee_generic():
    items = ["rare", "rare", "common", "common", "common"]
    r = prune_to_knee(items, lambda s: 10.0 if s == "rare" else 1.0)
    assert len(r["kept"]) >= 1
    assert set(r["archived"]).issubset({"common"})
    # keeping 40% of items retains 87% of value (value >> fraction)
    assert r["retained_value"] >= 0.8
    assert r["retained_value"] > r["retained_fraction"]


def test_prune_corpus_add_only():
    # corpus ABOVE the 500-line floor so the knee is expressible (the floor
    # caps at min(min_lines, len(raw)): a tiny corpus is kept whole by design)
    with tempfile.TemporaryDirectory() as td:
        cp = os.path.join(td, "c.jsonl")
        lines = []
        for i in range(20):
            lines.append(json.dumps({"text": f"zebra quokka wombat aardvark {i}"}))  # rare tokens
        for i in range(500):
            lines.append(json.dumps({"text": f"the cat sat on the mat {i}"}))        # common
        with open(cp, "w") as f:
            for ln in lines:
                f.write(ln + "\n")
        r = prune_corpus(cp, dry_run=False)
        assert r["archived"] >= 1
        # archived lines preserved verbatim (ADD-only, never deleted)
        with open(cp + ".archive.jsonl") as f:
            archive = f.read()
        assert "the cat sat on the mat" in archive
        # kept corpus still has the rare-token line
        with open(cp) as f:
            kept = f.read()
        assert "zebra quokka" in kept


def test_corpus_values_rare_scores_higher():
    vals = corpus_line_values(["zebra quokka wombat", "the the the the", "cat sat"])
    assert vals[0] > vals[1] and vals[0] > vals[2]


def test_world_archived_persists():
    from bdi_fsm.world_model import WorldModel
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "wm.json")
        wm = WorldModel(state_path=p)
        wm.observe("server", "host1", {f"attr{i}": f"val{i}" for i in range(8)})
        # attr0 observed 3 more times -> higher utility -> the only "keeper"
        for _ in range(3):
            wm.observe("server", "host1", {"attr0": "val0"})
        wm.prune_to_optimum(dry_run=False)
        wm.save()
        wm2 = WorldModel(state_path=p)
        dag = wm2.entity("server", "host1")
        assert dag.archived, "archived nodes must persist across save/load (never lost)"
        assert "attr0" in dag.nodes        # the high-utility keeper survives live
        assert any("attr1" in k for k in dag.archived)  # low-utility tail archived


def test_prune_cooldown_skips_recent_prune(tmp_path):
    """Anti compound-prune: a fresh archive suppresses another prune."""
    from bdi_fsm.asymptotic import prune_corpus
    cp = tmp_path / "chat_corpus.jsonl"
    lines = [json.dumps({"text": f"token_a token_{i} " + " ".join(f"w{j}" for j in range(30))})
             for i in range(60)]
    cp.write_text("\n".join(lines) + "\n")
    # first prune: no archive yet -> asymptotic_knee
    r1 = prune_corpus(str(cp), dry_run=True)
    assert r1["reason"] == "asymptotic_knee"
    # simulate a real prune by writing the archive now
    ap = tmp_path / "chat_corpus.jsonl.archive.jsonl"
    ap.write_text("\n".join(lines[:30]) + "\n")
    # second prune within cooldown -> skip, keep everything
    r2 = prune_corpus(str(cp), dry_run=True)
    assert r2["reason"] == "cooldown_skip"
    assert r2["kept"] == 60 and r2["archived"] == 0
    # cooldown=0 disables the guard (archive age always >= 0)
    r3 = prune_corpus(str(cp), dry_run=True, cooldown_hours=0)
    assert r3["reason"] == "asymptotic_knee"


def test_prune_corpus_rejects_degenerate_knee():
    """Heartbeat 2026-08-16 regression: a corpus whose knee-prune would
    discard more than half the REMAINING information value (spurious knee on
    an already-pruned set) must NOT be pruned — the knee is an artifact, not
    an asymptote. Floor alone (500) is insufficient: the floored cut keeps
    only ~45% of value here."""
    with tempfile.TemporaryDirectory() as td:
        cp = os.path.join(td, "deg.jsonl")
        lines = []
        # head: 19 lines of high-value rare content (the "already-pruned" core)
        for i in range(19):
            toks = " ".join(f"rare{i}_{j}" for j in range(15))
            lines.append(json.dumps({"text": toks}))
        # tail: 1425 near-uniform lines (what a degenerate re-prune would shave)
        for i in range(1425):
            lines.append(json.dumps({"text": f"the cat sat on the mat again {i}"}))
        with open(cp, "w") as f:
            for ln in lines:
                f.write(ln + "\n")
        r = prune_corpus(cp, dry_run=False)
        assert r["archived"] == 0, f"degenerate knee must not prune, got {r}"
        assert r["kept"] == len(lines), f"corpus must stay intact, got {r}"
        with open(cp) as f:
            assert len([ln for ln in f if ln.strip()]) == len(lines)
        # no archive written either (nothing archived)
        assert not os.path.exists(cp + ".archive.jsonl") or r["reason"] == "degenerate_knee"
