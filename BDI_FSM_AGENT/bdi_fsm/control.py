"""AEGIS CONTROL CHANNEL — the agent is controlled by Aegis.

The agent never acts on the outside world directly. It proposes actions
to a queue; Aegis (the sovereign brain) reviews, approves/denies, and
executes. The agent executes locally-verifiable internal steps only.

Queue: proposals.jsonl (append-only) + approved/denied responses.
"""

import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional


class ControlChannel:
    def __init__(self, queue_dir: str):
        self.queue_dir = queue_dir
        os.makedirs(queue_dir, exist_ok=True)
        self.proposals_path = os.path.join(queue_dir, "proposals.jsonl")
        self.responses_path = os.path.join(queue_dir, "responses.jsonl")

    def propose(self, action: str, target: str, payload: Optional[Dict[str, Any]] = None,
                priority: int = 5, reason: str = "") -> Dict[str, Any]:
        """Agent proposes an external action for Aegis approval."""
        proposal = {
            "proposal_id": uuid.uuid4().hex[:12],
            "ts": time.time(),
            "agent": "bdi-fsm-agent",
            "action": action,
            "target": target,
            "payload": payload or {},
            "priority": priority,
            "reason": reason,
            "status": "PENDING",
        }
        with open(self.proposals_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(proposal) + "\n")
        return proposal

    def pending(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.proposals_path):
            return []
        return [json.loads(l) for l in open(self.proposals_path, encoding="utf-8")
                if json.loads(l).get("status") == "PENDING"]

    def respond(self, proposal_id: str, decision: str, note: str = "") -> None:
        """Aegis responds: approve / deny / defer."""
        lines = []
        if os.path.exists(self.proposals_path):
            lines = open(self.proposals_path, encoding="utf-8").readlines()
        with open(self.proposals_path, "w", encoding="utf-8") as f:
            for line in lines:
                p = json.loads(line)
                if p.get("proposal_id") == proposal_id:
                    p["status"] = decision.upper()
                    p["response_note"] = note
                f.write(json.dumps(p) + "\n")
        with open(self.responses_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"proposal_id": proposal_id,
                                "decision": decision.upper(),
                                "note": note, "ts": time.time()}) + "\n")

    def get_response(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        if not os.path.exists(self.responses_path):
            return None
        for line in reversed(open(self.responses_path, encoding="utf-8").readlines()):
            r = json.loads(line)
            if r.get("proposal_id") == proposal_id:
                return r
        return None
