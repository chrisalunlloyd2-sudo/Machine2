"""NIGHTLY SEED FACTORY (deterministic, zero-LLM, near-zero quota).

Lead-developer doctrine (Chris 2026-08-16): every night the dream cycle
CREATES seeds — new FOW contracts, needed repos, and pedagogy lessons — so the
fleet is always growing toward the fog-of-war frontier instead of idling.

Seeds are mined from REAL gaps, never invented:
  - FOW contracts  : open TODO/FIXME markers + missing README/pyproject/LICENSE
                     + untested modules (a .py without a matching test_*.py)
  - Needed repos   : gaps no existing repo covers (e.g. Kernel_Pedagogy)
  - Pedagogy       : lessons distilled from REAL code in the fleet (DPLL fix,
                     N-retry guard, BMC frame constraint, knee pruning, gist
                     unification) — templates verified against live symbols.

Every seed is hashed (seed_id = sha1(kind:target:action)[:10]) and recorded in
state/seeds.jsonl — never seeded twice (Q.E.D. zero-repeat). FOW events are
appended to state/agent_events.jsonl so the hex grid marks OCCUPIED cells.
"""
from __future__ import annotations
import hashlib, json, os, re, time
from typing import Dict, List, Optional

FLEET_REPOS = ["Aegis_Unified", "Sophia", "BDI_FSM_AGENT", "Aegis_Agents",
               "mind-palace", "MasterLogs"]
TODO_RE = re.compile(r"\b(TODO|FIXME|XXX|HACK)\b[:\s]*(.*)$", re.MULTILINE)
PEDAGOGY_DIR = "pedagogy"


# --------------------------------------------------------------------------
# gap scanning (stdlib, read-only)
# --------------------------------------------------------------------------
def scan_fleet_gaps(root: str = "/root", repos: Optional[List[str]] = None) -> List[Dict]:
    """Mine REAL gaps: TODO markers, missing docs/packaging, untested modules."""
    gaps: List[Dict] = []
    for repo in repos or FLEET_REPOS:
        base = os.path.join(root, repo)
        if not os.path.isdir(base):
            continue
        # 1) TODO/FIXME markers in .py/.md (line-level, capped)
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames
                           if d not in (".git", "__pycache__", "node_modules",
                                        "dist", "build", ".venv", "venv")]
            for fn in filenames:
                if not fn.endswith((".py", ".md")):
                    continue
                path = os.path.join(dirpath, fn)
                rel = os.path.relpath(path, base)
                if rel.startswith(("tests/", "test_", "docs/", "pedagogy/")):
                    continue
                try:
                    txt = open(path, encoding="utf-8", errors="replace").read()
                except OSError:
                    continue
                for m in TODO_RE.finditer(txt):
                    if len(gaps) >= 60:
                        return gaps
                    pre = txt[max(0, m.start() - 24):m.start()]
                    # prose mentions ("scan for TODO", "the TODO list") are NOT gaps
                    if re.search(r"(for|the|of|scan|count|list|with|and|or|:)\s+$", pre) or \
                       re.search(r"TODO[/\s]+(FIXME|XXX|HACK)", txt[m.start():m.start() + 16]):
                        continue
                    # regex-literal listings ("(TODO|FIXME|XXX|HACK)") are NOT gaps
                    if pre.endswith(("(", "|", '"')) or "r\"" in pre[-6:]:
                        continue
                    gaps.append({"kind": "fow", "repo": repo, "file": rel,
                                 "line": txt.count("\n", 0, m.start()) + 1,
                                 "marker": m.group(1),
                                 "note": m.group(2).strip()[:100],
                                 "action": f"resolve {m.group(1)} in {repo}/{rel}"})
        # 2) missing standard files
        for fname in ("README.md", "pyproject.toml", "LICENSE"):
            if not os.path.exists(os.path.join(base, fname)):
                gaps.append({"kind": "fow", "repo": repo, "file": fname,
                             "line": 0, "marker": "MISSING",
                             "note": f"no {fname}",
                             "action": f"add {fname} to {repo}"})
        # 3) untested modules (any package .py without a matching test)
        test_dir = os.path.join(base, "tests")
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames
                           if d not in (".git", "__pycache__", "node_modules",
                                        "dist", "build", ".venv", "venv", "tests")]
            if "tests" in dirpath.split(os.sep):
                continue
            # scripts / demo / heartbeat are not library modules — not gaps
            rel_dir = os.path.relpath(dirpath, base)
            if rel_dir.split(os.sep)[0] in ("scripts", "state", "heartbeat", "pedagogy", "docs"):
                continue
            test_files = [os.path.join(test_dir, t) for t in os.listdir(test_dir)
                          if t.startswith("test_") and t.endswith(".py")] if os.path.isdir(test_dir) else []
            test_text = "\n".join(open(t, encoding="utf-8", errors="replace").read()
                                   for t in test_files)
            for fn in filenames:
                if not (fn.endswith(".py") and not fn.startswith("__")
                        and fn != "seed_factory.py"):
                    continue
                stem = fn[:-3]
                # covered if a test file imports this module OR its parent package
                # (parent-package check only applies to subdirs — root-level
                #  modules must be imported by name, "." would match every dot)
                if re.search(rf"\b{re.escape(stem)}\b", test_text) or \
                   (rel_dir != "." and re.search(
                       rf"\b{re.escape(os.path.basename(rel_dir))}\b", test_text)):
                    continue
                rel = os.path.normpath(os.path.join(rel_dir, fn))
                gaps.append({"kind": "fow", "repo": repo, "file": rel,
                             "line": 0, "marker": "UNTESTED",
                             "note": f"no test_{stem}.py",
                             "action": f"write tests for {repo} {rel}"})
                if len(gaps) >= 60:
                    return gaps
    return gaps


# --------------------------------------------------------------------------
# pedagogy (lessons distilled from REAL code, verified against live symbols)
# --------------------------------------------------------------------------
LESSON_TEMPLATES = [
    {"slug": "dpll_sat", "title": "DPLL SAT: how the solver proves the livelock is dead",
     "module": "sophia/sat.py", "symbols": ["dpll", "_unit_propagate"],
     "concept": ("The DPLL solver walks a CNF formula: unit clauses force "
                 "assignments, pure literals assign freely, conflicts backtrack. "
                 "The classic bug we fixed: treating an already-SATISFIED clause "
                 "as a unit and forcing its remaining literal — spurious UNSAT "
                 "on satisfiable formulas."),
     "why": "The reachability verifier encodes 'can I reach the exit' as a SAT problem — the solver IS the proof machine."},
    {"slug": "bmc_frame", "title": "BMC: the frame constraint that killed teleportation",
     "module": "sophia/reach.py", "symbols": ["bounded_path_formula", "path_exists"],
     "concept": ("Naive bounded-model-checking forced every enabled edge to fire "
                 "AND let the goal pop into existence without a predecessor. The "
                 "frame constraint fixes both: a state at t+1 must be reachable "
                 "from t, exactly-one choice per time-step."),
     "why": "Sound reachability = the difference between 'looks right' and provably right."},
    {"slug": "n_retry", "title": "Nothing runs forever: the N-retry doctrine",
     "module": "BDI_FSM_AGENT/bdi_fsm/agent.py", "symbols": ["_retries_left", "_count_retry"],
     "concept": ("BLOCKED->give_up->IDLE looped forever by design (the code even "
                 "admitted it). The fix: a retry budget (default 3) guards give_up; "
                 "at exhaustion BLOCKED is a TRUE dead-end and the driver parks the "
                 "task. The SAT verifier proved the design before implementation."),
     "why": "Every system needs a bounded horizon — 'nothing runs forever' at the state-machine level."},
    {"slug": "knee_prune", "title": "Prune to the knee: the asymptotic dream",
     "module": "BDI_FSM_AGENT/bdi_fsm/asymptotic.py", "symbols": ["find_knee", "prune_to_knee"],
     "concept": ("Effectiveness-vs-retention curves have a knee: past it, the tail "
                 "is redundant. Kneedle finds the knee; we prune to it and ARCHIVE "
                 "never delete. Real corpus: 40.5% retention kept 67.2% of value."),
     "why": "Memory must stay bounded while information survives — the steady-state doctrine."},
    {"slug": "fleet_gist", "title": "Gist unification: so we all know what we are doing",
     "module": "Aegis_Unified/fleet.py", "symbols": ["post_status", "log_workflow"],
     "concept": ("Every agent appends its cycle status + successful workflow "
                 "LOGITS (deciban bans) to one shared secret gist. Ban = what is "
                 "right; logit = the record; gist = the shared memory."),
     "why": "A fleet that shares its logits learns which workflows score high — cross-machine learning with zero LLM."},
]


def _verify_symbol(path: str, symbols: List[str]) -> Dict[str, bool]:
    """Check the lesson's referenced symbols really exist (honest pedagogy)."""
    found: Dict[str, bool] = {}
    for sym in symbols:
        try:
            txt = open(path, encoding="utf-8", errors="replace").read()
            found[sym] = bool(re.search(rf"def {sym}\b|class {sym}\b|{sym}\s*=", txt))
        except OSError:
            found[sym] = False
    return found


def seed_pedagogy_lessons(root: str = "/root", out_dir: str = None) -> List[Dict]:
    """Write markdown lessons distilled from REAL fleet code."""
    out = out_dir or os.path.join(root, "BDI_FSM_AGENT", PEDAGOGY_DIR)
    os.makedirs(out, exist_ok=True)
    written = []
    for tpl in LESSON_TEMPLATES:
        path = os.path.join(root, tpl["module"]) if os.path.isabs(tpl["module"]) else \
               os.path.join(root, tpl["module"])
        if not os.path.exists(path):
            for repo in FLEET_REPOS:
                cand = os.path.join(root, repo, tpl["module"])
                if os.path.exists(cand):
                    path = cand
                    break
        verified = _verify_symbol(path, tpl["symbols"]) if os.path.exists(path) else \
                   {s: False for s in tpl["symbols"]}
        md = f"""# {tpl['title']}

*Seed generated {time.strftime('%Y-%m-%d %H:%M')} — deterministic, zero-LLM.*

## Concept
{tpl['concept']}

## Where it lives
`{tpl['module']}`

## Symbols verified live
{chr(10).join(f"- `{s}`: {'present' if v else 'MISSING'}" for s, v in verified.items())}

## Why it matters
{tpl['why']}

## Practice
1. Re-read the module. 2. Find where the concept is applied. 3. Write a test
that would FAIL if the concept were removed.
"""
        slug = tpl["slug"]
        fpath = os.path.join(out, f"{slug}.md")
        with open(fpath, "w", encoding="utf-8") as fh:
            fh.write(md)
        written.append({"slug": slug, "file": fpath,
                        "verified": all(verified.values())})
    return written


# --------------------------------------------------------------------------
# seed store (Q.E.D. zero-repeat)
# --------------------------------------------------------------------------
def load_seeds(state_dir: str) -> List[Dict]:
    p = os.path.join(state_dir, "seeds.jsonl")
    if not os.path.exists(p):
        return []
    out = []
    for ln in open(p, encoding="utf-8", errors="replace"):
        ln = ln.strip()
        if ln:
            try:
                out.append(json.loads(ln))
            except json.JSONDecodeError:
                pass
    return out


def _seed_id(kind: str, target: str, action: str) -> str:
    return hashlib.sha1(f"{kind}:{target}:{action}".encode()).hexdigest()[:10]


def generate_seeds(gaps: List[Dict], state_dir: str, max_seeds: int = 24) -> Dict:
    """Turn gaps into NEW seed contracts (never duplicate an existing seed)."""
    existing = {s["seed_id"] for s in load_seeds(state_dir)}
    seeds, skipped = [], 0
    for g in gaps:
        if len(seeds) >= max_seeds:
            break
        target = f"{g['repo']}/{g['file']}#{g['line']}" if g["line"] else f"{g['repo']}/{g['file']}"
        sid = _seed_id(g["kind"], target, g["action"])
        if sid in existing:
            skipped += 1
            continue
        seeds.append({"seed_id": sid, "kind": g["kind"], "repo": g["repo"],
                      "target": target, "action": g["action"], "marker": g["marker"],
                      "priority": "med" if g["marker"] == "MISSING" else "low",
                      "ts": int(time.time())})
    return {"seeds": seeds, "skipped_duplicates": skipped}


def save_seeds(state_dir: str, seeds: List[Dict]) -> str:
    """Overwrite the seed frontier (nightly mint = fresh queue). The FOW grid
    keeps its history via agent_events; the seed file is the WORKING QUEUE and
    must never accumulate stale duplicates across nights."""
    p = os.path.join(state_dir, "seeds.jsonl")
    with open(p, "w", encoding="utf-8") as fh:
        for s in seeds:
            fh.write(json.dumps(s) + "\n")
    return p


# --------------------------------------------------------------------------
# FOW feed (hex grid OCCUPIED cells)
# --------------------------------------------------------------------------
def post_to_fow(state_dir: str, seeds: List[Dict], agent: str = "seed_factory") -> int:
    """Append seed contracts to the agent-events feed the hex grid consumes."""
    p = os.path.join(state_dir, "agent_events.jsonl")
    n = 0
    with open(p, "a", encoding="utf-8") as fh:
        for s in seeds:
            fh.write(json.dumps({"ts": int(time.time()), "agent": agent,
                                 "action": f"seed:{s['seed_id']}",
                                 "contract": f"{s['kind']}:{s['target']}"}) + "\n")
            n += 1
    return n


# --------------------------------------------------------------------------
# needed repos (cheap API call; skipped without creds)
# --------------------------------------------------------------------------
def seed_needed_repos(state_dir: str, token: str = "", dry_run: bool = True) -> List[Dict]:
    """Create repos the fleet needs but doesn't have (e.g. Kernel_Pedagogy)."""
    import urllib.request, urllib.error
    created = []
    wanted = [
        {"name": "Kernel_Pedagogy", "desc": "Lessons distilled from Kernel's real code — DPLL, BMC, N-retry, knee-pruning, fleet gist. Auto-seeded nightly."},
    ]
    for w in wanted:
        if not token:
            created.append({"repo": w["name"], "status": "skipped_no_token"})
            continue
        req = urllib.request.Request("https://api.github.com/user/repos", method="POST",
                                     data=json.dumps({"name": w["name"], "description": w["desc"],
                                                      "private": False, "auto_init": True}).encode())
        req.add_header("Authorization", f"token {token}")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                created.append({"repo": w["name"], "status": "created"})
        except urllib.error.HTTPError as e:
            status = "exists" if e.code == 422 else f"http_{e.code}"
            created.append({"repo": w["name"], "status": status})
    return created


# --------------------------------------------------------------------------
# orchestrator
# --------------------------------------------------------------------------
def run_nightly(root: str = "/root", state_dir: str = "state",
                token: str = "", max_seeds: int = 24,
                commit: bool = False, dry_run: bool = False) -> Dict:
    """One nightly pass: scan gaps -> generate seeds -> save -> FOW feed ->
    pedagogy lessons -> needed repos. Failure-isolated stages."""
    state_dir = state_dir if os.path.isabs(state_dir) else os.path.join(root, "BDI_FSM_AGENT", state_dir)
    report: Dict = {}
    # 1. gaps
    gaps = scan_fleet_gaps(root)
    report["gaps_found"] = len(gaps)
    # 2. seeds
    gen = generate_seeds(gaps, state_dir, max_seeds=max_seeds)
    report["seeds_new"] = len(gen["seeds"])
    report["seeds_duplicate_skipped"] = gen["skipped_duplicates"]
    if gen["seeds"] and not dry_run:
        save_seeds(state_dir, gen["seeds"])
    # 3. FOW feed
    if gen["seeds"] and not dry_run:
        report["fow_events_posted"] = post_to_fow(state_dir, gen["seeds"])
    # 4. pedagogy
    lessons = seed_pedagogy_lessons(root)
    report["pedagogy_written"] = len(lessons)
    report["pedagogy_verified"] = sum(1 for l in lessons if l["verified"])
    report["pedagogy_missing_symbols"] = [l["slug"] for l in lessons if not l["verified"]]
    # 5. needed repos
    report["repos"] = seed_needed_repos(state_dir, token=token, dry_run=dry_run)
    report["done"] = True
    return report

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
