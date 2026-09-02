"""N-retry budget: BLOCKED->give_up fires only while retries remain; when the
budget is exhausted BLOCKED is a TRUE dead-end (livelock fix, proven design)."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bdi_fsm.agent import BDIFSMAgent


def make_agent(max_retries="3"):
    env = dict(os.environ)
    env["BDI_MAX_RETRIES"] = max_retries
    old = os.environ.get("BDI_MAX_RETRIES")
    os.environ["BDI_MAX_RETRIES"] = max_retries
    try:
        return BDIFSMAgent(state_dir=tempfile.mkdtemp())
    finally:
        if old is None:
            os.environ.pop("BDI_MAX_RETRIES", None)
        else:
            os.environ["BDI_MAX_RETRIES"] = old


def test_default_budget_is_three():
    a = make_agent()
    assert a.MAX_RETRIES == 3


def test_env_configurable():
    a = make_agent("5")
    assert a.MAX_RETRIES == 5


def test_give_up_guard_blocks_when_exhausted():
    a = make_agent()
    a.fsm.state = "BLOCKED"   # give_up is a transition FROM BLOCKED
    a._current_slot = "slot_x"
    a._retries["slot_x"] = 0
    assert a.fsm.can("give_up") is True
    a._retries["slot_x"] = a.MAX_RETRIES - 1
    assert a.fsm.can("give_up") is True
    a._retries["slot_x"] = a.MAX_RETRIES
    assert a.fsm.can("give_up") is False   # true dead-end: no more retries
    a._retries["slot_x"] = a.MAX_RETRIES + 5
    assert a.fsm.can("give_up") is False


def test_blocked_edges_have_retry_guard():
    """The structural marker of the fix: BLOCKED->give_up carries a guard."""
    a = make_agent()
    _, guard = a.fsm._transitions["BLOCKED"]["give_up"]
    assert callable(guard), "BLOCKED->give_up must be guard-gated (N-retry)"


def test_resolve_slot_counts_retries_to_dead_end():
    a = make_agent("3")
    slot = "never_produces"
    results = []
    for i in range(4):
        r = a.resolve_slot(slot, "test", candidate_generator=lambda: [])
        results.append(r["state"])
    # three attempts, then the budget is gone and the slot is PARKED
    assert results == ["BLOCKED", "BLOCKED", "BLOCKED", "BLOCKED"]
    assert a._retries[slot] == 3
    parked = a.resolve_slot(slot, "test", candidate_generator=lambda: [])
    assert parked.get("retries_exhausted") is True
    # the give_up edge is now structurally blocked for this slot
    a._current_slot = slot
    a.fsm.state = "BLOCKED"
    assert a.fsm.can("give_up") is False


def test_success_resets_retry_budget():
    a = make_agent("2")
    slot = "flaky"
    for _ in range(2):
        a.resolve_slot(slot, "test", candidate_generator=lambda: [])
    assert a._retries.get(slot, 0) == 2
    # a successful resolve (recipe hit via NMCT seal) resets the counter
    a.nmct.seal(slot, "def flaky():\n    return 1\n", [{"cmd": "x", "exit_code": 0}])
    a.resolve_slot(slot, "test", candidate_generator=lambda: [])
    assert a._retries.get(slot, 0) == 0
    a._current_slot = slot
    a.fsm.state = "BLOCKED"
    assert a.fsm.can("give_up") is True


def test_plateau_give_up_unguarded():
    """PLATEAU exit keeps its give_up (soft stall recovery is not a failure
    retry — no budget consumption by design)."""
    a = make_agent()
    _, guard = a.fsm._transitions["PLATEAU"]["give_up"]
    assert guard is None
