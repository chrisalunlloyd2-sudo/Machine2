"""SCHEDULER — the time-aware learning loop.

"Submit a function based off time to emulate time aware." A deterministic
cron-style scheduler: register (name, expr, fn), and due(dt) returns the
functions DUE at that datetime. The agent's Clock drives it, so behaviour
becomes a function of WHEN, not just WHAT. Night is a first-class concept
(the dream cycle runs then).

Pure stdlib. Deterministic. Zero LLM.
"""
import datetime as _dt
from typing import Callable, Dict, List, Optional, Tuple

# 5-field cron: minute hour day-of-month month day-of-week (0=Monday..6=Sunday,
# Python weekday() convention). Supports *, number, comma lists, a-b ranges,
# and */step.


def _field_match(expr: str, value: int, lo: int, hi: int) -> bool:
    if expr == "*":
        return True
    for part in expr.split(","):
        part = part.strip()
        if not part:
            continue
        if "/" in part:
            base, step = part.split("/", 1)
            step = int(step)
            start = lo if base in ("*", "") else int(base)
            if start <= value <= hi and (value - start) % step == 0:
                return True
        elif "-" in part:
            a, b = part.split("-", 1)
            if int(a) <= value <= int(b):
                return True
        elif int(part) == value:
            return True
    return False


def cron_match(expr: str, dt) -> bool:
    """Does dt satisfy the 5-field cron expr?"""
    parts = expr.split()
    if len(parts) != 5:
        raise ValueError(f"cron expr needs 5 fields, got {len(parts)}: {expr!r}")
    minute, hour, dom, mon, dow = parts
    return (_field_match(minute, dt.minute, 0, 59)
            and _field_match(hour, dt.hour, 0, 23)
            and _field_match(dom, dt.day, 1, 31)
            and _field_match(mon, dt.month, 1, 12)
            and _field_match(dow, dt.weekday(), 0, 6))


def is_nighttime(dt, start_hour: int = 0, end_hour: int = 6) -> bool:
    """Night = the hours [start_hour, end_hour) local (default midnight-6am)."""
    return dt.hour >= start_hour and dt.hour < end_hour


class Scheduler:
    """Register time->function entries and query what's due."""

    def __init__(self, clock=None):
        self.clock = clock
        self.entries: List[Dict] = []  # {name, expr, fn}

    def every(self, name: str, expr: str, fn: Callable) -> "Scheduler":
        cron_match(expr, _dt.datetime(2024, 1, 1, 0, 0))  # validate early
        self.entries.append({"name": name, "expr": expr, "fn": fn})
        return self

    def due(self, dt) -> List[Dict]:
        return [e for e in self.entries if cron_match(e["expr"], dt)]

    def due_now(self) -> List[Dict]:
        if self.clock is not None:
            now = _dt.datetime.fromtimestamp(self.clock.now())
        else:
            now = _dt.datetime.now()
        return self.due(now)
