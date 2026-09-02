"""differential.py — store the derivative, integrate on demand (save compute).

Chris 2026-08-15: "getting a vector of acceleration curve by logging just
speed and time, saving efficiency of logging the entire graph by using
calculus to integrate and get acceleration — this will save compute."

The idea: don't store the full curve. Store the DERIVATIVE signal (deltas =
the "speed"), and reconstruct the integral (the "position") by cumulative sum
on demand. Higher-order derivatives (acceleration) fall out by differencing
again. This is delta-encoding: sparse, reversible, compute-cheap.

Pure stdlib, deterministic, zero-LLM.
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence


def deltas(series: Sequence[float]) -> List[float]:
    """First differences (the 'speed' of a position series)."""
    return [series[i] - series[i - 1] for i in range(1, len(series))]


def integrate(deltas: Sequence[float], initial: float) -> List[float]:
    """Cumulative sum (reconstruct 'position' from 'speed' + start)."""
    out = [initial]
    for d in deltas:
        out.append(out[-1] + d)
    return out


def derive(series: Sequence[float], order: int = 1) -> List[float]:
    """nth derivative: order=1 speed, order=2 acceleration, ..."""
    s = list(series)
    for _ in range(order):
        s = deltas(s)
    return s


def encode(series: Sequence[float]) -> Dict[str, Any]:
    """Compact form: {initial, deltas} — the sparse signal."""
    if not series:
        return {"initial": 0.0, "deltas": []}
    return {"initial": series[0], "deltas": deltas(series)}


def decode(encoded: Dict[str, Any]) -> List[float]:
    """Reconstruct the full series from its compact form."""
    return integrate(encoded.get("deltas", []), encoded.get("initial", 0.0))


def roundtrip_ok(series: Sequence[float]) -> bool:
    """True iff encode -> decode reproduces the series exactly."""
    return decode(encode(series)) == list(series)

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
