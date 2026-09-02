"""DETERMINISTIC ACTION JOURNAL — append-only, hash-chained recording.

Every agent action + outcome is recorded as a chained record
(prev_hash + sha256), so the full decision trail is replayable and
tamper-evident. This is the recording half of "better learning and
recording behavior" — the learning half (RecursiveLearner) reads this
journal to mirror tokens and derive guardrails.

Pure stdlib. No cloud, no LLM.
"""

import hashlib
import json
import os
import time
from typing import Any, Dict, List, Optional


class DeterministicActionJournal:
    def __init__(self, journal_path: str):
        self.path = journal_path
        self._seq = 0
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        if os.path.exists(self.path):
            # resume sequence from last record
            try:
                for line in open(self.path, encoding="utf-8"):
                    line = line.strip()
                    if line:
                        self._seq = json.loads(line).get("seq", 0)
            except Exception:
                pass

    @staticmethod
    def _hash(record: Dict[str, Any]) -> str:
        body = dict(record)
        body.pop("hash", None)
        canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()

    def _prev_hash(self) -> str:
        if not os.path.exists(self.path):
            return hashlib.sha256(b"GENESIS").hexdigest()
        lines = [l for l in open(self.path, encoding="utf-8") if l.strip()]
        if not lines:
            return hashlib.sha256(b"GENESIS").hexdigest()
        return json.loads(lines[-1]).get("hash", "")

    def record(self, agent: str, action: str, detail: str,
               outcome: str = "ok", meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Append one action record. outcome: ok|fail|block|defer."""
        self._seq += 1
        record = {
            "ts": time.time(),
            "seq": self._seq,
            "agent": agent,
            "action": action,
            "detail": detail[:4000],
            "outcome": outcome,
            "meta": meta or {},
            "prev_hash": self._prev_hash(),
        }
        record["hash"] = self._hash(record)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        return record

    def entries(self, limit: Optional[int] = None, outcome: Optional[str] = None,
                agent: Optional[str] = None) -> List[Dict[str, Any]]:
        rows = []
        if os.path.exists(self.path):
            for line in open(self.path, encoding="utf-8"):
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if outcome and e.get("outcome") != outcome:
                    continue
                if agent and e.get("agent") != agent:
                    continue
                rows.append(e)
        if limit:
            rows = rows[-limit:]
        return rows

    def verify(self) -> Dict[str, Any]:
        """Replay the chain; return ok + first broken seq if tampered."""
        rows = self.entries()
        prev = hashlib.sha256(b"GENESIS").hexdigest()
        for e in rows:
            if e.get("prev_hash") != prev:
                return {"ok": False, "broken_at": e.get("seq"), "reason": "prev_hash_mismatch"}
            if e.get("hash") != self._hash(e):
                return {"ok": False, "broken_at": e.get("seq"), "reason": "hash_mismatch"}
            prev = e.get("hash", "")
        return {"ok": True, "count": len(rows)}

    def stats(self) -> Dict[str, Any]:
        rows = self.entries()
        counts: Dict[str, int] = {}
        for e in rows:
            counts[e.get("outcome", "?")] = counts.get(e.get("outcome", "?"), 0) + 1
        return {"count": len(rows), "by_outcome": counts}

    def suggest_guardrails(self, min_fails: int = 1) -> List[Dict[str, str]]:
        """Derive (trigger, rule) guardrails from failing entries."""
        fails = self.entries(outcome="fail")
        seen = set()
        out = []
        for e in fails:
            trigger = e.get("action", "unknown_action")
            detail = e.get("detail", "")[:160]
            key = f"{trigger}|{detail[:40]}"
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "trigger": trigger,
                "rule": f"Never {trigger} blindly when: {detail}",
                "agent": e.get("agent", "?"),
                "seq": e.get("seq"),
            })
            if len(out) >= min_fails * 10:
                break
        return out

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
