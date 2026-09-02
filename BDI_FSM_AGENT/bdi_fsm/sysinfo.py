"""SYSINFO — the host facts, on whichever host this actually is.

WHY THIS EXISTS
    telemetry.py and pacing.py were both written against the phone: `/proc/meminfo`,
    `os.statvfs`, `os.getloadavg`, `ps`. On Windows none of those exist, and both modules
    swallowed the failure -- telemetry returned `{}` for memory and disk, and `guard_memory`
    returned True on the exception path, i.e. "plenty of room" on a 4-core box already holding
    a 2.2 GB llama-server. A guard that cannot measure must not vote; it must say so.

    This module is the single place that knows how to ask the OS. Both callers read it, so
    porting the next platform is one file, not a grep.

THE CONTRACT
    Every reader returns EITHER a real number OR None. None means "not measurable here" and is
    never silently coerced to zero or to a healthy default. Callers decide what to do with an
    unknown -- but they are forced to see that it is unknown, which is the property the old
    exception handlers destroyed.
"""
import os
import shutil
import subprocess
import sys

WINDOWS = sys.platform.startswith("win")


def mem():
    """{total_gb, avail_gb, avail_pct} — values are None when unmeasurable."""
    blank = {"total_gb": None, "avail_gb": None, "avail_pct": None}
    total = avail = None
    if WINDOWS:
        try:
            import ctypes

            class _MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong),
                            ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong),
                            ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong),
                            ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

            st = _MS()
            st.dwLength = ctypes.sizeof(_MS)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
                total, avail = st.ullTotalPhys, st.ullAvailPhys
        except Exception:
            return blank
    else:
        try:
            vals = {}
            with open("/proc/meminfo", encoding="utf-8") as f:
                for line in f:
                    k, v = line.split(":", 1)
                    vals[k] = int(v.strip().split()[0]) * 1024
            total, avail = vals.get("MemTotal"), vals.get("MemAvailable")
        except Exception:
            return blank
    if not total or avail is None:
        return blank
    return {"total_gb": round(total / 1e9, 2),
            "avail_gb": round(avail / 1e9, 2),
            "avail_pct": round(100.0 * avail / total, 1)}


def avail_mb():
    """Available RAM in MB, or None if it cannot be measured on this host."""
    g = mem().get("avail_gb")
    return None if g is None else g * 1000.0


def disk(path=None):
    """{free_gb, total_gb} for the volume holding `path`.

    shutil.disk_usage is already cross-platform, so the statvfs call was never needed -- it only
    narrowed the module to POSIX. Defaults to the drive this code lives on rather than "/",
    which on Windows is not where anything of ours is.
    """
    try:
        u = shutil.disk_usage(path or os.path.abspath(os.sep))
        return {"free_gb": round(u.free / 1e9, 2), "total_gb": round(u.total / 1e9, 2)}
    except Exception:
        return {"free_gb": None, "total_gb": None}


def loadavg():
    """1/5/15-minute load, or None where the OS has no such concept.

    Windows has no loadavg. Rather than inventing one from CPU percent -- a different quantity
    that would be silently compared against POSIX-tuned thresholds -- this reports None, and
    callers fall back to memory pressure, which both platforms really do measure.
    """
    try:
        return [round(x, 2) for x in os.getloadavg()]
    except (OSError, AttributeError):
        return None


def top_procs(n=5):
    """[[pid, cpu%, mem%, name], ...] — heaviest first. [] if unavailable."""
    try:
        if WINDOWS:
            ps = ("Get-Process | Sort-Object -Property WS -Descending | "
                  "Select-Object -First %d Id,@{n='WS';e={[int]($_.WorkingSet64/1MB)}},ProcessName | "
                  "ForEach-Object { \"$($_.Id) $($_.WS) $($_.ProcessName)\" }" % n)
            r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                               capture_output=True, text=True, timeout=20,
                               creationflags=0x08000000)
            out = []
            tot = mem().get("total_gb")
            for line in r.stdout.strip().splitlines():
                parts = line.split(None, 2)
                if len(parts) < 3:
                    continue
                pid, ws_mb, name = parts
                # No per-process CPU% without a second sample; report None rather than 0.0,
                # which would read as "idle" instead of "not measured".
                pct = round(100.0 * (float(ws_mb) / 1000.0) / tot, 1) if tot else None
                out.append([pid, None, pct, name])
            return out
        r = subprocess.run(["ps", "-eo", "pid,pcpu,pmem,comm", "--sort=-pcpu"],
                           capture_output=True, text=True, timeout=5)
        lines = r.stdout.strip().splitlines()[1:1 + n]
        return [l.split(None, 3) for l in lines if l.strip()]
    except Exception:
        return []
