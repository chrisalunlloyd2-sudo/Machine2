"""ToK Memory Harness — learnings ledger, recipe book, NMCT vault, NMTD DB.

Intercepts every candidate generation attempt, validates against known
learnings, retrieves canonical recipes, logs incidents on failure.
Compounding determinism: over time candidate generation drops toward zero
as the system pulls from the Recipe Book + NMCT Vault.
"""

import hashlib
import json
import os
import re
from typing import Any, Dict, List, Optional


class ToKMemoryHarness:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.learnings_file = os.path.join(base_dir, "learnings.md")
        self.recipes_dir = os.path.join(base_dir, "recipe_book")
        self.nmct_vault = os.path.join(base_dir, "nmct_vault")
        self.nmtd_db = os.path.join(base_dir, "nmtd_db")
        self._init_storage()

    def _init_storage(self) -> None:
        for d in (self.recipes_dir, self.nmct_vault, self.nmtd_db):
            os.makedirs(d, exist_ok=True)
        if not os.path.exists(self.learnings_file):
            with open(self.learnings_file, "w", encoding="utf-8") as f:
                f.write("# AGENT LEARNINGS LEDGER\n\n")

    # ---- 1. LEARNINGS LEDGER ------------------------------------------
    def load_active_rules(self, scope: str) -> List[str]:
        if not os.path.exists(self.learnings_file):
            return []
        content = open(self.learnings_file, encoding="utf-8").read()
        rules = []
        for block in content.split("## "):
            if f"Scope:** {scope}" in block or "Scope:** Universal" in block:
                m = re.search(r"- \*\*Rule:\*\* (.*)", block)
                if m:
                    rules.append(m.group(1).strip())
        return rules

    def append_learning(self, incident_id: str, scope: str, trigger: str,
                        outcome: str, rule: str) -> None:
        entry = (f"\n## [{incident_id}] Auto-Extracted Guardrail\n"
                 f"- **Scope:** {scope}\n- **Trigger:** {trigger}\n"
                 f"- **Negative Outcome:** {outcome}\n- **Rule:** {rule}\n")
        with open(self.learnings_file, "a", encoding="utf-8") as f:
            f.write(entry)

    # ---- 2. RECIPE BOOK -------------------------------------------------
    def fetch_recipe(self, performative_id: str) -> Optional[Dict[str, Any]]:
        p = os.path.join(self.recipes_dir, f"{performative_id}.json")
        if os.path.exists(p):
            return json.load(open(p, encoding="utf-8"))
        return None

    def save_recipe(self, performative_id: str, ast_skeleton: str,
                    params: Optional[Dict[str, str]] = None) -> None:
        with open(os.path.join(self.recipes_dir, f"{performative_id}.json"), "w", encoding="utf-8") as f:
            json.dump({"performative_id": performative_id,
                       "ast_skeleton": ast_skeleton,
                       "params": params or {}}, f, indent=2)

    def instantiate_recipe(self, recipe: Dict[str, Any], params: Dict[str, str]) -> str:
        code = recipe["ast_skeleton"]
        for k, v in params.items():
            code = code.replace("{{" + k + "}}", v)
        return code

    # ---- 3. RULE GATE -----------------------------------------------------
    def filter_candidates(self, candidates: List[str], active_rules: List[str]) -> List[str]:
        ok = []
        for cand in candidates:
            bad = False
            for rule in active_rules:
                if "raw multiline backticks" in rule and "```" in cand:
                    bad = True
                elif "no eval" in rule and re.search(r"\beval\s*\(", cand):
                    bad = True
                elif "no subprocess shell" in rule and "shell=True" in cand:
                    bad = True
                if bad:
                    break
            if not bad:
                ok.append(cand)
        return ok

    # ---- 4. NMTD — NEVER MAKE MISTAKES TWICE -------------------------------
    def log_critical_incident(self, slot_name: str, scope: str,
                              agents: List[str], error_logs: str,
                              failing_candidates: List[str]) -> str:
        h = hashlib.sha256(error_logs.encode()).hexdigest()[:8]
        incident_id = f"INC-{h.upper()}"
        data = {
            "incident_id": incident_id, "triggering_slot": slot_name,
            "scope": scope, "agents_involved": agents,
            "error_summary": error_logs[-500:],
            "exhausted_candidates_count": len(failing_candidates),
            "ts": __import__("time").time(),
        }
        with open(os.path.join(self.nmtd_db, f"{incident_id}.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        last = error_logs.splitlines()[-1] if error_logs else "Unknown Error"
        self.append_learning(incident_id, scope,
                             f"Exhaustion of candidates on slot '{slot_name}'",
                             "Sandbox failure across all race instances",
                             f"Avoid candidate patterns triggering: {last}")
        return incident_id

    def lookup_incident(self, fingerprint: str) -> Optional[Dict[str, Any]]:
        h = hashlib.sha256(fingerprint.encode()).hexdigest()[:8]
        p = os.path.join(self.nmtd_db, f"INC-{h.upper()}.json")
        if os.path.exists(p):
            return json.load(open(p, encoding="utf-8"))
        return None

    # ---- 5. NMCT — NEVER MAKE CODE TWICE VAULT ------------------------------
    def commit_canonical_code(self, slot_name: str, code: str,
                              execution_tape: List[Dict[str, Any]]) -> str:
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        entry = {"canonical_hash": code_hash, "slot_name": slot_name,
                 "code": code, "execution_tape": execution_tape}
        p = os.path.join(self.nmct_vault, f"{code_hash[:12]}.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(entry, f, indent=2)
        return code_hash[:12]

    def lookup_canonical(self, slot_name: str) -> Optional[Dict[str, Any]]:
        for fn in os.listdir(self.nmct_vault):
            if not fn.endswith(".json"):
                continue
            e = json.load(open(os.path.join(self.nmct_vault, fn), encoding="utf-8"))
            if e.get("slot_name") == slot_name:
                return e
        return None

    def vault_count(self) -> int:
        return len([f for f in os.listdir(self.nmct_vault) if f.endswith(".json")])

    def nmtd_count(self) -> int:
        return len([f for f in os.listdir(self.nmtd_db) if f.endswith(".json")])

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
