"""Identity tests — self-model, operator boundary, accretion, persistence."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bdi_fsm.identity import Identity


def test_identity_has_axioms_and_boundary():
    d = tempfile.mkdtemp(prefix="bdi_id_")
    i = Identity(path=os.path.join(d, "id.json"))
    assert len(i.axioms) >= 3
    self_report = i.who_am_i()
    assert "axioms" in self_report
    assert "skills" in self_report
    assert "narrative" in self_report
    # operator is a separate boundary report
    op = i.operator_report()
    assert "likes" in op and "corrections" in op


def test_identity_master_skill_monotonic():
    d = tempfile.mkdtemp(prefix="bdi_id_")
    i = Identity(path=os.path.join(d, "id.json"))
    i.master_skill("collision_fsm", 0.4)
    i.master_skill("collision_fsm", 0.9)
    i.master_skill("collision_fsm", 0.5)  # lower should NOT decrease
    assert i.skills["collision_fsm"] == 0.9


def test_identity_feedback_counts():
    d = tempfile.mkdtemp(prefix="bdi_id_")
    i = Identity(path=os.path.join(d, "id.json"))
    i.feedback(True)
    i.feedback(True)
    i.feedback(False)
    i.record_correction("flagged_wrong")
    s = i.stats()
    assert s["operator_likes"] == 2
    assert s["operator_dislikes"] == 1
    assert s["operator_corrections"] == 1


def test_identity_persists_across_instances():
    d = tempfile.mkdtemp(prefix="bdi_id_")
    p = os.path.join(d, "id.json")
    i = Identity(path=p)
    i.master_skill("markov_plateau", 0.7)
    i.learn_fact("repo", "BDI_FSM_AGENT")
    i.feedback(True, "hello -> hi")
    i2 = Identity(path=p)
    assert i2.skills["markov_plateau"] == 0.7
    assert i2.facts["repo"] == "BDI_FSM_AGENT"
    assert i2.born_at == i.born_at


def test_identity_history_ttl_capped():
    d = tempfile.mkdtemp(prefix="bdi_id_")
    i = Identity(path=os.path.join(d, "id.json"))
    for n in range(600):
        i._narrate("event", f"event {n}")
    assert len(i.history) == 500


def test_identity_tick_increments_cycle():
    d = tempfile.mkdtemp(prefix="bdi_id_")
    i = Identity(path=os.path.join(d, "id.json"))
    i.tick(); i.tick(); i.tick()
    assert i.cycle == 3
