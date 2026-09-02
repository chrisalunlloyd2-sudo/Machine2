"""Tests for FOW contracts: routing, leases, evidence, and the expiry paths.

The failure cases matter more than the happy one here. A contract system that works when everyone
behaves is not a contract system — it is a to-do list. What makes it a contract is what happens
when a holder dies, delivers late, or reaches for work that is not theirs.
"""
import os
import sys
import tempfile
import time

sys.path.insert(0, r"C:\Viper\projects\BDI_FSM_AGENT")

from bdi_fsm.contracts import Contracts, route
from bdi_fsm.fow import FOW


def _c(ttl=60):
    """A board with a LONG lease by default.

    The default was 2s, which made every test that was not about expiry depend on finishing
    within two seconds. Alone they pass in 0.13s; inside the full 437s suite the lease ran out
    between take() and deliver() and the failure looked like a contract bug. A test whose result
    depends on how busy the machine is measures the machine.

    The expiry tests pass ttl=1 explicitly, so they still test the thing they name.
    """
    return Contracts(tempfile.mkdtemp(prefix="contracts_"), ttl_seconds=ttl)


# ── routing: capability, not preference ──────────────────────────────────────
def test_build_work_goes_to_the_deterministic_agent():
    for t in ("Add AST fitness evaluator", "Add dark theme CSS for MoeGUI",
              "Implement JSON-over-stdio bridge", "Run the pedagogy suite"):
        assert route(t) == "bdi", t


def test_language_work_goes_to_the_slm():
    for t in ("Explain how the hive throttle works", "Document the plateau detector",
              "Summarise the backlog", "Draft a readme"):
        assert route(t) == "slm", t


def test_judgement_and_outside_world_go_to_aegis():
    for t in ("Prioritise the remaining backlog", "Approve the deploy plan",
              "Implement GitHub auth permanent setup SOP (web OAuth)",
              "Schedule the migration"):
        assert route(t) == "aegis", t


def test_routing_is_deterministic():
    assert route("Explain the thing") == route("Explain the thing")


# ── the board ────────────────────────────────────────────────────────────────
def test_offering_is_idempotent():
    c = _c()
    assert c.offer("t1", "Add a thing")["offered"] is True
    assert c.offer("t1", "Add a thing")["offered"] is False


def test_a_todo_never_takes_a_lattice_cell():
    """Authority (repos) owns the dominating set. A todo displacing one would silently break the
    property the whole board rests on."""
    c = _c()
    for i in range(60):
        rec = c.offer("todo%d" % i, "Add feature %d" % i)
        q, r = rec["hex"]
        assert (q + 3 * r) % 7 != 0, (i, q, r)


def test_placement_is_stable_for_the_same_id():
    a, b = _c(), _c()
    assert a.offer("same", "Add x")["hex"] == b.offer("same", "Add x")["hex"]


# ── leases ───────────────────────────────────────────────────────────────────
def test_one_holder_at_a_time():
    c = _c()
    c.offer("t1", "Add a thing")
    assert c.take("bdi") is not None
    assert c.take("bdi") is None, "nothing else is available; it must not be handed out twice"


def test_a_party_is_only_offered_its_own_shape_of_work():
    c = _c()
    c.offer("t1", "Explain the detector")      # slm
    assert c.take("bdi") is None
    assert c.take("slm") is not None


def test_a_dead_holders_work_comes_back():
    c = _c(ttl=1)
    c.offer("t1", "Add a thing")
    c.take("bdi")
    assert c.available("bdi") == []
    time.sleep(1.3)
    assert [r["id"] for r in c.available("bdi")] == ["t1"], "an expired lease must return the work"


def test_a_late_deliver_after_the_lease_expired_is_refused():
    """THE ONE THAT MATTERS. The worker cannot know whether someone else redid the work."""
    c = _c(ttl=1)
    c.offer("t1", "Add a thing")
    c.take("bdi")
    time.sleep(1.3)
    r = c.deliver("t1", "bdi", ok=True, evidence="finished eventually")
    assert r["delivered"] is False
    assert "expired" in r["why"]


def test_another_party_cannot_close_your_contract():
    c = _c()
    c.offer("t1", "Explain the thing")
    c.take("slm")
    r = c.deliver("t1", "aegis", ok=True, evidence="x")
    assert r["delivered"] is False
    assert r.get("holder") == "slm"


# ── evidence ─────────────────────────────────────────────────────────────────
def test_success_requires_evidence():
    c = _c()
    c.offer("t1", "Add a thing")
    c.take("bdi")
    assert c.deliver("t1", "bdi", ok=True)["delivered"] is False
    assert c.deliver("t1", "bdi", ok=True, evidence="tests 12/12")["delivered"] is True


def test_failure_needs_no_evidence_and_returns_the_work():
    c = _c()
    c.offer("t1", "Add a thing")
    c.take("bdi")
    r = c.deliver("t1", "bdi", ok=False, evidence="")
    assert r["delivered"] is True and r["state"] == "open"
    assert [x["id"] for x in c.available("bdi")] == ["t1"]


def test_attempts_survive_a_failure():
    c = _c()
    c.offer("t1", "Add a thing")
    c.take("bdi")
    c.deliver("t1", "bdi", ok=False)
    c.take("bdi")
    assert c._read()["t1"]["attempts"] == 2


def test_history_records_who_did_what():
    c = _c()
    c.offer("t1", "Add a thing")
    c.take("bdi")
    c.deliver("t1", "bdi", ok=True, evidence="commit a1b2c3")
    h = c._read()["t1"]["history"]
    assert h[-1]["party"] == "bdi" and "a1b2c3" in h[-1]["evidence"]


def test_a_done_contract_is_not_offered_again():
    c = _c()
    c.offer("t1", "Add a thing")
    c.take("bdi")
    c.deliver("t1", "bdi", ok=True, evidence="done")
    assert c.available("bdi") == []


# ── the fow primitive itself ─────────────────────────────────────────────────
def test_release_honours_ownership():
    f = FOW(os.path.join(tempfile.mkdtemp(), "f.json"), ttl_seconds=30)
    f.claim("t", owner="aegis")
    assert f.release("t", owner="bdi") is False, "a party must not release another's claim"
    assert f.release("t", owner="aegis") is True


def test_release_treats_an_expired_claim_as_not_held():
    f = FOW(os.path.join(tempfile.mkdtemp(), "f.json"), ttl_seconds=1)
    f.claim("t", owner="bdi")
    time.sleep(1.3)
    assert f.release("t", owner="bdi") is False
    assert f.held("t") is None


def test_release_without_an_owner_still_works_for_plain_locking():
    # In-process callers use this as a lock and are correct as they are.
    f = FOW(os.path.join(tempfile.mkdtemp(), "f.json"), ttl_seconds=30)
    f.claim("t", owner="whoever")
    assert f.release("t") is True


def test_release_reason_distinguishes_the_three_failures():
    f = FOW(os.path.join(tempfile.mkdtemp(), "f.json"), ttl_seconds=1)
    assert "not held" in f.release_reason("nope")["why"]
    f.claim("t", owner="aegis")
    assert "held by aegis" in f.release_reason("t", owner="bdi")["why"]
    time.sleep(1.3)
    assert f.release_reason("t", owner="aegis").get("expired") is True
