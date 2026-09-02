"""ROTOR CODEC — JAVA crib. Same Enigma permutation, different filter.

The rotor (bijective key -> candidate) is language-agnostic; only the CRIB
changes. Python = exec + compare. Java = javac compile + java run + compare
stdout against expected output.

  enumerator  = rotor_permutation   (shared with rotor_codec.py)
  crib        = compile + run       (javac gate + stdout compare)
  stop        = nash_threshold      (log10(C_miss/C_false))
  fallback    = plain_enumerate_java (no-fail brute foundry)

NO LLM. Deterministic. Symbolic.
"""
import os
import subprocess
import tempfile
from typing import Callable, Dict, Sequence, Tuple

from .enigma_lock import nash_threshold
from .rotor_codec import _normalize, rotor_permutation

# Self-contained Java program whose calc() body is the rotor-chosen fragment.
# __FRAGMENT__ is replaced verbatim (no brace-escaping footguns from .format).
CLASS_SKELETON = """\
public class Solver {
    public static int calc(int a, int b) {
        return __FRAGMENT__;
    }
    public static void main(String[] args) {
        int a = Integer.parseInt(args[0]);
        int b = Integer.parseInt(args[1]);
        System.out.println(calc(a, b));
    }
}
"""


def _render(fragment: str) -> str:
    return CLASS_SKELETON.replace("__FRAGMENT__", fragment)


def generate_java(grammar: Sequence[str], key: int) -> str:
    """Assemble a full Java class whose calc() body is the rotor-chosen fragment.

    v1 = single-expression body (the rotor picks WHICH fragment). Composition is
    intentionally deferred so every generated program is trivially compilable —
    the Java analog of rotor_codec.generate_program.
    """
    perm = rotor_permutation(len(grammar), key)
    return _render(grammar[perm[0]])


def make_java_test_fn(cases: Sequence[Tuple[int, int, int]],
                      timeout: int = 20) -> Callable[[str], float]:
    """Return test_fn(source) -> float: compile + run against cases, fraction passed.

    cases = [(a, b, expected_int), ...]. The crib is DEFINITIVE: every case must
    match (score 1.0) for the candidate to be accepted.
    """
    def test_fn(source: str) -> float:
        with tempfile.TemporaryDirectory(prefix="bdi_javac_") as tmp:
            src_path = os.path.join(tmp, "Solver.java")
            with open(src_path, "w", encoding="utf-8") as f:
                f.write(source)
            try:
                cp = subprocess.run(["javac", "Solver.java"], cwd=tmp,
                                    capture_output=True, text=True, timeout=timeout)
            except Exception:
                return 0.0
            if cp.returncode != 0:
                return 0.0
            passed = 0
            for a, b, expected in cases:
                try:
                    rp = subprocess.run(["java", "-cp", tmp, "Solver",
                                         str(a), str(b)],
                                        capture_output=True, text=True,
                                        timeout=timeout)
                    if rp.returncode == 0 and rp.stdout.strip() == str(expected):
                        passed += 1
                except Exception:
                    pass
            return passed / len(cases) if cases else 0.0
    return test_fn


def brute_find_java(grammar: Sequence[str],
                    cases: Sequence[Tuple[int, int, int]],
                    max_keys: int = 20000,
                    c_miss: float = 10.0, c_false: float = 1.0,
                    patience: int = 60) -> Dict:
    """Brute-force rotor keys until the Java crib (compile + run) is matched.

    Mirrors rotor_codec.brute_find with the javac/java crib. Returns theta* in
    bans (nash_threshold) so the caller sees the commit-vs-keep-searching stop.
    """
    test_fn = make_java_test_fn(cases)
    theta_bans = nash_threshold(c_miss, c_false)
    seen = set()
    best = None
    stagnant = 0
    attempts = 0
    for key in range(max_keys):
        src = generate_java(grammar, key)
        if src in seen:
            continue
        seen.add(src)
        attempts += 1
        score = _normalize(test_fn(src))
        if score >= 1.0:
            return {"found": True, "source": src, "key": key,
                    "attempts": attempts, "score": 1.0,
                    "theta_bans": theta_bans, "reason": "crib matched"}
        if best is None or score > best["score"]:
            best = {"source": src, "key": key, "score": score}
            stagnant = 0
        else:
            stagnant += 1
        if stagnant >= patience:
            return {"found": False, "best": best, "attempts": attempts,
                    "theta_bans": theta_bans, "reason": "plateau"}
    return {"found": False, "best": best, "attempts": attempts,
            "theta_bans": theta_bans, "reason": "exhausted"}


def plain_enumerate_java(grammar: Sequence[str],
                         cases: Sequence[Tuple[int, int, int]],
                         timeout: int = 20) -> Dict:
    """No-fail brute foundry fallback for Java: try every fragment in order.

    Guaranteed to terminate and to test every candidate exactly once — the
    deterministic floor under the rotor path if rotor settings can't build a
    valid class for some fragment.
    """
    test_fn = make_java_test_fn(cases, timeout=timeout)
    seen = set()
    attempts = 0
    for i, frag in enumerate(grammar):
        src = _render(frag)
        if src in seen:
            continue
        seen.add(src)
        attempts += 1
        score = _normalize(test_fn(src))
        if score >= 1.0:
            return {"found": True, "source": src, "key": i,
                    "attempts": attempts, "score": 1.0, "reason": "crib matched"}
    return {"found": False, "best": None, "attempts": attempts,
            "reason": "exhausted"}
