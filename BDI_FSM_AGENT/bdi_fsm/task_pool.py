"""FLEET TASK POOL — consume task_pool.json (thousands-of-items lists).

Phase 8 fleet integration: the agent works the same task pool as the
swarm scheduler — classifies tasks deterministically (probe vs llm vs
unknown), claims with FOW, records outcomes to the action journal.

Pure stdlib. No cloud, no LLM. Pacing doctrine: ONE task per cycle.
"""

import json
import os
import re
import time
from typing import Any, Dict, List, Optional

# Words that mark a task as needing a model (deferred to the LLM/SLM
# pipeline — the deterministic agent never touches these).
LLM_MARKERS = ("llm", "model", "slm", "prompt", "chat", "generate essay",
               "write poem", "summarize", "translate", "inference")
# Deterministic-capable file types.
PROBE_EXTS = (".py", ".sh", ".json", ".md", ".txt", ".js")


class FleetTaskPool:
    def __init__(self, pool_path: str, state_dir: str,
                 default_agent: str = "bdi-fsm-agent"):
        self.pool_path = pool_path
        self.state_dir = state_dir
        self.default_agent = default_agent
        os.makedirs(state_dir, exist_ok=True)
        self.claims_path = os.path.join(state_dir, "pool_claims.json")
        self._claims: Dict[str, Dict[str, Any]] = {}
        if os.path.exists(self.claims_path):
            try:
                self._claims = json.load(open(self.claims_path, encoding="utf-8"))
            except Exception:
                self._claims = {}

    # ---- pool IO ------------------------------------------------------
    def load(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.pool_path):
            return []
        try:
            data = json.load(open(self.pool_path, encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get("tasks"), list):
            return data["tasks"]
        return []

    def save_claims(self) -> None:
        with open(self.claims_path, "w", encoding="utf-8") as f:
            json.dump(self._claims, f, indent=2)

    # ---- classification -----------------------------------------------
    @staticmethod
    def classify(task: Dict[str, Any]) -> str:
        """probe | llm | unknown — deterministic, no model."""
        if task.get("done"):
            return "done"
        ttype = str(task.get("type", "")).lower()
        if ttype in ("probe", "deterministic", "local", "file"):
            return "probe"
        if ttype in ("llm", "model", "slm", "ai"):
            return "llm"
        text = " ".join(str(task.get(k, "")) for k in ("task", "title", "id"))
        low = text.lower()
        if any(m in low for m in LLM_MARKERS):
            return "llm"
        fname = str(task.get("file", "")).lower()
        if fname.endswith(PROBE_EXTS) or (fname and "/" not in fname):
            return "probe"
        return "unknown"

    # ---- selection -----------------------------------------------------
    def next_open(self, agent: Optional[str] = None, skip_done: bool = True,
                  prefer: str = "probe") -> Optional[Dict[str, Any]]:
        """Highest-priority open, unclaimed, not-done task.
        prefer: 'probe' (deterministic agent default) | 'llm' | 'any'."""
        agent = agent or self.default_agent
        tasks = [t for t in self.load() if not t.get("done")]
        tasks.sort(key=lambda t: -int(t.get("priority", 0) or 0))
        for t in tasks:
            tid = str(t.get("id", t.get("task", "")))
            if not tid:
                continue
            claim = self._claims.get(tid)
            if claim and claim.get("agent") != agent and \
               time.time() - claim.get("ts", 0) < claim.get("ttl", 1800):
                continue
            cls = self.classify(t)
            if cls == "done":
                continue
            if prefer == "any" or cls == prefer:
                return t
        return None

    # ---- claim / release ----------------------------------------------
    def claim(self, task_id: str, agent: Optional[str] = None,
              ttl: int = 1800) -> bool:
        agent = agent or self.default_agent
        existing = self._claims.get(task_id)
        if existing and existing.get("agent") != agent and \
           time.time() - existing.get("ts", 0) < existing.get("ttl", ttl):
            return False
        self._claims[task_id] = {"agent": agent, "ts": time.time(), "ttl": ttl}
        self.save_claims()
        return True

    def release(self, task_id: str) -> None:
        self._claims.pop(task_id, None)
        self.save_claims()

    def sweep_stale(self, max_age: float = 1800.0) -> int:
        now = time.time()
        stale = [k for k, v in self._claims.items()
                 if now - v.get("ts", 0) > v.get("ttl", max_age)]
        for k in stale:
            self._claims.pop(k, None)
        self.save_claims()
        return len(stale)

    # ---- outcome recording ---------------------------------------------
    # A task that keeps failing must stop being retried. The foundry is genetic, so a retry is
    # sometimes the right answer -- but only a bounded number of times.
    MAX_ATTEMPTS = int(os.environ.get("VIPER_BDI_MAX_ATTEMPTS", "3"))

    def record_outcome(self, task_id: str, agent: str, outcome: str,
                       detail: str, journal) -> Dict[str, Any]:
        """Journal the outcome; close the task on success, park it after repeated failure.

        Previously only `ok` closed a task and the claim was always released, so a task that could
        not be mined came back as the highest-priority open task on the very next cycle -- forever.
        Each attempt costs a full foundry mine (~6s measured), so one unmineable task quietly
        consumed the agent's entire duty cycle and nothing behind it in the queue ever ran.

        A parked task is NOT deleted and NOT marked done-successfully: it carries `blocked`, the
        attempt count and the last error, so it stays visible and can be released deliberately.
        """
        entry = journal.record(agent, f"pool:{task_id}", detail, outcome)
        tasks = self.load()
        dirty = False
        for t in tasks:
            if str(t.get("id", t.get("task", ""))) != task_id:
                continue
            if outcome == "ok":
                t["done"] = True
                t["done_by"] = agent
                t["done_ts"] = time.time()
            else:
                t["attempts"] = int(t.get("attempts", 0)) + 1
                t["last_error"] = detail[:300]
                t["last_attempt_ts"] = time.time()
                if t["attempts"] >= self.MAX_ATTEMPTS:
                    t["blocked"] = True
                    t["blocked_reason"] = (
                        "failed {} attempts; last: {}".format(t["attempts"], detail[:200]))
                    t["done"] = True          # removes it from next_open; `blocked` says why
            dirty = True
        if dirty:
            with open(self.pool_path, "w", encoding="utf-8") as f:
                json.dump(tasks, f, indent=2)
        self.release(task_id)
        return entry

    def stats(self) -> Dict[str, Any]:
        tasks = self.load()
        open_tasks = [t for t in tasks if not t.get("done")]
        classes: Dict[str, int] = {}
        for t in tasks:
            c = self.classify(t)
            classes[c] = classes.get(c, 0) + 1
        blocked = [t for t in tasks if t.get("blocked")]
        return {"total": len(tasks), "open": len(open_tasks),
                # `done` counts genuinely completed work only. Folding parked failures in here
                # would report a stuck pool as a finished one.
                "done": len(tasks) - len(open_tasks) - len(blocked),
                "blocked": len(blocked),
                "by_class": classes, "claims": len(self._claims)}

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
