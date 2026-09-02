"""WRAPPED NMCT — Never Make Code Twice vault with seal/verify.

Canonical code + execution tape, sealed with SHA-256, verified on read.
Anything sealed can be re-derived; nothing unsealed is trusted.
"""

import hashlib
import json
import os
import time
from typing import Any, Dict, List, Optional

from .langdetect import detect_language


class NMCTSealError(Exception):
    pass


class NMCT:
    def __init__(self, vault_dir: str):
        self.vault_dir = vault_dir
        os.makedirs(vault_dir, exist_ok=True)

    @staticmethod
    def _seal(code: str) -> str:
        return hashlib.sha256(code.encode()).hexdigest()

    def seal(self, slot_name: str, code: str,
             execution_tape: List[Dict[str, Any]],
             source: str = "agent",
             language: Optional[str] = None) -> Dict[str, Any]:
        """Seal canonical code + tape into the vault. Returns the entry.

        Tagged with a timestamp and a detected programming language so the
        vault is TIMESTAMPED and ORGANISED BY LANGUAGE (never code twice)."""
        h = self._seal(code)
        entry = {
            "canonical_hash": h,
            "slot_name": slot_name,
            "code": code,
            "execution_tape": execution_tape,
            "source": source,
            "sealed": True,
            "ts": time.time(),
            "language": language or detect_language(code=code, slot=slot_name),
        }
        p = os.path.join(self.vault_dir, f"{h[:12]}.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(entry, f, indent=2)
        return entry

    def verify(self, code: str) -> bool:
        """Check whether this exact code already exists sealed."""
        h = self._seal(code)
        return os.path.exists(os.path.join(self.vault_dir, f"{h[:12]}.json"))

    def get(self, code: str) -> Optional[Dict[str, Any]]:
        h = self._seal(code)
        p = os.path.join(self.vault_dir, f"{h[:12]}.json")
        if os.path.exists(p):
            e = json.load(open(p, encoding="utf-8"))
            if e.get("canonical_hash") != h:
                raise NMCTSealError("seal mismatch — tampered vault entry")
            return e
        return None

    def lookup(self, slot_name: str) -> Optional[Dict[str, Any]]:
        for fn in os.listdir(self.vault_dir):
            if not fn.endswith(".json"):
                continue
            e = json.load(open(os.path.join(self.vault_dir, fn), encoding="utf-8"))
            if e.get("slot_name") == slot_name:
                return e
        return None

    def count(self) -> int:
        return len([f for f in os.listdir(self.vault_dir) if f.endswith(".json")])

    def by_language(self, lang: str) -> List[Dict[str, Any]]:
        """All sealed entries tagged with the given programming language."""
        out = []
        for fn in os.listdir(self.vault_dir):
            if not fn.endswith(".json"):
                continue
            try:
                e = json.load(open(os.path.join(self.vault_dir, fn)))
            except Exception:
                continue
            tag = e.get("language") or detect_language(
                code=e.get("code", ""), slot=e.get("slot_name", ""))
            if tag == lang:
                out.append(e)
        return out

    def languages(self) -> List[str]:
        """The set of programming languages present in the vault."""
        seen = set()
        for fn in os.listdir(self.vault_dir):
            if not fn.endswith(".json"):
                continue
            try:
                e = json.load(open(os.path.join(self.vault_dir, fn)))
            except Exception:
                continue
            seen.add(e.get("language") or detect_language(
                code=e.get("code", ""), slot=e.get("slot_name", "")))
        return sorted(seen)

    def audit(self) -> Dict[str, Any]:
        """Full vault integrity audit. Returns counts + tamper list."""
        sealed = 0
        tampered = []
        for fn in os.listdir(self.vault_dir):
            if not fn.endswith(".json"):
                continue
            try:
                e = json.load(open(os.path.join(self.vault_dir, fn), encoding="utf-8"))
                if e.get("canonical_hash") == self._seal(e.get("code", "")):
                    sealed += 1
                else:
                    tampered.append(fn)
            except Exception:
                tampered.append(fn)
        return {"sealed_valid": sealed, "tampered": tampered,
                "total": sealed + len(tampered)}

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
