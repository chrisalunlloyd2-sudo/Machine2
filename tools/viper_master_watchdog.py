#!/usr/bin/env python3
"""
VIPER MASTER WATCHDOG v2.1 - Permanent service supervisor
Fixed: won't crash on missing directories or scripts.
Keeps HUD (:18282) and SLM Proxy (:8765) alive. Others optional.
"""
import subprocess
import sys
import time
import socket
import os
import datetime

PY       = r"C:\Users\viper\AppData\Local\Programs\Python\Python311\python.exe"
VIPER    = r"C:\Users\viper\VIPER_JAVA_RISC"
GANOTG   = r"C:\Users\viper\gan-otg-db"
LMSTUDIO = r"C:\Users\viper\AppData\Local\LM Studio\LM Studio.exe"


def log(msg: str) -> None:
    ts = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    print(f"[{ts}] WATCHDOG | {msg}", flush=True)


def port_alive(port: int, host: str = "127.0.0.1", timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def start_svc(svc: dict) -> None:
    script = svc["script"]
    cwd = svc.get("cwd", VIPER)

    if not os.path.isfile(script):
        if svc.get("critical", False):
            log(f"CRITICAL script missing: {script}")
        else:
            log(f"SKIP {svc['name']} (script not found)")
        return

    if not os.path.isdir(cwd):
        cwd = VIPER  # fallback cwd

    try:
        flags = 0
        if sys.platform == "win32":
            flags = subprocess.CREATE_NO_WINDOW
        proc = subprocess.Popen(
            [PY, script],
            cwd=cwd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
        )
        svc["proc"] = proc
        log(f"STARTED {svc['name']} PID={proc.pid}")
    except Exception as e:
        log(f"FAILED to start {svc['name']}: {e}")
        svc["proc"] = None


def check_svc(svc: dict) -> None:
    try:
        # Port-based health check for services with known ports
        if svc.get("port") and port_alive(svc["port"]):
            return  # Port is alive — service ok

        proc = svc.get("proc")
        if proc is not None:
            ret = proc.poll()
            if ret is None:
                # Process running, no port check needed
                if not svc.get("port"):
                    return
                # Has port but not responding yet — let it warm up
                return
            else:
                log(f"DIED {svc['name']} exit={ret} — queued restart")
                svc["proc"] = None

        # Not running — restart after delay
        time.sleep(svc.get("restart_delay", 3))
        start_svc(svc)
    except Exception as e:
        log(f"ERROR checking {svc['name']}: {e}")


SERVICES = [
    {
        "name": "viper_omniscient_hud",
        "port": 18282,
        "script": rf"{VIPER}\tools\viper_omniscient_hud.py",
        "cwd": VIPER,
        "proc": None,
        "restart_delay": 2,
        "critical": True,
    },
    {
        "name": "viper_slm_station_proxy",
        "port": 8765,
        "script": rf"{VIPER}\tools\viper_slm_station_proxy.py",
        "cwd": VIPER,
        "proc": None,
        "restart_delay": 2,
        "critical": True,
    },
    {
        "name": "otg_dual_bridge_A",
        "port": 18283,
        "script": rf"{VIPER}\tools\otg_dual_bridge.py",
        "cwd": VIPER,
        "proc": None,
        "restart_delay": 3,
        "critical": True,
    },
    {
        "name": "karoo_code_miner",
        "port": None,
        "script": rf"{VIPER}\tools\karoo_code_miner.py",
        "cwd": VIPER,
        "proc": None,
        "restart_delay": 10,
        "critical": False,
    },
    {
        "name": "viper_llm_server",
        "port": None,
        "script": rf"{GANOTG}\viper-scripts\viper_llm_server.py",
        "cwd": rf"{GANOTG}\viper-scripts",
        "proc": None,
        "restart_delay": 10,
        "critical": False,
    },
    {
        "name": "otg_db_bridge",
        "port": None,
        "script": rf"{GANOTG}\otg_db_bridge.py",
        "cwd": GANOTG,
        "proc": None,
        "restart_delay": 10,
        "critical": False,
    },
    {
        "name": "sovereign_loop",
        "port": None,
        "script": rf"{GANOTG}\viper-scripts\sovereign_loop.py",
        "cwd": rf"{GANOTG}\viper-scripts",
        "proc": None,
        "restart_delay": 10,
        "critical": False,
    },
    {
        "name": "moe_server",
        "port": None,
        "script": rf"{GANOTG}\ArchivalMoe\moe_server.py",
        "cwd": rf"{GANOTG}\ArchivalMoe",
        "proc": None,
        "restart_delay": 10,
        "critical": False,
    },
]


def maybe_start_lmstudio() -> None:
    if port_alive(1234):
        log("LM Studio already on :1234")
        return
    if not os.path.isfile(LMSTUDIO):
        log("LM Studio not found — skipping (ensure LM Studio is open and server enabled)")
        return
    log("Starting LM Studio with --server flag...")
    try:
        subprocess.Popen(
            [LMSTUDIO, "--server"],
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        log("LM Studio launched")
    except Exception as e:
        log(f"Could not launch LM Studio: {e}")


def main() -> None:
    log("=" * 60)
    log("VIPER MASTER WATCHDOG v2.1 — ONLINE")
    log("=" * 60)

    maybe_start_lmstudio()
    time.sleep(1)

    # Initial start — only start if port is not already live
    for svc in SERVICES:
        try:
            if svc.get("port") and port_alive(svc["port"]):
                log(f"ALREADY UP: {svc['name']} on :{svc['port']}")
                # Just track it exists (no proc handle, port check will keep it safe)
            else:
                start_svc(svc)
            time.sleep(0.5)
        except Exception as e:
            log(f"ERROR starting {svc['name']}: {e}")

    log("All services initialized. Monitoring loop active...")

    cycle = 0
    while True:
        cycle += 1
        for svc in SERVICES:
            check_svc(svc)

        if cycle % 12 == 0:  # Log heartbeat every ~60s
            ports_up = [p for p in [1234, 8765, 11435, 18181, 18282] if port_alive(p)]
            log(f"HEARTBEAT | ports_up={ports_up}")

        time.sleep(5)


if __name__ == "__main__":
    main()
