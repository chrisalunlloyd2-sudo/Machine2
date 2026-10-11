"""ROTOR CODEC (Java) — Enigma permutation with a javac/java crib."""
import os
import shutil
import subprocess
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bdi_fsm.rotor_codec_java import (
    _render, brute_find_java, generate_java, make_java_test_fn,
    plain_enumerate_java,
)

def _jdk(exe):
    """Find a JDK binary on PATH, or under JAVA_HOME.

    shutil.which() alone was skipping these four tests on a box where the JDK
    is installed and working: JAVA_HOME points at the Android OpenJDK 21 and
    java.exe/javac.exe are right there under bin, but PATH never exported them.
    The same one-place lookup had already refused three agents every capability
    they declare (authority_map, 2026-09-09).

    A skip is the quietest possible failure -- the suite still reports green,
    and the untested code is the Java path on a box whose flagship project is
    JavaFX.
    """
    hit = shutil.which(exe)
    if hit:
        return hit
    home = os.environ.get("JAVA_HOME")
    if not home:
        return None
    for name in (exe + ".exe", exe):
        cand = os.path.join(home, "bin", name)
        if os.path.isfile(cand):
            return cand
    return None


_JAVA = _jdk("javac") is not None and _jdk("java") is not None
pytestmark = pytest.mark.skipif(not _JAVA, reason="javac/java not installed")


def _compile_ok(source: str) -> bool:
    with tempfile.TemporaryDirectory(prefix="bdi_jt_") as tmp:
        p = os.path.join(tmp, "Solver.java")
        with open(p, "w") as f:
            f.write(source)
        # Resolved, not assumed on PATH -- the same reason _jdk() exists.
        r = subprocess.run([_jdk("javac"), "Solver.java"], cwd=tmp,
                           capture_output=True, text=True)
        return r.returncode == 0


def test_generate_java_compiles():
    src = generate_java(["a * b", "a + b", "a - b"], 0)
    assert "public class Solver" in src
    assert "return " in src
    assert _compile_ok(src)


def test_java_crib_scores_correct_vs_incorrect():
    tf = make_java_test_fn([(2, 3, 6)])
    assert tf(_render("a * b")) == 1.0   # 2*3 == 6
    assert tf(_render("a + b")) == 0.0   # 2+3 == 5 != 6


def test_brute_find_java_finds_multiply():
    r = brute_find_java(["a + b", "a - b", "a * b"], [(2, 3, 6)])
    assert r["found"] is True
    assert "a * b" in r["source"]
    assert r["theta_bans"] > 0           # Nash stop reported


def test_plain_enumerate_java_finds_multiply():
    r = plain_enumerate_java(["a + b", "a - b", "a * b"], [(2, 3, 6)])
    assert r["found"] is True
    assert "a * b" in r["source"]
