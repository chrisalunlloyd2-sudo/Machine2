"""HEX FOW — spatial fog-of-war locking.

Every task claims a hex before running; stale claims (> ttl) are
released. Prevents duplicate execution across cron overlaps, shell
restarts and manual runs. Pure stdlib, file-backed.
"""

import json
import os
import time
import uuid
from typing import Any, Dict, Optional


class FOW:
    def __init__(self, state_path: str, ttl_seconds: int = 480):
        self.state_path = state_path
        self.ttl = ttl_seconds
        os.makedirs(os.path.dirname(state_path), exist_ok=True) if os.path.dirname(state_path) else None
        if not os.path.exists(state_path):
            self._write({})

    def _read(self) -> Dict[str, Any]:
        try:
            return json.load(open(self.state_path, encoding="utf-8"))
        except Exception:
            return {}

    def _write(self, data: Dict[str, Any]) -> None:
        tmp = self.state_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, self.state_path)

    def claim(self, task_id: str, owner: str = "bdi-fsm-agent") -> bool:
        state = self._read()
        now = time.time()
        # sweep stale
        for k, v in list(state.items()):
            if now - v.get("ts", 0) > self.ttl:
                del state[k]
        if task_id in state:
            return False
        state[task_id] = {"owner": owner, "pid": os.getpid(),
                          "ts": now, "claim_id": uuid.uuid4().hex[:8]}
        self._write(state)
        return True

    def release(self, task_id: str, owner: Optional[str] = None) -> bool:
        """Release a claim. With `owner`, ONLY if that owner still holds it.

        Two hazards this closes, both of which only bite once the claim is used as a CONTRACT
        between several parties rather than as a lock inside one process:

        1. ANYONE COULD RELEASE ANYONE'S CLAIM. Nothing checked who was asking, so BDI finishing
           its own task could drop the contract Aegis was holding on a different one, and the next
           claimant would walk straight in.

        2. A LATE WORKER RELEASED THE WRONG HOLDER. If a claim expires and someone else takes it,
           the original worker finishing afterwards would delete the NEW holder's claim — the
           classic expired-lease bug, and the reason a lease has a fencing token at all.
           `claim_id` already exists on every record and was never checked; now it is.

        owner=None keeps the old unconditional behaviour, because the in-process callers that use
        this as a plain lock are correct as they are.
        """
        state = self._read()
        cur = state.get(task_id)
        if not cur:
            return False
        # An EXPIRED claim is not held, whatever the file still says.
        #
        # held() has always honoured the TTL, but release() read the record directly and stale
        # entries are only swept by claim(). So a worker whose lease had run out could still
        # release -- and therefore still close a contract it no longer owned. It cannot know
        # whether someone else picked the work up and redid it in the meantime, which is the
        # whole reason the lease exists.
        if time.time() - cur.get("ts", 0) > self.ttl:
            del state[task_id]          # sweep it, but report that it was not held
            self._write(state)
            return False
        if owner is not None and cur.get("owner") != owner:
            return False
        del state[task_id]
        self._write(state)
        return True

    def release_reason(self, task_id: str, owner: Optional[str] = None) -> Dict[str, Any]:
        """Why a release did or did not happen. `release` returns a bare bool and False means
        three different things -- never held, held by someone else, or already expired and swept.
        A contract layer has to tell those apart to know whether its work still counts."""
        state = self._read()
        cur = state.get(task_id)
        if not cur:
            return {"released": False, "why": "not held (never claimed, or already expired)"}
        if time.time() - cur.get("ts", 0) > self.ttl:
            return {"released": False, "why": "lease expired %.0fs ago" % (
                time.time() - cur.get("ts", 0) - self.ttl), "holder": cur.get("owner"),
                "expired": True}
        holder = cur.get("owner")
        if owner is not None and holder != owner:
            return {"released": False, "why": "held by %s, not %s" % (holder, owner),
                    "holder": holder}
        ok = self.release(task_id, owner=owner)
        return {"released": ok, "holder": holder}

    def held(self, task_id: str) -> Optional[Dict[str, Any]]:
        state = self._read()
        v = state.get(task_id)
        if v and time.time() - v.get("ts", 0) <= self.ttl:
            return v
        return None

    def snapshot(self) -> Dict[str, Any]:
        return self._read()
