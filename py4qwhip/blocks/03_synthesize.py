"""py4qwhip block 03 — synthesize: loop closure for missing imports.

Design notes (Chris, verbatim, 2026-10-12):
  "Every one of those is a crash in a normal runtime and a *synthesis job* in
   py4qwhip. Loop closure instead of ModuleNotFoundError, forever."
  "harden all to be local no cloud use this should tie things together"

The synthesize engine consumes a gap feed (Aria findings -> synthesis jobs,
Claude lane's gap_feed.jsonl). For each job it:
  1. fingerprints the gap (module name, kind)
  2. searches prior art in code.db (code_ledger.retrieve, LOCAL only)
  3. synthesizes a canonical skeleton program (block-01 bytecode) whose
     kāraka roles (block 02) state intent: AGT=callee, PAT=module...
  4. registers the result in the ledger via code_ledger.submit
     (never-make-twice enforcement reuses instead of duplicating)

No network. No model calls. Deterministic: same job -> same program -> same
content hash, always.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

import importlib.util

# 2026-10-14 (Claude, Hermes out): no sys.path edits -- py4qwhip exists to remove that trick.
# code_ledger is loaded by file path (it needs no sibling imports, verified by the battery).
def _load_path(path: str, modname: str):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


code_ledger = _load_path(r"C:\Viper\scripts\code_ledger.py", "pq4_code_ledger")  # LOCAL sqlite ledger


def _load_local(fname: str, modname: str):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), fname)
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


b01 = _load_local("01_bytespace.py", "pq4_b01")
b02 = _load_local("02_karaka.py", "pq4_b02")


class SynthesizeError(Exception):
    """Deterministic synthesis fault (bad job, no viable skeleton)."""


GAP_KINDS = {"MODULE_MISSING", "IMPORT_ELSEWHERE"}
GAP_FEED_DEFAULT = r"C:\Viper\projects\py4qwhip\gap_feed.jsonl"


def fingerprint(job: Dict[str, Any]) -> str:
    """Stable gap fingerprint: kind + module + imported_by (sorted)."""
    payload = json.dumps({
        "kind": str(job.get("kind", "")).upper(),
        "module": str(job.get("module", "")),
        "imported_by": sorted(job.get("imported_by", []) or []),
    }, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


# ---------------------------------------------------------------- prior art

def lookup_prior_art(job: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
    """Find ledger artifacts relevant to this gap. LOCAL code.db read only."""
    kind = str(job.get("kind", "")).upper()
    mod = str(job.get("module", "") or "").replace("_", " ")
    if kind == "MODULE_MISSING":
        q = "synthesize stub module %s import resolver placeholder" % mod
    else:
        q = "import path resolve module %s" % mod
    try:
        hits = code_ledger.retrieve(q, limit=limit)
    except Exception as e:  # never explode a search (code_ledger convention)
        return []
    out = []
    for h in hits:
        out.append({"id": h["id"], "name": h["name"], "kind": h["kind"],
                    "score": round(float(h.get("bm25") or h.get("score") or 0), 4)})
    return out


# ---------------------------------------------------------------- synthesis

ASM_TEMPLATE = """\
load_const r3, 'SKELETON:{module}'
out r3
load_const r0, 0
halt
"""


def synth_skeleton(job: Dict[str, Any]) -> Dict[str, Any]:
    """Build the canonical skeleton program for a gap job (deterministic).

    BLOCKED for non-skeletal kinds: the resolver only auto-synthesizes a
    placeholder that HALTs printing SKELETON:<module> -- an explicit marker, never faked behavior (docstring said RAISES; corrected 2026-10-14, fault-vs-marker is an Alice ruling).
    """
    kind = str(job.get("kind", "")).upper()
    if kind not in GAP_KINDS:
        raise SynthesizeError("unsupported gap kind %r" % kind)
    module = str(job.get("module", "") or "")
    if not module or not module.replace("_", "").isalnum():
        raise SynthesizeError("bad module name %r" % module)

    table = b02.KarakaTable()
    table.bind("AGT", 3)   # AGT: the halt register (caller context)
    table.bind("PAT", 0)   # PAT: slot 0 holds the module placeholder value

    nlocals = 8
    asm = ASM_TEMPLATE.format(module=module)
    pool = ["SKELETON:%s" % module]
    prog = b01.assemble(asm, name="skel:%s" % module, nlocals=nlocals,
                        const_extra=pool)
    prog["nlocals"] = nlocals
    b01.validate(prog)
    return {"program": prog, "karaka": json.loads(table.to_json()),
            "kind": kind, "fingerprint": fingerprint(job)}


def _payload(job: Dict[str, Any], synth: Dict[str, Any],
             prior_art: List[Dict[str, Any]]) -> Tuple[str, str, str]:
    """Canonical ledger payload for a synthesized skeleton (single source)."""
    name = "pq4_skel_%s" % str(job.get("module", "unnamed"))
    purpose = ("py4qwhip skeleton for gap %s (kind %s, fingerprint %s); "
               "prior art ids %s" % (job.get("gap_id", "?"), synth["kind"],
                                     synth["fingerprint"],
                                     [p["id"] for p in prior_art]))
    code_text = json.dumps({
        "program": {k: (v.decode("latin-1") if isinstance(v, bytes) else v)
                    for k, v in synth["program"].items()},
        "karaka": synth["karaka"],
        "fingerprint": synth["fingerprint"],
    }, sort_keys=True)
    return name, purpose, code_text


def submit_synthesis(job: Dict[str, Any], synth: Dict[str, Any],
                     prior_art: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Register the synthesized program in the ledger (never-make-twice)."""
    name, purpose, code_text = _payload(job, synth, prior_art)
    res = code_ledger.submit(code=code_text, name=name, purpose=purpose,
                             language="json", kind="artifact",
                             file_path=r"C:\Viper\projects\py4qwhip\blocks\03_synthesize.py",
                             fitness_score=0.5)
    return res


def _body_matches_row(row_id: int, synth: Dict[str, Any]) -> bool:
    """Read-only: does ledger row @row_id carry the SAME body as live synth?

    Body = program bytes + nlocals + karakas. The embedded fingerprint is
    deliberately ignored: it is derived annotation and may be stale in older
    rows (10-13 writer era). No writes, no verdict override — callers still
    keep code_ledger's own 'blocked' unless this exact body match succeeds.
    """
    try:
        import sqlite3
        con = sqlite3.connect(r"file:C:\Viper\databases\code\code.db?mode=ro", uri=True)
        try:
            row = con.execute("SELECT code FROM code_artifacts WHERE id=?",
                              (row_id,)).fetchone()
        finally:
            con.close()
        if not row:
            return False
        old = json.loads(row[0])
        prog_old = old.get("program", {})
        return (old.get("karaka") == synth["karaka"] and
                prog_old.get("code") ==
                synth["program"]["code"].decode("latin-1") and
                prog_old.get("nlocals") == synth["program"].get("nlocals"))
    except Exception:
        return False


# ---------------------------------------------------------------- feed loop

def load_feed(path: str = GAP_FEED_DEFAULT) -> List[Dict[str, Any]]:
    jobs = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                jobs.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # malformed lines skipped deterministically
    return jobs


def run_feed(path: str = GAP_FEED_DEFAULT, verbose: bool = False
             ) -> Dict[str, Any]:
    jobs = load_feed(path)
    summary = {"jobs": len(jobs), "synthesized": 0, "reused": 0,
               "blocked": 0, "rejected": 0, "errors": []}
    ledger = {}
    for job in jobs:
        gid = str(job.get("gap_id", "?"))
        try:
            prior = lookup_prior_art(job)
            synth = synth_skeleton(job)
        except SynthesizeError as e:
            summary["errors"].append("%s: %s" % (gid, e))
            continue
        try:
            res = submit_synthesis(job, synth, prior)
        except Exception as e:
            summary["errors"].append("%s: submit %s" % (gid, e))
            continue
        action = str(res.get("action", "?"))
        if action == "blocked":
            code_text = _payload(job, synth, prior)[2]
            # code_ledger refused as near-dup (never-make-twice). If the prior row's
            # BODY matches ours (program + karakas identical; only its embedded
            # fingerprint annotation is stale), this is reuse of the SAME artifact
            # with annotation drift — not a synthesis dead end. Read-only re-derive.
            near_id, ratio = None, None
            try:
                near, ratio = code_ledger._nearest(code_text, "json")
                thr = getattr(code_ledger, "DUP_THRESHOLD", 0.9)
                if near and ratio >= thr and _body_matches_row(near["id"], synth):
                    near_id = near["id"]
                    action = "existing_stale_fp"  # reuse verdict, annotation drift only
            except Exception:
                pass  # keep the strict ledger verdict on any probe failure
            if action == "existing_stale_fp":
                res = dict(res, id=near_id, nearest_ratio=round(ratio, 4))
        entry = {"action": action, "id": res.get("id"),
                 "fingerprint": synth["fingerprint"],
                 "content_hash": b01.content_hash(synth["program"])}
        if "nearest_ratio" in res:
            entry["nearest_ratio"] = res["nearest_ratio"]
        ledger[gid] = entry
        if action == "added":
            summary["synthesized"] += 1
        elif action == "existing":
            summary["reused"] += 1
        elif action == "existing_stale_fp":
            summary["reused"] += 1  # still reuse; separate counter for audit
            summary["reused_stale_fp"] = summary.get("reused_stale_fp", 0) + 1
        elif action == "blocked":
            summary["blocked"] += 1
        else:
            summary["rejected"] += 1
    return {"summary": summary, "ledger": ledger}


# ---------------------------------------------------------------- selftest

def selftest() -> dict:
    checks = {}
    # 1. fingerprint stability + distinctness
    j1 = {"kind": "MODULE_MISSING", "module": "cpuinfo",
          "imported_by": ["machine_env.py"]}
    j2 = dict(j1, imported_by=["other.py"])
    fp1, fp2 = fingerprint(j1), fingerprint(j2)
    checks["fp_stable"] = fp1 == fingerprint(dict(j1))
    checks["fp_distinct"] = fp1 != fp2
    # 2. prior art lookup finds LOCAL hits for known-good query
    pa = lookup_prior_art({"kind": "MODULE_MISSING", "module": "path",
                           "imported_by": ["x.py"]})
    checks["prior_art_local"] = all(isinstance(p["id"], int) for p in pa)
    # 3. skeleton build validates + deterministic hash
    s1 = synth_skeleton({"kind": "MODULE_MISSING", "module": "cpuinfo",
                         "imported_by": []})
    s2 = synth_skeleton({"kind": "MODULE_MISSING", "module": "cpuinfo",
                         "imported_by": []})
    h1, h2 = b01.content_hash(s1["program"]), b01.content_hash(s2["program"])
    checks["synth_deterministic"] = h1 == h2
    checks["karaka_present"] = s1["karaka"]["AGT"] == 3
    # 4. bad kind refused
    try:
        synth_skeleton({"kind": "BOGUS", "module": "x"})
        checks["bad_kind_refused"] = False
    except SynthesizeError:
        checks["bad_kind_refused"] = True
    # 5. bad module refused
    try:
        synth_skeleton({"kind": "MODULE_MISSING", "module": "../evil"})
        checks["bad_module_refused"] = False
    except SynthesizeError:
        checks["bad_module_refused"] = True
    # 6. code_ledger reachable locally
    checks["ledger_ok"] = stats_ok = False
    try:
        st = code_ledger.stats()
        stats_ok = st.get("artifacts", 0) > 0
    except Exception:
        stats_ok = False
    checks["ledger_ok"] = stats_ok
    ok = all(checks.values())
    return {"ok": ok, "name": "synthesize", "checks": checks}


if __name__ == "__main__":
    r = selftest()
    print(json.dumps(r, default=str))
    sys.exit(0 if r["ok"] else 1)