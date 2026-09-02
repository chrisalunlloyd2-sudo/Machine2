"""WRAPPED NMTD — Never Make Mistakes Twice database.

Full post-mortem incident records + auto-extracted guardrails.
Fingerprint-based: the same failure signature can never be retried
blindly. Consults the DB BEFORE attempting work.
"""

import hashlib
import json
import os
import time
from typing import Any, Dict, List, Optional

from .langdetect import detect_language


class NMTD:
    def __init__(self, db_dir: str, learnings_file: Optional[str] = None):
        self.db_dir = db_dir
        os.makedirs(db_dir, exist_ok=True)
        self.learnings_file = learnings_file

    @staticmethod
    def fingerprint(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:8]

    def incident_id(self, fingerprint_text: str) -> str:
        return f"INC-{self.fingerprint(fingerprint_text).upper()}"

    def record(self, slot_name: str, scope: str, agents: List[str],
               error_logs: str, failing_candidates: List[str],
               rule: Optional[str] = None) -> Dict[str, Any]:
        fp = self.fingerprint(error_logs)
        inc_id = f"INC-{fp.upper()}"
        data = {
            "incident_id": inc_id,
            "triggering_slot": slot_name,
            "scope": scope,
            "agents_involved": agents,
            "error_summary": error_logs[-500:],
            "fingerprint": fp,
            "exhausted_candidates_count": len(failing_candidates),
            "ts": time.time(),
        }
        with open(os.path.join(self.db_dir, f"{inc_id}.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        if rule is None:
            last = error_logs.splitlines()[-1] if error_logs else "Unknown Error"
            rule = f"Avoid candidate patterns triggering: {last}"
        if self.learnings_file:
            self._append_guardrail(inc_id, scope, slot_name, rule)
        return data

    def _append_guardrail(self, inc_id: str, scope: str, slot: str, rule: str) -> None:
        with open(self.learnings_file, "a", encoding="utf-8") as f:
            f.write(f"\n## [{inc_id}] Auto-Extracted Guardrail\n"
                    f"- **Scope:** {scope}\n- **Trigger:** failure on slot '{slot}'\n"
                    f"- **Rule:** {rule}\n")

    def check(self, error_signature: str) -> Optional[Dict[str, Any]]:
        """Never-try-twice gate: has this exact failure happened before?"""
        inc_id = self.incident_id(error_signature)
        p = os.path.join(self.db_dir, f"{inc_id}.json")
        if os.path.exists(p):
            return json.load(open(p, encoding="utf-8"))
        return None

    def list_incidents(self) -> List[Dict[str, Any]]:
        out = []
        for fn in os.listdir(self.db_dir):
            if fn.startswith("INC-") and fn.endswith(".json"):
                out.append(json.load(open(os.path.join(self.db_dir, fn),
                                          encoding="utf-8")))
        return sorted(out, key=lambda x: x.get("ts", 0))

    def count(self) -> int:
        return len([f for f in os.listdir(self.db_dir)
                    if f.startswith("INC-") and f.endswith(".json")])

    # ---- step-level recorder (steps that do NOT work) --------------------
    def step_id(self, step: str) -> str:
        return f"STEP-{self.fingerprint(step).upper()}"

    def record_step(self, step: str, error_logs: str = "",
                    language: Optional[str] = None,
                    scope: str = "") -> Dict[str, Any]:
        """Record a granular STEP that failed so it can never be retried."""
        sid = self.step_id(step)
        data = {
            "step_id": sid,
            "step": step,
            "error_summary": (error_logs or "")[-300:],
            "language": language or detect_language(slot=step),
            "scope": scope,
            "ts": time.time(),
        }
        with open(os.path.join(self.db_dir, f"{sid}.json"), "w") as f:
            json.dump(data, f, indent=2)
        return data

    def check_step(self, step: str) -> Optional[Dict[str, Any]]:
        """Never-try-twice gate: has this exact step already failed?"""
        sid = self.step_id(step)
        p = os.path.join(self.db_dir, f"{sid}.json")
        if os.path.exists(p):
            return json.load(open(p))
        return None

    def failed_steps(self) -> List[Dict[str, Any]]:
        out = []
        for fn in os.listdir(self.db_dir):
            if fn.startswith("STEP-") and fn.endswith(".json"):
                out.append(json.load(open(os.path.join(self.db_dir, fn))))
        return sorted(out, key=lambda x: x.get("ts", 0))

    def step_count(self) -> int:
        return len(self.failed_steps())

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
