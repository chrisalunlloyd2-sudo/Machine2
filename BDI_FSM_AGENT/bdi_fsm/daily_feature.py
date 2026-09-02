"""DAILY FEATURE UPDATER — BDI_FSM owns the Daily Feature for its sibling repos.

Chris's side quest: BDI_FSM updates the Daily Feature (living-ascii-art
gitpage section) with changes and updates to mind-palace and/or SIMS1337.

Deterministic flow:
  1. scan local clones of mind-palace + SIMS1337 (git log since last sha)
  2. if new commits -> compose a feature entry (repo, sha, date, message,
     changed files, small code slice when useful)
  3. if nothing new   -> reuse the previous feature with a note
  4. push daily_feature.json to living-ascii-art (token at call time)

The BDI agent can trigger it via verb flags ("update daily feature",
"feature sims1337", "publish mind-palace changes") — it's a behavior-tree
action. Also runs as one of the triple-loop hourly channels.

Pure stdlib. Zero LLM. Token read from /root/.secrets/github_token at
call time (never hardcoded — tokens go stale).
"""

import base64
import json
import os
import subprocess
import time
import urllib.request
import urllib.error
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

OWNER = "chrisalunlloyd2-sudo"
LIVING_REPO = f"{OWNER}/living-ascii-art"
FEATURE_PATH = "daily_feature.json"
TOKEN_FILE = "/root/.secrets/github_token"

# sibling repos BDI_FSM features + their local clones
TRACKED = [
    {"repo": "mind-palace", "clone": "/root/scan_tmp/mind-palace", "branch": "main"},
    {"repo": "SIMS1337", "clone": "/root/scan_tmp/SIMS1337", "branch": "main"},
    {"repo": "karoo-hexeract", "clone": "/tmp/karoo-hexeract", "branch": "main"},
    {"repo": "karoo_gp", "clone": "/root/scan_tmp/karoo_gp", "branch": "main"},
]


def _token() -> str:
    try:
        return open(TOKEN_FILE).read().strip()
    except Exception:
        return ""


def gh(path: str, timeout: int = 30, retries: int = 3) -> Any:
    tok = _token()
    if not tok:
        return {"error": "no token"}
    for a in range(retries):
        req = urllib.request.Request("https://api.github.com" + path, headers={
            "Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (401, 403, 502) and a < retries - 1:
                time.sleep(3)
                continue
            return {"error": e.code, "msg": e.read()[:150].decode(errors="replace")}
        except Exception:
            if a < retries - 1:
                time.sleep(2)
                continue
            return {"error": "net"}
    return {"error": "retries"}


def put_file(path: str, content_b64: str, msg: str) -> Any:
    tok = _token()
    data = {"message": msg, "content": content_b64}
    cur = gh(f"/repos/{LIVING_REPO}/contents/{path}")
    if isinstance(cur, dict) and "sha" in cur:
        data["sha"] = cur["sha"]
    req = urllib.request.Request(f"https://api.github.com/repos/{LIVING_REPO}/contents/{path}",
        method="PUT", headers={"Authorization": f"Bearer {tok}",
                               "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, json.dumps(data).encode(), timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {"error": e.code, "msg": e.read()[:200].decode(errors="replace")}


def git_log(clone: str, branch: str, since_sha: Optional[str] = None) -> List[Dict]:
    """Read local git log since last seen sha (or last 5 if none)."""
    if not os.path.isdir(os.path.join(clone, ".git")):
        return []
    args = ["git", "-C", clone, "log", "--oneline", "--no-decorate", "-30"]
    if since_sha:
        args += [f"{since_sha}..HEAD"]
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=20)
        out = r.stdout.strip()
        if not out:
            return []
        commits = []
        for line in out.splitlines():
            parts = line.split(" ", 1)
            if len(parts) == 2:
                commits.append({"sha": parts[0], "msg": parts[1][:120]})
        return commits
    except Exception:
        return []


def changed_files(clone: str, sha: str) -> List[str]:
    try:
        r = subprocess.run(["git", "-C", clone, "show", "--stat",
                            "--oneline", sha], capture_output=True, text=True, timeout=20)
        files = []
        for line in (r.stdout or "").splitlines():
            line = line.strip()
            if "|" in line and line.endswith((")", "+", "-", "++")):
                files.append(line.split("|")[0].strip())
        return files[:12]
    except Exception:
        return []


def code_slice(clone: str, sha: str, max_lines: int = 18) -> Tuple[str, str]:
    """Grab a small readable slice of the newest .py/.java/.sh touched."""
    try:
        r = subprocess.run(["git", "-C", clone, "show", "--name-only",
                            "--format=", sha], capture_output=True, text=True, timeout=20)
        for p in (r.stdout or "").splitlines():
            p = p.strip()
            if not p or p.endswith((".md", ".json", ".png", ".jpg", ".txt")):
                continue
            if p.endswith((".py", ".java", ".sh")):
                got = subprocess.run(["git", "-C", clone, "show",
                                      f"{sha}:{p}"], capture_output=True, text=True, timeout=20)
                if got.returncode == 0:
                    lines = (got.stdout or "").splitlines()
                    code = "\n".join(lines[:max_lines])
                    lang = "python" if p.endswith(".py") else ("java" if p.endswith(".java") else "bash")
                    return code, lang
    except Exception:
        pass
    return "", ""


def run(dry_run: bool = False, state_dir: Optional[str] = None,
        force: bool = False) -> Dict[str, Any]:
    """Scan siblings, compose the feature, push. Returns the feature dict."""
    state_path = os.path.join(state_dir or "/root/hexgame",
                              "daily_feature_state.json")
    os.makedirs(os.path.dirname(state_path), exist_ok=True)
    state = {}
    if os.path.exists(state_path):
        try:
            state = json.load(open(state_path))
        except Exception:
            state = {}
    prev = state.get("feature", {})
    last_sha = state.get("last_sha", {})

    today = date.today().isoformat()
    newest = None  # (repo, sha, msg, commits)
    scans = {}
    for t in TRACKED:
        commits = git_log(t["clone"], t["branch"], last_sha.get(t["repo"]))
        scans[t["repo"]] = commits
        if commits:
            c = commits[0]
            if newest is None or c["sha"] > newest[1]:
                newest = (t["repo"], c["sha"], c["msg"], commits)

    # fetch upstream to be sure (local clones may lag)
    if not newest and not force:
        pass  # local scan only — paced, no network fetch storm

    feature = None
    if newest:
        repo, sha, msg, commits = newest
        files = changed_files(TRACKED[[t["repo"] for t in TRACKED].index(repo)]["clone"], sha)
        code, lang = code_slice(TRACKED[[t["repo"] for t in TRACKED].index(repo)]["clone"], sha)
        n_commits = len(commits)
        if code:
            feature = {
                "date": today, "type": "code", "repo": repo, "commit": sha,
                "title": f"Daily Feature — {repo}",
                "code": code, "language": lang,
                "description": msg,
                "explanation": (f"{n_commits} new commit(s) in {repo} since the last "
                                f"feature ({', '.join(c['msg'][:50] for c in commits[:3])}). "
                                f"BDI_FSM_AGENT surfaced this slice from the newest change."),
                "is_new": True, "note": "fresh via BDI_FSM triple loop",
                "files": files[:6],
            }
        else:
            feature = {
                "date": today, "type": "commit", "repo": repo, "commit": sha,
                "title": f"Daily Feature — {repo}",
                "description": msg,
                "explanation": (f"{n_commits} new commit(s) in {repo} since last check. "
                                f"Changes touch: {', '.join(files[:6]) or 'docs/state'}."),
                "is_new": True, "note": "fresh via BDI_FSM triple loop",
                "files": files[:6],
            }
        # update state
        state["last_sha"] = dict(last_sha)
        state["last_sha"][repo] = sha
        state["feature"] = feature
        state["last_date"] = today

    else:
        if prev:
            feature = dict(prev)
            feature["date"] = today
            feature["is_new"] = False
            feature["note"] = "no new sibling changes — showing previous feature (BDI_FSM)"
        else:
            feature = {
                "date": today, "type": "commit", "repo": "SIMS1337",
                "title": "Daily Feature — SIMS1337",
                "description": "The deterministic agent foundry — ADD-only, quality-gated.",
                "explanation": "Seed feature from BDI_FSM_AGENT. No sibling changes yet.",
                "is_new": True, "note": "seed",
            }
        state["feature"] = feature
        state["last_date"] = today

    # persist state (local)
    with open(state_path, "w") as f:
        json.dump(state, f, indent=1)

    if dry_run:
        return {"ok": True, "dry_run": True, "feature": feature, "scans": {
            k: [c["sha"] for c in v] for k, v in scans.items()}}

    out = json.dumps(feature, indent=1)
    r = put_file(FEATURE_PATH, base64.b64encode(out.encode()).decode(),
                 f"daily feature: {feature.get('type')} {feature.get('repo','')} "
                 f"({'new' if feature.get('is_new') else 'reuse'}) [BDI-FSM]")
    return {"ok": "content" in r or "commit" in r, "feature": feature,
            "push": r if "content" not in r else {"sha": r.get("content", {}).get("sha", "")},
            "scans": {k: [c["sha"] for c in v] for k, v in scans.items()}}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="BDI_FSM Daily Feature updater")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--state", default="/root/hexgame")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    res = run(dry_run=a.dry_run, state_dir=a.state, force=a.force)
    print(json.dumps({k: v for k, v in res.items() if k != "feature"}, indent=1)[:1200])
    f = res.get("feature", {})
    print("feature:", f.get("date"), f.get("type"), f.get("repo"), f.get("commit"),
          "|", (f.get("description") or "")[:80])
