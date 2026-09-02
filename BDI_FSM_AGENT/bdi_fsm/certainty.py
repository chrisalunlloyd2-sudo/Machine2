"""
CERTAINTY GATE — the 100% doctrine (Chris 2026-08-11).

"every step ask: is this going to work 100%? if not take a step back assessment
and redo. until 100%"

Every step of a task is gated: run deterministic checks, and ONLY pass the step
when ALL checks pass — 100%. Any check failing triggers a STEP_BACK: assess what
failed, record it in never-try-twice (NMTD) so the same failing variant is never
tried again, then redo with a variant until 100% or max_redo exhausted.

Deterministic verifiers only — zero LLM. A step is 100% iff every check passes.

Verifier catalog (pure stdlib):
    compile(path)              py_compile
    test_run(test_file)        pytest exit 0 (bounded timeout)
    file_exists(path)
    fact(bb_key)               blackboard has the fact
    dependency(input_keys)     all inputs present in blackboard
    constraint(callable, out)  predicate(out) is True
    not_blocked(action)        action not in NMTD never-try-twice
    not_empty(value)           output is non-empty
"""

import os
import subprocess
import time


class CertaintyGate:
    """Ask 'will this work 100%?' and only pass when every check does."""

    VERIFIERS = ("compile", "test_run", "file_exists", "fact", "dependency",
                 "constraint", "not_blocked", "not_empty", "ban_gain")

    def __init__(self, nmtd=None, state_dir: str | None = None):
        self.nmtd = nmtd
        self.state_dir = state_dir

    # ---- verifier implementations ---------------------------------------
    def _verify(self, name: str, arg, context: dict) -> dict:
        try:
            if name == "compile":
                import py_compile
                py_compile.compile(arg, doraise=True)
                return {"pass": True, "detail": f"{arg} compiles"}
            if name == "test_run":
                ok = self._run_tests(arg)
                return {"pass": ok, "detail": f"pytest {arg} -> {'ok' if ok else 'FAIL'}"}
            if name == "file_exists":
                ok = os.path.exists(arg)
                return {"pass": ok, "detail": f"{arg} exists" if ok else f"{arg} MISSING"}
            if name == "fact":
                bb = context.get("bb", {})
                ok = bb.get(arg) is not None
                return {"pass": ok, "detail": f"fact {arg} present" if ok else f"fact {arg} ABSENT"}
            if name == "dependency":
                bb = context.get("bb", {})
                missing = [k for k in arg if bb.get(k) is None]
                ok = not missing
                return {"pass": ok, "detail": f"deps ok" if ok else f"missing deps: {missing}"}
            if name == "constraint":
                pred = arg
                out = context.get("output")
                ok = bool(pred(out))
                return {"pass": ok, "detail": f"constraint {'holds' if ok else 'VIOLATED'}"}
            if name == "not_blocked":
                ok = True
                if self.nmtd is not None:
                    try:
                        ok = not self.nmtd.is_blocked(arg)
                    except Exception:
                        ok = True
                return {"pass": ok, "detail": f"{arg} not blocked" if ok else f"{arg} BLOCKED (never-try-twice)"}
            if name == "not_empty":
                ok = bool(context.get("output"))
                return {"pass": ok, "detail": "output non-empty" if ok else "output EMPTY"}
            if name == "ban_gain":
                # arg = minimum information gain in bans; context["ban_gain"]
                # set by the caller from BanLedger/Ban (the soul).
                gain = context.get("ban_gain")
                if gain is None:
                    return {"pass": False, "detail": "no ban_gain in context"}
                ok = gain >= arg
                return {"pass": ok,
                        "detail": f"info gain {gain:.4f} bans >= {arg} min" if ok
                                  else f"info gain {gain:.4f} bans < {arg} min (zero-ban step = wasted)"}
            return {"pass": False, "detail": f"unknown verifier {name}"}
        except Exception as e:  # noqa: BLE001
            return {"pass": False, "detail": f"{name}: {type(e).__name__}: {e}"}

    def _run_tests(self, test_file: str, timeout: int = 45) -> bool:
        try:
            r = subprocess.run(
                ["python3", "-m", "pytest", test_file, "-q", "-x"],
                capture_output=True, text=True, timeout=timeout)
            return r.returncode == 0
        except Exception:
            return False

    # ---- the gate --------------------------------------------------------
    def assess(self, step: dict, context: dict) -> dict:
        """step: {name, checks: [(verifier, arg), ...], output}
        Returns verdict PASS (all checks) or STEP_BACK with failing checks."""
        checks = [self._verify(v, a, context) for v, a in step.get("checks", [])]
        passed = all(c["pass"] for c in checks)
        return {
            "step": step.get("name"),
            "verdict": "PASS" if passed else "STEP_BACK",
            "confidence": 1.0 if passed else 0.0,   # binary: 100% or not
            "checks": checks,
            "failing": [c for c in checks if not c["pass"]],
            "ts": time.time(),
        }

    def step_back(self, step: dict, assessment: dict) -> dict:
        """Step-back assessment + redo variant. Records NMTD so the same
        failing variant is never tried twice."""
        name = step.get("name", "step")
        failing = assessment.get("failing", [])
        reason = "; ".join(f["detail"] for f in failing) or "unknown failure"
        recorded = False
        if self.nmtd is not None:
            try:
                self.nmtd.record(name, "fail", reason)
                recorded = True
            except Exception:
                recorded = False
        variant = step.get("redo_variant")
        return {
            "assessment": {
                "step": name,
                "reason": reason,
                "failing_checks": [f.get("name") or f.get("detail", "?")[:40] for f in failing],
                "state_snapshot": {k: v for k, v in
                                   assessment.get("checks", []) if False},  # placeholder
                "redo_instruction": (f"step back: '{name}' failed ({reason}); "
                                     f"assess and redo until 100%"),
            },
            "nmtd_recorded": recorded,
            "redo_variant": variant,
            "max_redo_hint": "retry with variant; if still failing, course-change",
        }
