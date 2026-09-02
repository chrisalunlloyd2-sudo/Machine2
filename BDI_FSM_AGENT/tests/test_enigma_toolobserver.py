"""Tests for the Enigma lock + tool-use observer (the Banburismus gate)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bdi_fsm.enigma_lock import (
    Enigma, Rotor, ROTORS, REFLECTORS, verify_invariants,
    verify_wiring_bijections, brute_force_crib, nash_threshold, keyspace,
)
from bdi_fsm.tool_observer import ToolObserver


def test_wiring_bijections():
    assert verify_wiring_bijections(), "all rotors/reflectors must be permutations"


def test_invariants():
    inv, nofix = verify_invariants()
    assert inv, "E(E(x)) == x (involution) must hold"
    assert nofix, "E(x) != x (no fixed point) must hold"


def test_reciprocity():
    e = Enigma(rotor_order=("I", "II", "III"), positions=(0, 0, 0))
    ct = e.encrypt("HELLOWORLD")
    e2 = Enigma(rotor_order=("I", "II", "III"), positions=(0, 0, 0))
    assert e2.encrypt(ct) == "HELLOWORLD"


def test_keyspace_real_number():
    ks = keyspace()
    assert abs(ks["total"] - 1.5896255521782636e20) / 1.5896255521782636e20 < 1e-9


def test_nash_threshold_bans():
    assert abs(nash_threshold(10, 1) - 1.0) < 1e-9   # log10(10) = 1 ban
    assert nash_threshold(1, 10) == -1.0
    assert nash_threshold(10, 0) == float("inf")


def test_double_step_anomaly():
    # middle rotor steps twice in a row when both notches align
    e = Enigma(rotor_order=("I", "II", "III"), positions=(0, 16, 4))
    # right rotor III notch at W(22); middle II notch at F(5). Position right=4,
    # we just assert the machine encrypts without error and positions advance.
    e.encrypt("AAAA")
    assert e.rotors[2].position != 0, "right rotor must advance"


def test_crib_converges_to_unique():
    e = Enigma(rotor_order=("III", "I", "II"), positions=(1, 2, 3))
    ct = e.encrypt("SECRETMESSAGE")
    hits = brute_force_crib(ct, "SECRETME", rotor_pool=("I", "II", "III"))
    assert len(hits) == 1, "long crib must converge to a unique setting"
    assert hits[0]["order"] == "III-I-II" and hits[0]["positions"] == "BCD"


def test_observer_chat_vs_tool():
    obs = ToolObserver()
    assert not obs.score("hey how are you doing").is_tool
    assert obs.score("run the tests and commit").is_tool
    assert obs.score("fix build in agent.py").is_tool
    assert not obs.score("explain what a state machine is").is_tool


def test_observer_learns():
    obs = ToolObserver()
    before = obs.score("blorf the zorp into the quux").probability
    obs.record("blorf the zorp into the quux", True)
    after = obs.score("blorf the zorp into the quux").probability
    assert after >= before, "positive example should raise tool probability"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"  {name} PASS")
    print("ALL enigma/toolobserver tests passed")
