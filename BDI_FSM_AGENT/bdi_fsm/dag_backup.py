"""DAG BACKUP — scrub + render entity DAGs to the private BDI_FSM_DAGs repo.

The git artifact is a PROJECTION, not live state: render_all(scrub_pii=True)
redacts PII/secrets, then one JSON per entity + an index is committed and
pushed. ADD-only at the DAG level; the repo history is the audit trail.

Pure stdlib (git via subprocess). Deterministic. Zero LLM.
"""
import json
import os
import subprocess
import time
from typing import Any, Dict, Optional

from .world_model import WorldModel


def render_world(world: WorldModel) -> Dict[str, Any]:
    """Scrubbed render of every entity DAG + stats."""
    return {
        "rendered_at": time.time(),
        "stats": world.stats(),
        "entities": world.render_all(scrub_pii=True),
    }


def backup(world: WorldModel, repo_dir: str, commit_message: Optional[str] = None,
           push: bool = True) -> Dict[str, Any]:
    """Write scrubbed renders into a git repo dir; commit (+push)."""
    os.makedirs(os.path.join(repo_dir, "dags"), exist_ok=True)
    payload = render_world(world)
    for eid, dag in payload["entities"].items():
        with open(os.path.join(repo_dir, "dags", f"{eid}.json"), "w") as f:
            json.dump(dag, f, indent=2)
    with open(os.path.join(repo_dir, "index.json"), "w") as f:
        json.dump({"rendered_at": payload["rendered_at"],
                   "stats": payload["stats"],
                   "entities": sorted(payload["entities"].keys())}, f, indent=2)

    out: Dict[str, Any] = {"entities": len(payload["entities"])}
    if not os.path.isdir(os.path.join(repo_dir, ".git")):
        out["error"] = f"not a git repo: {repo_dir}"
        return out
    subprocess.run(["git", "-C", repo_dir, "add", "-A"], check=False,
                   capture_output=True)
    msg = commit_message or f"dag render {time.strftime('%Y-%m-%d %H:%M:%S')}"
    subprocess.run(["git", "-C", repo_dir, "commit", "-m", msg, "--allow-empty"],
                   check=False, capture_output=True)
    if push:
        r = subprocess.run(["git", "-C", repo_dir, "push"], check=False,
                           capture_output=True, text=True)
        out["push"] = {"ok": r.returncode == 0,
                       "stderr": (r.stderr or "")[-300:]}
    return out
