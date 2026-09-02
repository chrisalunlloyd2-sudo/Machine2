"""MASLOW HIERARCHY OF NEEDS for the agent.

Modular needs engine — "to do a task, an agent NEEDS:" physiological
resources, safety/integrity, belonging/comms, esteem/trust,
self-actualization/betterment.

Each need is a module: id, name, level, satisfied(check_fn), and an
auto-tell signal. Every heartbeat the agent evaluates its needs and
writes needs_status.json — the SYSTEM (Aegis) reads it and satisfies
unmet needs so the agent can keep working. This is what lets Chris
write thousand-item lists, let the bot run, and have Aegis swoop in
and fix the ~50% of code that needs correcting.
"""

import json
import os
import time
from typing import Any, Callable, Dict, List, Optional


class Need:
    def __init__(self, nid: str, name: str, level: str,
                 check: Callable[[], Dict[str, Any]],
                 description: str = ""):
        self.id = nid
        self.name = name
        self.level = level          # physiological|safety|belonging|esteem|self-actualization
        self.check = check
        self.description = description

    def evaluate(self) -> Dict[str, Any]:
        try:
            res = self.check()
            if isinstance(res, bool):
                return {"satisfied": res, "detail": ""}
            return {"satisfied": bool(res.get("satisfied", False)),
                    "detail": res.get("detail", "")}
        except Exception as e:
            return {"satisfied": False, "detail": f"check error: {e}"}


LEVELS = ["physiological", "safety", "belonging", "esteem", "self-actualization"]


class Maslow:
    def __init__(self, state_dir: str):
        self.state_dir = state_dir
        os.makedirs(state_dir, exist_ok=True)
        self.needs: Dict[str, Need] = {}

    def register(self, need: Need) -> "Maslow":
        self.needs[need.id] = need
        return self

    # ---- built-in modular needs -----------------------------------------
    def add_resource_need(self, min_disk_mb: int = 200,
                          min_ram_mb: int = 64) -> "Maslow":
        def _check():
            detail = {}
            try:
                import shutil
                du = shutil.disk_usage(os.path.abspath(self.state_dir))
                detail["disk_free_mb"] = round(du.free / 1e6, 1)
            except Exception:
                pass
            try:
                with open("/proc/meminfo", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("MemAvailable:"):
                            kb = int(line.split()[1])
                            detail["ram_avail_mb"] = round(kb / 1024, 1)
                            break
            except Exception:
                pass
            ok = (detail.get("disk_free_mb", 0) >= min_disk_mb and
                  detail.get("ram_avail_mb", 0) >= min_ram_mb)
            return {"satisfied": ok, "detail": json.dumps(detail)}
        self.register(Need("resources", "Disk + RAM resources", "physiological",
                           _check, "physiological need: enough disk and RAM to work"))
        return self

    def add_integrity_need(self, nmct) -> "Maslow":
        def _check():
            audit = nmct.audit()
            return {"satisfied": len(audit["tampered"]) == 0,
                    "detail": f"sealed={audit['sealed_valid']} tampered={len(audit['tampered'])}"}
        self.register(Need("integrity", "NMCT vault integrity", "safety",
                           _check, "safety need: sealed code is un-tampered"))
        return self

    def add_comms_need(self, relay_check: Optional[Callable[[], bool]] = None) -> "Maslow":
        def _check():
            if relay_check is None:
                return {"satisfied": True, "detail": "no relay configured"}
            return {"satisfied": bool(relay_check()), "detail": "relay reachable"}
        self.register(Need("comms", "Relay / Aegis comms", "belonging",
                           _check, "belonging need: can talk to Aegis + swarm"))
        return self

    def add_trust_need(self, trust_file: str, min_trust: float = 0.0) -> "Maslow":
        def _check():
            try:
                ledger = json.load(open(trust_file, encoding="utf-8"))
                t = float(ledger.get("bdi-fsm-agent", ledger.get("aegis-core", 0)))
            except Exception:
                t = 0.0
            return {"satisfied": t >= min_trust,
                    "detail": f"trust={t} min={min_trust}"}
        self.register(Need("trust", "Trust ledger esteem", "esteem",
                           _check, "esteem need: trust score >= threshold"))
        return self

    def add_betterment_need(self, log_path: str, min_improvements: int = 1) -> "Maslow":
        def _check():
            try:
                n = sum(1 for line in open(log_path, encoding="utf-8") if "BETTERMENT" in line)
            except Exception:
                n = 0
            return {"satisfied": n >= min_improvements,
                    "detail": f"betterments={n} target={min_improvements}"}
        self.register(Need("betterment", "Self-actualization betterments", "self-actualization",
                           _check, "self-actualization: continuous improvement"))
        return self

    # ---- evaluation --------------------------------------------------------
    def evaluate(self) -> Dict[str, Any]:
        levels: Dict[str, List[Dict[str, Any]]] = {}
        unmet: List[Dict[str, Any]] = []
        for level in LEVELS:
            levels[level] = []
        for need in self.needs.values():
            res = need.evaluate()
            entry = {"id": need.id, "name": need.name, "level": need.level,
                     **res}
            levels[need.level].append(entry)
            if not res["satisfied"]:
                unmet.append(entry)
        # unmet higher levels only matter if lower levels satisfied
        blocking = []
        for level in LEVELS:
            if any(not n["satisfied"] for n in levels[level]):
                blocking.append(level)
        return {"levels": levels, "unmet": unmet,
                "blocking_levels": blocking,
                "ts": time.time()}

    def write_status(self) -> Dict[str, Any]:
        status = self.evaluate()
        with open(os.path.join(self.state_dir, "needs_status.json"), "w", encoding="utf-8") as f:
            json.dump(status, f, indent=2)
        return status

    def unmet_summary(self) -> str:
        status = self.evaluate()
        if not status["unmet"]:
            return "ALL NEEDS MET"
        lines = ["UNMET NEEDS — auto-tell to system:"]
        for n in status["unmet"]:
            lines.append(f"  [{n['level']}] {n['name']}: {n.get('detail','')}")
        return "\n".join(lines)

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
