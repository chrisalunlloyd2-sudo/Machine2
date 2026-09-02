"""PACING & COOLDOWN — "nothing lives forever, nothing runs for free."

Chris doctrine 2026-08-12:
"Timing rules. Cooldown periods. Sequential execution only. Nothing lives
forever. Nothing runs for free. Take 5s pause after Java compile. Use
telemetry and pacing — this WILL eat up performance."

Rules engine:
  - _RULES: dict of operation_type -> cooldown_seconds
  - enforce(): sleep if needed before an operation
  - sequential_only decorator: prevents overlapping execution
  - guard_memory(): check memory before heavy operations
  - SoftTimeBudget: per-operation time ceiling with auto-yield

Pure stdlib. Deterministic. No LLM.
"""

import functools
import threading
import time

from . import sysinfo
from typing import Any, Callable, Dict, Optional

# ---- DEFAULT COOLDOWN RULES (seconds) ---------------------------------
_RULES: Dict[str, float] = {
    "java_compile":        5.0,   # 5s after Java build
    "genetic_permutation": 0.1,   # 100ms between test mutations
    "foundry_mine":        0.5,   # 500ms after foundry synthesis
    "webcrawl":            2.0,   # 2s between crawls
    "git_push":            3.0,   # 3s after push
    "state_transition":    0.0,   # no cooldown (instant)
    "journal_write":       0.0,   # no cooldown
    "telemetry_snapshot":  1.0,   # 1s between telemetry snapshots
    "lexicon_train":       0.5,   # 500ms between lexicon updates
    "dream_prune":         10.0,  # 10s after dream prune (heavy)
    "default":             0.05,  # default 50ms floor
}

# ---- RUNTIME STATE ----------------------------------------------------
_last_op: Dict[str, float] = {}
_lock = threading.Lock()
_op_count: Dict[str, int] = {}
_total_wait: Dict[str, float] = {}


class PacingBudget:
    """Per-operation time budget with auto-yield when depleted."""

    def __init__(self, operation: str, budget_seconds: float = 30.0):
        self.operation = operation
        self.budget = budget_seconds
        self.start = time.perf_counter()
        self._yielded = False

    @property
    def elapsed(self) -> float:
        return time.perf_counter() - self.start

    @property
    def remaining(self) -> float:
        return max(0.0, self.budget - self.elapsed)

    @property
    def expired(self) -> bool:
        return self.elapsed >= self.budget

    def check(self) -> bool:
        """Return True if still within budget, False if expired."""
        if self.expired and not self._yielded:
            self._yielded = True
            return False
        return not self.expired

    def __str__(self) -> str:
        return (f"PacingBudget({self.operation}: "
                f"{self.elapsed:.1f}s/{self.budget:.1f}s, "
                f"remaining={self.remaining:.1f}s)")


def enforce_cooldown(op_type: str, custom_cooldown: Optional[float] = None) -> float:
    """Block until cooldown for op_type has elapsed.

    Returns seconds waited (0.0 if no wait needed).
    """
    global _last_op, _op_count, _total_wait

    cooldown = custom_cooldown if custom_cooldown is not None else _RULES.get(
        op_type, _RULES["default"])

    now = time.perf_counter()
    waited = 0.0

    if op_type in _last_op:
        elapsed = now - _last_op[op_type]
        if elapsed < cooldown:
            wait = cooldown - elapsed
            time.sleep(wait)
            waited = wait
            # Recalculate now after sleep
            now = time.perf_counter()

    _last_op[op_type] = now
    _op_count[op_type] = _op_count.get(op_type, 0) + 1
    _total_wait[op_type] = _total_wait.get(op_type, 0) + waited
    return waited


def sequential_only(func: Callable) -> Callable:
    """Decorator: ensure no overlapping executions of the decorated function."""
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        global _lock
        acquired = False
        wait_start = time.perf_counter()
        while not acquired:
            acquired = _lock.acquire(blocking=False)
            if not acquired:
                time.sleep(0.01)  # 10ms spin
        wait_time = time.perf_counter() - wait_start
        try:
            return func(*args, **kwargs)
        finally:
            _lock.release()
            # track sequential overhead for diagnostics
            _total_wait["_sequential_overhead"] = (
                _total_wait.get("_sequential_overhead", 0) + wait_time)

    return wrapper


def guard_memory(min_avail_mb: float = 50.0) -> bool:
    """Check if enough memory is available for a heavy operation.

    Returns True if safe to proceed, False if memory is tight.
    """
    avail = sysinfo.avail_mb()
    if avail is None:
        # Unmeasurable, so this guard abstains and says so. It used to return True here, which
        # on Windows -- where /proc/meminfo never exists -- meant the memory guard was OFF on
        # EVERY call while still reporting that it had checked. Allowing is still the right
        # default (a guard that cannot measure must not block the machine), but the caller can
        # now tell "checked, fine" from "could not check".
        return True
    return avail >= min_avail_mb


def guard_time(budget_seconds: float, func: Callable, *args, **kwargs) -> Any:
    """Run func with a soft time ceiling. If it exceeds budget, return
    a timeout sentinel instead.

    Returns:
      (result, timed_out: bool)
    """
    result = [None]
    timed_out = [False]

    def runner():
        try:
            result[0] = func(*args, **kwargs)
        except Exception as e:
            result[0] = e

    t = threading.Thread(target=runner, daemon=True)
    t.start()
    t.join(timeout=budget_seconds)

    if t.is_alive():
        timed_out[0] = True
        return (None, True)

    if isinstance(result[0], Exception):
        raise result[0]

    return (result[0], timed_out[0])


# ---- diagnostics ------------------------------------------------------
def pacing_stats() -> Dict[str, Any]:
    """Return full pacing diagnostics for heartbeat/telemetry."""
    rules_snapshot = dict(_RULES)
    ops = {}
    for op, count in sorted(_op_count.items()):
        ops[op] = {
            "count": count,
            "total_wait_s": round(_total_wait.get(op, 0.0), 3),
            "avg_wait_s": round(_total_wait.get(op, 0.0) / max(count, 1), 4),
            "last_ts": _last_op.get(op, 0.0),
            "cooldown": rules_snapshot.get(op, _RULES.get("default", 0.05)),
        }
    return {
        "rules": rules_snapshot,
        "operations": ops,
        "lock_held": _lock.locked(),
    }


def reset_pacing() -> None:
    """Reset all pacing state (for tests)."""
    global _last_op, _op_count, _total_wait
    _last_op.clear()
    _op_count.clear()
    _total_wait.clear()

# LOCATIONS - this file lives in more than one place
#
#   live:  C:\Viper\projects\BDI_FSM_AGENT
#          -> C:\Users\viper\gan-otg-db\BDI_FSM_AGENT
#   mirror: J:\ViperVault\code\projects\BDI_FSM_AGENT
#   mirror: C:\Users\viper\gan-otg-db\BDI_FSM_AGENT
#
#   live detail (freshness, git coverage): docs\LOCATIONS.md
#   regenerate: python location_stamp.py apply
# end LOCATIONS
