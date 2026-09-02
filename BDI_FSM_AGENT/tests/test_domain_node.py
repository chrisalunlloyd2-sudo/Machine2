"""Tests for the domain node (environment boundary + Bayesian intersection)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bdi_fsm.domain_node import DomainSpec, DomainGate, SymbolMapper, IntersectionSynthesizer
from bdi_fsm.android_domain import ANDROID_SPEC, AndroidCodeGenerator, synthesize_android


def test_domain_gate_rejects_foreign_imports():
    g = DomainGate(ANDROID_SPEC)
    assert g.spec.allows_import("android.content.Context")
    assert g.spec.allows_import("androidx.appcompat.app.AppCompatActivity")
    assert not g.spec.allows_import("java.util.ArrayList")
    assert not g.spec.allows_import("os.system")


def test_domain_gate_prefix_boundary():
    # the startswith(pkg) bug: "android.contentEvil" must NOT be allowed
    g = DomainGate(ANDROID_SPEC)
    assert not g.spec.allows_import("android.contentEvil")
    assert g.spec.allows_import("android.content.Context")  # real subpackage OK


def test_domain_gate_commands():
    g = DomainGate(ANDROID_SPEC)
    assert g.spec.allows_command("adb_shell")
    assert not g.spec.allows_command("rm_rf_root")


def test_symbol_mapper_type_and_scope():
    m = SymbolMapper()
    m.register("A", "mContext", "Context", "Activity")
    m.register("B", "appContext", "Context", "Activity")
    m.register("A", "mBt", "BluetoothAdapter", "Activity")
    m.register("B", "mNet", "ConnectivityManager", "Activity")
    mapped = m.find_intersections()
    # only Context<->Context maps (same type + scope); Bt vs Net does not
    assert len(mapped) == 1
    a, b, score = mapped[0]
    assert a.type_hint == b.type_hint == "Context"
    assert score >= 25.0


def test_intersection_survives_only_in_both():
    s = IntersectionSynthesizer(threshold_dban=5.0)
    s.register_constructs(["X", "Y", "Z"])
    s.observe_project({"X", "Y"})   # X,Y present
    s.observe_project({"Y", "Z"})   # Y,Z present
    assert s.extract() == ["Y"]     # only Y is in BOTH


def test_intersection_scores_match_math():
    s = IntersectionSynthesizer(threshold_dban=5.0)
    s.register_constructs(["A"])
    s.observe_project({"A"})
    s.observe_project({"A"})
    import math
    expected = 2 * 10 * math.log10(0.8 / 0.3)   # two PRESENT votes
    assert abs(s.ledger.scores["A"] - expected) < 1e-6


def test_android_gate_blocks_foreign_command():
    gen = AndroidCodeGenerator()
    try:
        gen.synthesize("x", [], [], commands=["rm_rf_root"])
        assert False, "should have raised PermissionError"
    except PermissionError:
        pass


def test_end_to_end_intersection():
    code = synthesize_android(
        "init_device_manager",
        {"mContext": ("Context", "Activity")},
        {"appContext": ("Context", "Activity")},
        {"Context", "onCreate", "BluetoothAdapter"},
        {"Context", "onCreate", "ConnectivityManager"},
        commands=["adb_shell"])
    assert "unified_mContext" in code          # mapped symbol
    assert "onCreate" in code                   # shared lifecycle
    assert "BluetoothAdapter" not in code       # A-only => excluded
    assert "ConnectivityManager" not in code    # B-only => excluded
    assert "private Context" in code


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print(f"  {name} PASS")
    print("ALL domain_node tests passed")
