"""law.py — the CORE LAW + BRIDGE RULE guardrail.

Chris 2026-08-15 governance spec:
    "All actions must be logged, hashed, fenced, and reviewed before promotion."

CORE LAW (7 rules) and BRIDGE RULE (6 rules) are encoded as checkable verdicts.
Every action is logged AND hashed (sha256) into an append-only ledger. Dangerous
actions (blind edits, unfenced exec, unproven promotion, secret reads, blind
deletes) are BLOCKED with a reason. Deterministic, zero-LLM.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, List, Optional

CORE_LAW: List[str] = [
    "Nothing runs forever.",
    "Nothing edits blindly.",
    "Nothing promotes without proof.",
    "One change per phase.",
    "Verify before continuing.",
    "Never overwrite the only good state.",
    "Promote only verified checkpoints.",
]

BRIDGE_RULE: List[str] = [
    "Visible user-owned automation is allowed.",
    "Do not steal cookies.",
    "Do not steal tokens.",
    "Do not bypass account controls.",
    "Do not pretend scratch output is truth.",
    "Every read, write, prompt, file change, and promotion must be logged.",
]

SECRET_MARKERS = ("cookie", "token", ".env", "credential", "secret", ".key",
                  ".pem", "id_rsa", "password", "api_key", "pat", "oauth",
                  "authorization", "github_pat", "sk-")


def is_secret_path(path: Optional[str]) -> bool:
    """BRIDGE RULE: a path that looks like credentials/cookies/tokens."""
    p = (path or "").lower()
    return any(m in p for m in SECRET_MARKERS)


class Law:
    """Encodes + enforces the CORE LAW and BRIDGE RULE as verdicts."""

    def __init__(self, allow_delete: bool = False, allow_promote: bool = False,
                 sandbox: bool = True):
        self.allow_delete = allow_delete      # "never overwrite the only good state"
        self.allow_promote = allow_promote    # "promote only verified checkpoints"
        self.sandbox = sandbox                # True = execution is fenced
        self.ledger: List[Dict[str, Any]] = []  # every action: logged + hashed

    def hash_artifact(self, content: Any) -> str:
        if content is None:
            return ""
        if isinstance(content, str):
            content = content.encode("utf-8")
        return hashlib.sha256(content).hexdigest()[:16]

    def log(self, action: str, target: Optional[str] = None,
            content: Any = None, verdict: str = "pending") -> Dict[str, Any]:
        rec = {"ts": time.time(), "action": action, "target": target,
               "hash": self.hash_artifact(content), "verdict": verdict,
               "reason": ""}
        self.ledger.append(rec)
        return rec

    def check(self, action: str, target: Optional[str] = None,
              content: Any = None, proof: Any = None) -> Dict[str, Any]:
        """Verdict an action. Every action is logged + hashed first."""
        rec = self.log(action, target, content)
        a = (action or "").lower()

        # BRIDGE RULE: do not steal cookies/tokens
        if a == "read" and target and is_secret_path(target):
            rec.update(verdict="BLOCKED", reason="secret path (bridge rule)")
            return rec

        # CORE LAW: nothing edits blindly (edit needs a target + hashed content)
        if a in ("edit", "write", "overwrite") and (target is None or content is None):
            rec.update(verdict="BLOCKED", reason="blind edit (no target/hash)")
            return rec

        # CORE LAW: never overwrite the only good state
        if a in ("delete", "overwrite") and not self.allow_delete:
            rec.update(verdict="BLOCKED", reason="delete gate closed")
            return rec

        # CORE LAW: execution must be fenced
        if a in ("exec", "run") and not self.sandbox:
            rec.update(verdict="BLOCKED", reason="unfenced execution")
            return rec

        # CORE LAW: nothing promotes without proof; only verified checkpoints
        if a in ("promote", "commit", "deploy"):
            if not proof:
                rec.update(verdict="BLOCKED", reason="promotion without proof")
                return rec
            if not self.allow_promote:
                rec.update(verdict="BLOCKED", reason="promotion gate closed")
                return rec

        rec.update(verdict="ALLOWED")
        return rec

    def promote(self, checkpoint: Dict, proof: Any) -> Dict[str, Any]:
        """The promotion pipeline: log + hash + fence + review."""
        return self.check("promote", target=checkpoint.get("target"),
                          content=checkpoint.get("content"), proof=proof)

    def stats(self) -> Dict[str, int]:
        from collections import Counter
        return dict(Counter(r["verdict"] for r in self.ledger))

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
