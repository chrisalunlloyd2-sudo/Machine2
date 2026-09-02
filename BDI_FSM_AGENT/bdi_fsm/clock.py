"""CLOCK — authoritative time from the Cloudflare atomic clock.

"Time-aware" needs a trustworthy epoch: local clocks drift, but Cloudflare's
edge is NTP-synced to atomic time. The cdn-cgi/trace endpoint returns
`ts=<unix epoch>` over HTTPS — a deterministic, stdlib-only, no-auth epoch
anchor. sync() returns the authoritative epoch plus the local-vs-atomic
drift so the agent knows how far its own clock is off, and Clock.now()
returns drift-corrected time.

Pure stdlib. Deterministic. Zero LLM.
"""
import time
import urllib.request
from typing import Callable, Dict, Optional

TRACE_URL = "https://cloudflare.com/cdn-cgi/trace"
TIMEOUT = 8
UA = "BDI-FSM-AGENT/0.3 (deterministic clock sync; polite)"


def _fetch_trace_epoch(url: str = TRACE_URL, timeout: int = TIMEOUT) -> Optional[float]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        for line in r.read().decode("utf-8", errors="replace").splitlines():
            if line.startswith("ts="):
                return float(line[3:].strip())
    return None


def sync(fetch_fn: Optional[Callable] = None, timeout: int = TIMEOUT) -> Dict:
    """Return {atomic_epoch, local_epoch, drift_seconds, ok}. Injectable fetch
    so tests stay deterministic (no network)."""
    local = time.time()
    fn = fetch_fn or _fetch_trace_epoch
    try:
        atomic = fn(timeout=timeout)
    except Exception as exc:
        return {"atomic_epoch": None, "local_epoch": local,
                "drift_seconds": None, "ok": False, "error": str(exc)[:120]}
    if atomic is None:
        return {"atomic_epoch": None, "local_epoch": local,
                "drift_seconds": None, "ok": False, "error": "no ts= in trace"}
    return {"atomic_epoch": atomic, "local_epoch": local,
            "drift_seconds": local - atomic, "ok": True}


class Clock:
    """Drift-corrected clock. sync() re-anchors to atomic time; now() returns
    local time corrected by the measured drift."""

    def __init__(self, fetch_fn: Optional[Callable] = None):
        self._fetch_fn = fetch_fn
        self._drift = 0.0
        self.last_sync: Optional[Dict] = None

    def sync(self, timeout: int = TIMEOUT) -> Dict:
        self.last_sync = sync(fetch_fn=self._fetch_fn, timeout=timeout)
        if self.last_sync.get("ok"):
            self._drift = self.last_sync["drift_seconds"]
        return self.last_sync

    def now(self) -> float:
        """Authoritative (drift-corrected) epoch seconds."""
        return time.time() - self._drift
