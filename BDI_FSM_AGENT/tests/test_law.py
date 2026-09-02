from bdi_fsm.law import Law, CORE_LAW, BRIDGE_RULE, is_secret_path


def test_law_is_complete():
    assert len(CORE_LAW) == 7
    assert len(BRIDGE_RULE) == 6


def test_secret_read_blocked():
    lw = Law()
    r = lw.check("read", target="~/.aws/credentials")
    assert r["verdict"] == "BLOCKED"
    assert is_secret_path("id_rsa")


def test_blind_edit_blocked():
    lw = Law()
    r = lw.check("edit", target=None)  # no target, no content
    assert r["verdict"] == "BLOCKED"


def test_delete_gate_closed_by_default():
    lw = Law()
    assert lw.check("delete", target="good_state.json")["verdict"] == "BLOCKED"
    lw2 = Law(allow_delete=True)
    assert lw2.check("delete", target="good_state.json")["verdict"] == "ALLOWED"


def test_unfenced_exec_blocked():
    lw = Law(sandbox=False)
    assert lw.check("exec", target="run.sh")["verdict"] == "BLOCKED"


def test_promotion_requires_proof_and_gate():
    lw = Law()
    assert lw.check("promote", target="v0.4.0")["verdict"] == "BLOCKED"  # no proof
    lw2 = Law(allow_promote=True)
    ok = lw2.check("promote", target="v0.4.0", proof={"tests": 521})
    assert ok["verdict"] == "ALLOWED"


def test_every_action_logged_and_hashed():
    lw = Law()
    lw.check("edit", target="a.py", content="x = 1")
    lw.check("read", target="notes.md")
    assert len(lw.ledger) == 2
    # every record carries a hash field; the edit (with content) is hashed
    assert all("hash" in r for r in lw.ledger)
    assert lw.ledger[0]["hash"] != ""
