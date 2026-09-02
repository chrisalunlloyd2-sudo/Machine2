"""CONTROLLER DISCOVERY — the agent seeks a controller, and does nothing
until one is satisfied.

Controllers (LOCAL ONLY — no cloud LLMs, ever):
  1. LocalLLMController  — probes localhost llama-server (:5001) / gguf (:5000)
  2. HumanController     — human in PowerShell / terminal (command files, stdin)

The agent proposes actions but ONLY executes external actions when an
active controller is present. If no controller is active, the agent stays
in WAIT_AEGIS / BLOCKED and reports the unmet controller need.
"""

import json
import os
import time
import urllib.request
from typing import Any, Dict, List, Optional


class Controller:
    kind = "base"
    name = "base"

    def probe(self) -> Dict[str, Any]:
        """Return {"active": bool, "detail": str}."""
        raise NotImplementedError

    def is_active(self) -> bool:
        return bool(self.probe().get("active"))


# The controller endpoints that actually exist on the Viper host, in preference order.
# 2026-08-10: the defaults were :5001/:5000, which nothing on this box has ever listened on, so
# has_controller() was permanently False and EVERY verified candidate parked in WAIT_AEGIS. The
# agent looked cautious; it was simply looking in the wrong place. Override with
# VIPER_BDI_ENDPOINTS (comma-separated) rather than editing this list.
VIPER_ENDPOINTS = [
    "http://127.0.0.1:8765/health",       # viper_llm_server -- the house LLM
    "http://127.0.0.1:11434/api/tags",    # ollama
    "http://localhost:5001/health",       # llama-server, if someone starts one
    "http://localhost:5000/healthz",
]


class LocalLLMController(Controller):
    """Probes the local house LLM / ollama. NEVER reaches outside localhost. No cloud."""

    kind = "local_llm"
    name = "local-llm"

    def __init__(self, endpoints: Optional[List[str]] = None,
                 timeout: float = 2.0):
        env = os.environ.get("VIPER_BDI_ENDPOINTS", "").strip()
        self.endpoints = endpoints or ([e.strip() for e in env.split(",") if e.strip()]
                                       or list(VIPER_ENDPOINTS))
        self.timeout = timeout

    def probe(self) -> Dict[str, Any]:
        """Stop at the FIRST live endpoint.

        The question is "is a controller present", not "how many". Probing all four cost up to
        4 x timeout on every heartbeat and every slot resolution, and the whole point of this
        agent is that it is cheap enough to run continuously on one core.
        """
        for url in self.endpoints:
            try:
                with urllib.request.urlopen(url, timeout=self.timeout) as r:
                    if r.status == 200:
                        return {"active": True, "detail": f"controller alive: {url}"}
            except Exception:
                pass
        return {"active": False,
                "detail": "no local controller on {}".format(", ".join(self.endpoints))}


class HumanController(Controller):
    """Human in PowerShell / terminal. Active when a command/request file
    exists (e.g. <state>/control/human_request.txt) or stdin is a tty.

    The human writes an instruction; the agent reads it, executes, and
    writes the response to human_response.txt. No cloud, no automation —
    a real human is in the loop."""

    kind = "human"
    name = "human-powershell"

    def __init__(self, control_dir: str, request_file: str = "human_request.txt",
                 response_file: str = "human_response.txt"):
        self.control_dir = control_dir
        self.request_file = request_file
        self.response_file = response_file

    def _req_path(self) -> str:
        return os.path.join(self.control_dir, self.request_file)

    def _resp_path(self) -> str:
        return os.path.join(self.control_dir, self.response_file)

    def probe(self) -> Dict[str, Any]:
        p = self._req_path()
        active = os.path.exists(p)
        return {"active": active,
                "detail": f"human request file: {p} (exists={active})"}

    def read_request(self) -> Optional[str]:
        p = self._req_path()
        if os.path.exists(p):
            return open(p, encoding="utf-8").read().strip()
        return None

    def write_response(self, text: str) -> None:
        with open(self._resp_path(), "w", encoding="utf-8") as f:
            f.write(text)


class ControllerHub:
    """Discovers active controllers. The agent does nothing external until
    at least one is satisfied."""

    def __init__(self, state_dir: str):
        self.state_dir = state_dir
        self.control_dir = os.path.join(state_dir, "control")
        os.makedirs(self.control_dir, exist_ok=True)
        self.controllers: List[Controller] = [
            LocalLLMController(),
            HumanController(self.control_dir),
        ]

    def add(self, c: Controller) -> "ControllerHub":
        self.controllers.append(c)
        return self

    def active_controllers(self) -> List[Dict[str, Any]]:
        out = []
        for c in self.controllers:
            p = c.probe()
            if p.get("active"):
                out.append({"kind": c.kind, "name": c.name, **p})
        return out

    def has_controller(self) -> bool:
        return len(self.active_controllers()) > 0

    def status(self) -> Dict[str, Any]:
        return {
            "controllers": [{"kind": c.kind, "name": c.name, **c.probe()}
                            for c in self.controllers],
            "any_active": self.has_controller(),
            "ts": time.time(),
        }

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
