"""Language-organized code vault + never-code-twice (timestamped) + never-
mistake-twice (step recorder) tests. Deterministic, no network."""
import tempfile

from bdi_fsm.langdetect import detect_language
from bdi_fsm.nmct import NMCT
from bdi_fsm.nmtd import NMTD
from bdi_fsm.lang_db import LangDB


def test_detect_language_by_extension():
    assert detect_language(filename="foo.py") == "python"
    assert detect_language(filename="foo.java") == "java"
    assert detect_language(filename="foo.rs") == "rust"
    assert detect_language(filename="foo.go") == "go"


def test_detect_language_by_code():
    assert detect_language(code="def f():\n    return 1") == "python"
    assert detect_language(code="public static void main(String[] a){}") == "java"
    assert detect_language(code="fn main() { let mut x = 1; }") == "rust"
    assert detect_language(code="#include <stdio.h>\nint main(){printf();}") == "cpp"


def test_detect_language_unknown_is_explicit():
    assert detect_language(code="xyzzy plugh thud") == "unknown"


def test_nmct_seal_is_timestamped_and_language_tagged():
    v = NMCT(tempfile.mkdtemp())
    e = v.seal("slot_x", "def f():\n    return 1", [], language="python")
    assert "ts" in e
    assert e["language"] == "python"
    # auto-detect when language omitted
    e2 = v.seal("slot_y", "public static void main(String[] a){}", [])
    assert e2["language"] == "java"


def test_nmct_by_language_and_languages():
    v = NMCT(tempfile.mkdtemp())
    v.seal("a", "def f():\n    return 1", [], language="python")
    v.seal("b", "public static void main(String[] a){}", [], language="java")
    assert set(v.languages()) == {"python", "java"}
    assert len(v.by_language("python")) == 1
    assert len(v.by_language("java")) == 1
    assert v.by_language("rust") == []


def test_nmct_never_code_twice():
    v = NMCT(tempfile.mkdtemp())
    code = "def f():\n    return 42"
    v.seal("slot", code, [])
    assert v.verify(code) is True
    assert v.verify("def f():\n    return 43") is False


def test_nmtd_step_recorder_never_mistake_twice():
    n = NMTD(tempfile.mkdtemp())
    step = "transpile:java:rotor_codec"
    assert n.check_step(step) is None
    rec = n.record_step(step, "missing semicolon", language="java")
    assert rec["step_id"].startswith("STEP-")
    # the gate now blocks a retry of the same step
    hit = n.check_step(step)
    assert hit is not None
    assert hit["language"] == "java"
    assert n.step_count() == 1


def test_nmtd_steps_do_not_pollute_incidents():
    n = NMTD(tempfile.mkdtemp())
    n.record("slot", "scope", ["A"], "boom error", [])
    n.record_step("run:python:x", "failed", language="python")
    assert n.count() == 1            # only the incident
    assert n.step_count() == 1       # only the step
    assert len(n.list_incidents()) == 1


def test_langdb_unified_index():
    d = tempfile.mkdtemp()
    v = NMCT(d + "/vault")
    n = NMTD(d + "/db")
    v.seal("py1", "def f():\n    return 1", [], language="python")
    v.seal("java1", "public static void main(String[] a){}", [], language="java")
    n.record_step("run:python:tests", "fail", language="python")
    db = LangDB(nmct=v, nmtd=n)
    assert set(db.languages()) == {"python", "java"}
    stats = db.stats()
    assert stats["python"] == 2   # 1 code + 1 step
    assert stats["java"] == 1
    kinds = {e["kind"] for e in db.by_language("python")}
    assert kinds == {"code", "step"}
