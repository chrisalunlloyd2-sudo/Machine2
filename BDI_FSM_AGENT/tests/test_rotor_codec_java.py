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

_JAVA = shutil.which("javac") is not None and shutil.which("java") is not None
pytestmark = pytest.mark.skipif(not _JAVA, reason="javac/java not installed")


def _compile_ok(source: str) -> bool:
    with tempfile.TemporaryDirectory(prefix="bdi_jt_") as tmp:
        p = os.path.join(tmp, "Solver.java")
        with open(p, "w") as f:
            f.write(source)
        r = subprocess.run(["javac", "Solver.java"], cwd=tmp,
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
