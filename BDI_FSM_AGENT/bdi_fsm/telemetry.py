"""
TELEMETRY & STABILIZATION — deterministic performance monitoring + self-healing.

Chris directive 2026-08-11: "monitor performance more — the FSM agent should be
able to handle telemetry stabilization."

- snapshot(): loadavg, memory (MemAvailable %), disk free, :5000/:5001 server
  health, heaviest procs, span error rate from the pipe_ops trace.
- trend(): rolling-window deltas (disk drift/hr, mem %, err rate) from the
  telemetry.jsonl log — "monitor performance MORE" = trend-aware, not just
  point-in-time.
- stabilize(): deterministic, threshold-driven actions:
    * server down (:5000/:5001)        -> restart via game_watchdog/restart_stack
    * memory < 15% avail               -> sync + drop_caches (root only, best-effort)
    * disk < 1 GB free                 -> report non-load-bearing candidates (never delete)
    * span err rate > 0.80             -> flag for journal/doctor (reported, no auto action)
  ADD-ONLY: stabilize never deletes anything.
"""

import json
import os
import subprocess
import time
import urllib.request
from urllib.parse import urlsplit

from . import sysinfo
from .controllers import VIPER_ENDPOINTS

# Derived from controllers.py, never typed twice: the ports telemetry watches must be the ports
# the agent actually uses, or a green monitor tells you nothing about a broken controller.
HEALTH_ENDPOINTS = tuple((urlsplit(u).port, urlsplit(u).path) for u in VIPER_ENDPOINTS)

WATCHDOG_SCRIPTS = (
    "/root/hexgame/game_watchdog.sh",
    "/root/hexgame/restart_stack.sh",
    "/root/MatrixWinCE/restart_stack.sh",
)

MEM_PRESSURE_PCT = 15.0
DISK_LOW_GB = 1.0
SPAN_ERR_HIGH = 0.80
LOG_MAX = 500


class Telemetry:
    def __init__(self, state_dir: str):
        self.state_dir = state_dir
        self.log_path = os.path.join(state_dir, "telemetry", "telemetry.jsonl")
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)

    # ---- collection ----------------------------------------------------
    def snapshot(self) -> dict:
        snap = {
            "ts": time.time(),
            "iso": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        snap["loadavg"] = sysinfo.loadavg()
        snap["mem"] = sysinfo.mem()
        snap["disk"] = sysinfo.disk(self.state_dir)
        snap["servers"] = self._server_health()
        snap["top_procs"] = self._top_procs(5)
        snap["span_err_rate"] = self._span_err_rate()
        snap["journal_lines"] = self._count_lines(
            os.path.join(self.state_dir, "journal.jsonl"))
        snap["skills"] = self._count_files(os.path.join(self.state_dir, "skills"))
        self._append(snap)
        return snap

    def _server_health(self) -> dict:
        """Are the controllers this agent actually talks to alive?

        :5000/:5001 were the phone's game servers and are nothing on the Viper host, so this
        probed two dead ports every snapshot and reported `down:URLError` forever -- a permanent
        red that means nothing, which is how a monitor teaches you to ignore it. controllers.py
        already resolved the real pair during the Windows port; read them from there so the two
        cannot drift apart again.
        """
        out = {}
        for port, path in HEALTH_ENDPOINTS:
            try:
                with urllib.request.urlopen(
                        f"http://localhost:{port}{path}", timeout=2) as r:
                    out[str(port)] = r.status
            except Exception as e:
                out[str(port)] = f"down:{type(e).__name__}"
        return out

    def _top_procs(self, n: int) -> list:
        return sysinfo.top_procs(n)

    def _span_err_rate(self) -> float | None:
        p = "/root/hexgame/telemetry/trace.jsonl"
        try:
            if not os.path.exists(p):
                return None
            rows = []
            with open(p) as f:
                for line in f:
                    try:
                        rows.append(json.loads(line))
                    except Exception:
                        pass
            rows = rows[-100:]
            if not rows:
                return None
            errs = sum(1 for r in rows if r.get("status") == "error")
            return round(errs / len(rows), 3)
        except Exception:
            return None

    @staticmethod
    def _count_lines(path: str) -> int:
        try:
            with open(path) as f:
                return sum(1 for _ in f)
        except Exception:
            return 0

    @staticmethod
    def _count_files(path: str) -> int:
        try:
            return len([x for x in os.listdir(path) if x.endswith(".json")])
        except Exception:
            return 0

    def _append(self, snap: dict) -> None:
        rows = []
        if os.path.exists(self.log_path):
            try:
                with open(self.log_path) as f:
                    for line in f:
                        try:
                            rows.append(json.loads(line))
                        except Exception:
                            pass
            except Exception:
                pass
        rows.append(snap)
        rows = rows[-LOG_MAX:]
        with open(self.log_path, "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")

    # ---- trends (monitor performance MORE) ------------------------------
    def trend(self, window: int = 12) -> dict:
        rows = []
        if os.path.exists(self.log_path):
            with open(self.log_path) as f:
                for line in f:
                    try:
                        rows.append(json.loads(line))
                    except Exception:
                        pass
        rows = rows[-window:]
        if len(rows) < 2:
            return {"samples": len(rows), "note": "need >= 2 samples"}
        first, last = rows[0], rows[-1]
        dt = max(last["ts"] - first["ts"], 1.0)
        hrs = dt / 3600.0

        def delta(key):
            a = first.get("disk", {}).get(key)
            b = last.get("disk", {}).get(key)
            if a is None or b is None:
                return None
            return round((b - a) / hrs, 3)  # per hour

        mem_last = last.get("mem", {})
        return {
            "samples": len(rows),
            "span_hours": round(hrs, 2),
            "disk_free_delta_h": delta("free_gb"),
            "mem_avail_pct": mem_last.get("avail_pct"),
            "span_err_rate": last.get("span_err_rate"),
            "servers": last.get("servers"),
            "loadavg": last.get("loadavg"),
        }

    # ---- stabilization --------------------------------------------------
    def stabilize(self, dry_run: bool = False) -> dict:
        """Deterministic stabilization. Returns actions taken/recommended."""
        snap = self.snapshot()
        actions = []

        # 1. controllers down -> restart via watchdog script
        #
        # ANY endpoint answering means the controller layer is up, because that is exactly what
        # controllers.has_controller() does -- first hit wins. Flagging each dead endpoint
        # separately raised restart_server for :5000 and :5001 on every single snapshot here:
        # they are the phone's game servers, they are nothing on this host, and they are only in
        # the list as fallbacks. A permanent red that is expected is worse than no check, because
        # it trains you to skim past the one that eventually matters.
        servers = snap.get("servers", {})
        if servers and not any(s == 200 for s in servers.values()):
            actions.append({
                "action": "restart_server", "ports": sorted(servers),
                "why": "no controller endpoint answered: {}".format(servers),
                "dry_run": dry_run})
            if not dry_run:
                for script in WATCHDOG_SCRIPTS:
                    if os.path.exists(script):
                        try:
                            subprocess.run(["sh", script],
                                           capture_output=True, timeout=25)
                        except Exception:
                            pass
                        break

        # 2. memory pressure -> sync + drop_caches (root only, best-effort)
        avail_pct = snap.get("mem", {}).get("avail_pct")
        if avail_pct is not None and avail_pct < MEM_PRESSURE_PCT:
            actions.append({
                "action": "memory_pressure", "pct": avail_pct,
                "why": f"avail < {MEM_PRESSURE_PCT}%", "dry_run": dry_run})
            # Reporting the pressure is the cross-platform part and always happens. The RELIEF is
            # POSIX-only (`sync` + drop_caches); Windows has no equivalent a user process may
            # perform, so it is skipped explicitly rather than attempted and swallowed -- the
            # action record says which of the two actually happened.
            if not dry_run and not sysinfo.WINDOWS:
                try:
                    subprocess.run(["sync"], capture_output=True, timeout=5)
                    if os.geteuid() == 0:
                        subprocess.run(["sh", "-c", "echo 3 > /proc/sys/vm/drop_caches"],
                                       capture_output=True, timeout=5)
                    actions[-1]["relief"] = "sync+drop_caches"
                except Exception:
                    pass
            elif sysinfo.WINDOWS:
                actions[-1]["relief"] = "none available on windows — reported only"

        # 3. disk low -> report candidates (ADD-ONLY: never delete)
        free_gb = snap.get("disk", {}).get("free_gb")
        if free_gb is not None and free_gb < DISK_LOW_GB:
            actions.append({
                "action": "disk_low", "free_gb": free_gb,
                "why": f"< {DISK_LOW_GB} GB — candidates: /tmp/*, __pycache__, old rollbacks",
                "dry_run": dry_run})

        # 4. high span error rate -> flag (report only, doctor decides)
        err = snap.get("span_err_rate")
        if err is not None and err > SPAN_ERR_HIGH:
            actions.append({
                "action": "high_span_error", "err_rate": err,
                "why": f"> {SPAN_ERR_HIGH} — check :5000/:5001 request health", "dry_run": dry_run})

        return {"snapshot": snap, "actions": actions, "trend": self.trend()}
