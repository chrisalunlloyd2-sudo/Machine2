"""Tests for the AST-guided code patcher + Banburismus synthesis gate."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bdi_fsm.code_patcher import (
    CodePatcher, PatchOp, CodeSynthesisGate, locate_node,
)

SAMPLE = '''"""Sample service."""


class Service:
    """Doc."""

    def __init__(self):
        self.enabled = False

    def run(self, x):
        print(x)
'''


def _setup():
    d = tempfile.mkdtemp()
    p = os.path.join(d, "svc.py")
    with open(p, "w") as f:
        f.write(SAMPLE)
    return d, p


def test_insert_before_field():
    d, p = _setup()
    pat = CodePatcher(d)
    r = pat.apply(PatchOp("svc.py", "insert_before", "run",
                          "counter = 0\n"))
    assert r.ok, r.error
    src = open(p).read()
    assert "counter = 0" in src
    assert src.index("counter = 0") < src.index("def run")


def test_insert_in_method_start_nested():
    d, p = _setup()
    pat = CodePatcher(d)
    r = pat.apply(PatchOp("svc.py", "insert_in_method_start", "run",
                          "if x is None:\n    return\n"))
    assert r.ok, r.error
    src = open(p).read()
    assert "        if x is None:" in src
    assert "            return" in src


def test_replace_body_flat():
    d, p = _setup()
    pat = CodePatcher(d)
    r = pat.apply(PatchOp("svc.py", "replace_body", "__init__",
                          "self.enabled = True\nself.ready = True\n"))
    assert r.ok, r.error
    src = open(p).read()
    assert "self.enabled = True" in src
    assert "self.ready = True" in src
    assert "self.enabled = False" not in src


def test_insert_after_new_method():
    d, p = _setup()
    pat = CodePatcher(d)
    r = pat.apply(PatchOp("svc.py", "insert_after", "run",
                          'def stop(self):\n    print("stop")\n'))
    assert r.ok, r.error
    src = open(p).read()
    assert "def stop(self):" in src
    assert src.index("def run") < src.index("def stop")


def test_delete_method():
    d, p = _setup()
    pat = CodePatcher(d)
    r = pat.apply(PatchOp("svc.py", "delete", "run"))
    assert r.ok, r.error
    src = open(p).read()
    assert "def run" not in src
    assert "def __init__" in src  # other method intact


def test_reject_syntax_error_no_write():
    d, p = _setup()
    pat = CodePatcher(d)
    before = open(p).read()
    r = pat.apply(PatchOp("svc.py", "insert_before", "run", "def broken(:\n"))
    assert not r.ok
    assert "validation failed" in r.error
    assert open(p).read() == before  # workspace untouched


def test_reject_missing_node():
    d, p = _setup()
    pat = CodePatcher(d)
    r = pat.apply(PatchOp("svc.py", "insert_before", "nope", "x = 1\n"))
    assert not r.ok
    assert "node not found" in r.error


def test_reject_path_escape():
    d, p = _setup()
    pat = CodePatcher(d)
    r = pat.apply(PatchOp("../secret.py", "insert_before", "run", "x=1\n"))
    assert not r.ok
    assert "file not found" in r.error


def test_dry_run_no_write():
    d, p = _setup()
    pat = CodePatcher(d)
    before = open(p).read()
    ok, _ = pat.dry_run(PatchOp("svc.py", "insert_before", "run", "x = 1\n"))
    assert ok
    assert open(p).read() == before  # dry run wrote nothing


def test_diff_is_targeted():
    d, p = _setup()
    pat = CodePatcher(d)
    r = pat.apply(PatchOp("svc.py", "insert_before", "run", "counter = 0\n"))
    assert r.ok
    # diff is a small hunk, not a full-file re-emit
    assert r.diff.count("@@") >= 1
    assert "counter = 0" in r.diff
    assert len(r.diff.splitlines()) < len(open(p).read().splitlines())


def test_backup_created():
    d, p = _setup()
    pat = CodePatcher(d)
    r = pat.apply(PatchOp("svc.py", "insert_before", "run", "counter = 0\n"))
    assert r.ok and r.backup_path
    assert os.path.exists(r.backup_path)
    assert open(r.backup_path).read() == SAMPLE


def test_gate_apply_success():
    d, p = _setup()
    gate = CodeSynthesisGate(d, threshold_dban=20, pass_dban=30)
    dec = gate.validate_and_apply(
        PatchOp("svc.py", "insert_before", "run", "counter = 0\n"))
    assert dec.fired
    assert dec.dban >= 20  # compiler pass -> +30 dBan cleared threshold
    assert "counter = 0" in open(p).read()


def test_gate_apply_fail():
    d, p = _setup()
    gate = CodeSynthesisGate(d)
    dec = gate.validate_and_apply(
        PatchOp("svc.py", "insert_before", "run", "def broken(:\n"))
    assert not dec.fired
    assert dec.dban == float("-inf")  # contradiction -> eliminated


def test_gate_select_picks_winner():
    d, p = _setup()
    gate = CodeSynthesisGate(d, threshold_dban=20, pass_dban=30)
    # one valid, one invalid, one targeting a missing node
    cands = [
        PatchOp("svc.py", "insert_before", "nope", "x = 1\n"),       # elim
        PatchOp("svc.py", "insert_before", "run", "def broken(:\n"), # elim
        PatchOp("svc.py", "insert_before", "run", "counter = 0\n"),  # valid
    ]
    dec = gate.select(cands)
    assert dec.fired
    assert dec.hypothesis.endswith("run")  # winner targets 'run'
    assert "counter = 0" in open(p).read()


def test_locate_node_span():
    span = locate_node(SAMPLE, "run")
    assert span is not None
    assert span.kind == "FunctionDef"
    assert span.indent == 4        # method at class indent
    assert span.body_indent == 8   # body one level deeper
    assert locate_node(SAMPLE, "missing") is None


if __name__ == "__main__":
    n = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); n += 1; print(f"  {name} PASS")
    print(f"ALL code_patcher tests passed ({n})")
