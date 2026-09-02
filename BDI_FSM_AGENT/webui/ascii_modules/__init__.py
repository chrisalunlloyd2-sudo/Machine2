"""Programmatic modular ASCII art — one piece per day, added programmatically.

The rotation is deterministic: day_index = days since 2026-08-16, module =
modules[day_index % len(modules)]. Today = sine_wave (the classic). Each day a
new module takes its place. New modules are ADDED to MODULES (never removed) —
the rotation extends forever. The mind-palace swarm votes new modules in.
"""
import importlib, os
from datetime import date

EPOCH = date(2026, 8, 16)  # the sine wave day
_ORDER = ["sine_wave", "warp_drive", "galaxy", "matrix_rain", "plasma"]
_HERE = os.path.dirname(os.path.abspath(__file__))

_MODULES = {}
for _name in _ORDER:
    try:
        _mod = importlib.import_module(f"ascii_modules.{_name}")
        _MODULES[_name] = _mod
    except Exception as _e:  # keep registry alive if one module breaks
        _MODULES[_name] = None


def module_names():
    return list(_ORDER)


def today_index(today: date = None) -> int:
    today = today or date.today()
    return (today - EPOCH).days


def module_for_day(today: date = None):
    i = today_index(today)
    name = _ORDER[i % len(_ORDER)]
    return {"name": name, "index": i, "slot": i % len(_ORDER),
            "total": len(_ORDER), "next": _ORDER[(i + 1) % len(_ORDER)],
            "frame_count": 60}


def frames_for(today: date = None, frames: int = 60):
    info = module_for_day(today)
    mod = _MODULES[info["name"]]
    if mod is None:
        return info, ["# module render unavailable"]
    out = []
    for f in range(frames):
        try:
            out.append(mod.render(f))
        except Exception as _e:
            out.append(f"# render error: {_e}")
    return info, out
