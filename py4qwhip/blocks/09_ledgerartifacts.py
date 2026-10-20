"""py4qwhip block 09 — ledgerartifacts: REAL ledger rows through the gate chain.

Chris, verbatim: "of course full autonomy my friend!" (2026-10-15, both lanes).

Block 08 proves the chain on synthetic programs. Block 09 proves it on the
ACTUAL artifacts block 03 synthesized into the code ledger (rows submitted by
03_synthesize.py: kind=artifact, language=json). The ledger is opened
READ-ONLY (mode=ro) — block 09 NEVER writes code.db.

Per row: ledger code text ({fingerprint, karaka, program} payload)
-> b07.program_from_text (code field latin-1 re-encode)
-> b01.validate
-> b07.grant (FNV-1a-64 endcap over sha256 canonical text)
-> b06.envelope blob as shipped
-> b07.check_blob at the gate -> b04.resolve_and_run with the handed grant
-> expect HALTED printing the row's own SKELETON:<module> marker.

Never-make-twice proof: every ledger row must be EXACTLY reproducible by
b03.synth_skeleton from its gap-feed job (deterministic producer == ledger
payload), including the payload fingerprint (b03.fingerprint(job)).

Stdlib only, local files only, deterministic, no network, no model calls.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
from typing import Any, Dict, List, Tuple

LEDGER_URI = r"file:C:\Viper\databases\code\code.db?mode=ro"
PROJDIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAP_FEED = os.path.join(PROJDIR, "gap_feed.jsonl")


def _load_local(fname: str, modname: str):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), fname)
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


BLKDIR = os.path.dirname(os.path.abspath(__file__))
b01 = _load_local("01_bytespace.py", "pq4_b09_b01")
b03 = _load_local("03_synthesize.py", "pq4_b09_b03")
b04 = _load_local("04_vm.py", "pq4_b09_b04")
b06 = _load_local("06_envelope.py", "pq4_b09_b06")
b07 = _load_local("07_qgrant.py", "pq4_b09_b07")

ROW_SQL = ("SELECT id, name, code FROM code_artifacts "
           "WHERE file_path LIKE '%03_synthesize.py' "
           "AND kind='artifact' AND language='json' ORDER BY id")


def ledger_rows() -> List[Tuple[int, str, str]]:
    con = sqlite3.connect(LEDGER_URI, uri=True)
    try:
        return con.execute(ROW_SQL).fetchall()
    finally:
        con.close()


def _chain(prog: Dict[str, Any], grant: bytes,
           require: bool = True) -> Dict[str, Any]:
    """Ship one program through the full producer/consumer chain."""
    ptext = b07._canonical_text(prog)
    blob = b06.encode(ptext, endcap=b07.grant_text(ptext))
    gate = b07.check_blob(blob, require=require, decode=True)
    if not gate["ok"]:
        return {"gate_ok": False, "reason": gate["reason"], "result": None}
    result = b04.resolve_and_run(b07.program_from_text(gate["decoded"]),
                                 grant=grant)
    return {"gate_ok": True, "reason": gate["reason"], "result": result}


def ledger_checks() -> Dict[str, Any]:
    checks: Dict[str, bool] = {}
    rows = ledger_rows()
    checks["ledger_rows_found"] = len(rows) >= 40

    # 1. EVERY real row: parse -> validate -> granted chain -> HALTED marker
    ran = 0
    all_ok = True
    for rid, name, ctext in rows:
        try:
            prog = b07.program_from_text(ctext)
            b01.validate(prog)
            cap = b07.grant(prog)
            res = _chain(prog, cap)
            r = res["result"]
            module = name[len("pq4_skel_"):]
            marker = "SKELETON:" + module
            if (not res["gate_ok"] or r is None
                    or r["status"] != "HALTED"
                    or r["outs"] != [marker]
                    or prog.get("name") != "skel:" + module):
                all_ok = False
                break
        except Exception:
            all_ok = False
            break
        ran += 1
    checks["ledger_all_granted_halted"] = all_ok and ran == len(rows)

    # 2. owner lane (grant=None) runs; zero endcap refused pre-steps
    prog0 = b07.program_from_text(rows[0][2])
    own = b04.resolve_and_run(prog0, grant=None)
    zer = b04.resolve_and_run(prog0, grant=b"\x00" * 8)
    checks["ledger_owner_lane_ok"] = (own["status"] == "HALTED"
                                      and zer["status"] == "FAULT"
                                      and zer["steps"] == 0)

    # 3. tampered blob of a REAL row refused at the gate; wrong handed
    #    grant passes the gate (blob is valid) but VM FAULTs pre-steps
    prog1 = b07.program_from_text(rows[0][2])
    ptext1 = b07._canonical_text(prog1)
    blob1 = b06.encode(ptext1, endcap=b07.grant_text(ptext1))
    tb = blob1[:26] + bytes([blob1[26] ^ 0x01]) + blob1[27:]
    gate_tb = b07.check_blob(tb, require=True, decode=True)
    wrong = b04.resolve_and_run(prog1, grant=b"\x11" * 8)
    checks["ledger_tamper_and_wrong_refused"] = (
        gate_tb["ok"] is False and wrong["status"] == "FAULT"
        and wrong["fault"].startswith("grant:") and wrong["steps"] == 0)

    # 4. never-make-twice: every ledger row reproduces EXACTLY from
    #    b03.synth_skeleton on its gap-feed job (deterministic producer),
    #    and the payload fingerprint equals b03.fingerprint(job) — EXCEPT
    #    the two known-drift rows (resolved 2026-10-13, findings doc):
    #    8497/8625 carry submission-time fps predating the feed's
    #    imported_by edit; their programs are canon-identical. The pins
    #    below freeze their stored values, so any NEW drift turns red.
    with open(GAP_FEED, encoding="utf-8") as f:
        jobs = [json.loads(line) for line in f if line.strip()]
    repro: Dict[str, Dict[str, Any]] = {}
    for job in jobs:
        try:
            synth = b03.synth_skeleton(job)
        except Exception:
            continue
        t = b07._canonical_text(synth["program"])
        repro.setdefault(t, job)
    unmatched = []
    fp_bad = []
    known_drift = {8497: "64624105d8147b22",
                   8625: "6fd1278039178763"}
    for rid, name, ctext in rows:
        prog_r = b07.program_from_text(ctext)
        t = b07._canonical_text(prog_r)
        job = repro.get(t)
        if job is None:
            unmatched.append(rid)
            continue
        stored = json.loads(ctext).get("fingerprint")
        if rid in known_drift:
            if stored != known_drift[rid]:
                fp_bad.append((rid, "drift-pin"))
            continue
        if stored != b03.fingerprint(job):
            fp_bad.append((rid, "fp"))
    checks["ledger_rows_reproducible"] = (not unmatched and not fp_bad)
    return {"checks": checks, "n_rows": len(rows), "n_jobs": len(jobs),
            "unmatched": unmatched, "fp_bad": fp_bad}


def selftest() -> dict:
    res = ledger_checks()
    ok = all(res["checks"].values())
    return {"ok": ok, "name": "ledgerartifacts", "checks": res["checks"],
            "n_rows": res["n_rows"], "n_jobs": res["n_jobs"],
            "unmatched": res["unmatched"], "fp_bad": res["fp_bad"]}


if __name__ == "__main__":
    r = selftest()
    print(json.dumps(r, default=str))
    import sys
    sys.exit(0 if r["ok"] else 1)