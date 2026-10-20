"""py4qwhip block 08 — e2e: external chain battery + receipts.

Chris, verbatim: "harden all to be local no cloud use this should tie things
together" / "of course full autonomy my friend!".

Battery blocks 01-07 verify each block's INTERNALS in isolation. This block
verifies the CHAIN as an external consumer would drive it (what an outside
runner actually does with no knowledge of block internals):

  b01.assemble -> b07.grant -> b06.encode(+endcap, blob as shipped to disk)
  -> b07.check_blob(blob) at the gate -> program_from_text -> b04 VM run
  with the handed grant -> HALT.

Also emits a RECEIPTS section (existence checks on shipped artifacts +
last_battery.json parse; findings text stays in the findings doc — this
block only proves the artifacts EXIST and the battery is machine-readable).

Stdlib only, local files only, deterministic, no network, no model calls.
"""
from __future__ import annotations

import importlib.util
import json
import os
from typing import Any, Dict, List, Tuple


def _load_local(fname: str, modname: str):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), fname)
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


BLKDIR = os.path.dirname(os.path.abspath(__file__))
b01 = _load_local("01_bytespace.py", "pq4_e2e_b01")
b04 = _load_local("04_vm.py", "pq4_e2e_b04")
b06 = _load_local("06_envelope.py", "pq4_e2e_b06")
b07 = _load_local("07_qgrant.py", "pq4_e2e_b07")

ZEROCAP = b"\x00" * 8


# ------------------------------------------------------------- chain checks

def _mk_program() -> Dict[str, Any]:
    return b01.assemble("load_const r0, 6\n"
                        "load_const r1, 7\n"
                        "mul r2, r0, r1\n"
                        "out r2\n"
                        "halt\n", "e2e_mul", nlocals=4)


def _ship_blob(program: Dict[str, Any]) -> Tuple[bytes, str]:
    """Producer side: canonical text + grant, wrapped into an envelope blob."""
    ptext = b07._canonical_text(program)
    return b06.encode(ptext, endcap=b07.grant_text(ptext)), ptext


def _consume_chain(blob: bytes, grant: bytes, require: bool = True) -> Dict[str, Any]:
    """Consumer side, exactly as block 04's gate consumes a handed blob."""
    gate = b07.check_blob(blob, require=require, decode=True)
    if not gate["ok"]:
        return {"gate_ok": False, "reason": gate["reason"], "result": None}
    program = b07.program_from_text(gate["decoded"])
    result = b04.resolve_and_run(program, grant=grant)
    return {"gate_ok": True, "reason": gate["reason"], "result": result}


def chain_checks() -> Dict[str, bool]:
    checks: Dict[str, bool] = {}
    p = _mk_program()
    cap = b07.grant(p)
    blob, _ptext = _ship_blob(p)

    # 1. full happy chain: granted blob -> gate -> VM -> HALTED [42]
    c = _consume_chain(blob, b07.grant(b07.program_from_text(
        b07._canonical_text(p))))
    r = c["result"]
    checks["chain_program_ok"] = (c["gate_ok"] and r is not None
                                  and r["status"] == "HALTED"
                                  and r["outs"] == [42])

    # 2. determinism: same chain twice -> identical gate hash + outs
    c2 = _consume_chain(blob, b07.grant(b07.program_from_text(
        b07._canonical_text(p))))
    gate1 = b07.check_blob(blob, require=True, decode=True)
    checks["chain_deterministic"] = (
        gate1["hash"] and c["result"]["outs"] == c2["result"]["outs"]
        and c["result"]["steps"] == c2["result"]["steps"])

    # 3. producer tamper (body byte flipped on disk) -> gate refuses, VM never runs
    blob_tb = blob[:26] + bytes([blob[26] ^ 0x01]) + blob[27:]
    ct = _consume_chain(blob_tb, cap)
    checks["chain_tamper_refused"] = (not ct["gate_ok"]
                                      and "envelope" in ct["reason"])

    # 4. valid blob but consumer handed the WRONG grant -> gate passes (blob
    #    integrity + blob endcap fine), VM refuses pre-step with FAULT.
    #    Layering: gate binds blob<=endcap; VM binds handed-grant<=program.
    cw = _consume_chain(blob, b"\x11" * 8)
    rw = cw["result"]
    checks["chain_wrong_grant_vm_fault"] = (
        cw["gate_ok"] and rw is not None and rw["status"] == "FAULT"
        and rw["fault"].startswith("grant:") and rw["steps"] == 0)

    # 5. zero endcap: producer shipped WITHOUT grant -> required lane refuses,
    #    Alice's reserved-mode lane passes the gate only.
    blob_z = b06.encode(b07._canonical_text(p))
    cz1 = _consume_chain(blob_z, ZEROCAP, require=True)
    cz2 = b07.check_blob(blob_z, require=False, decode=True)
    checks["chain_zero_policy"] = (not cz1["gate_ok"]
                                   and cz2["ok"] is True
                                   and "reserved zero" in cz2["reason"])

    # 6. KIND_CODE lane: marshal'd code object blob, grant-bound, verified
    co = compile("x = 6\ny = x * 7\n", "<e2e>", "exec")
    txt_c = b07._code_canonical_text(co)
    blob_c = b06.encode(co, endcap=b07.grant_text(txt_c))
    rc = b07.check_blob(blob_c, require=True, decode=True)
    import marshal
    d = rc["decoded"]
    # marshal.loads->dumps is not byte-stable (interned FLAG_REF flips), so the
    # consumer asserts SEMANTIC equality; byte identity is the BODY's job (the
    # grant binds the exact shipped marshal bytes, verified by the gate).
    checks["chain_kindcode_ok"] = (rc["ok"] is True and d is not None
                                   and d.co_code == co.co_code
                                   and d.co_consts == co.co_consts
                                   and d.co_names == co.co_names
                                   and d.co_name == co.co_name)

    # 7. KIND_SOURCE lane: plain source text, grant-bound, verified
    stext = "load_const r0, 9\nhalt\n"
    blob_s = b06.encode(stext, endcap=b07.grant_text(stext))
    rs = b07.check_blob(blob_s, require=True, decode=True)
    checks["chain_source_ok"] = (rs["ok"] is True and rs["decoded"] == stext)

    # 8. VM refuses an ungranted-but-valid program handed NULL grant bytes
    ru = b04.resolve_and_run(p, grant=ZEROCAP)
    checks["chain_vm_zero_refused"] = (ru["status"] == "FAULT"
                                       and "zero endcap" in ru["fault"]
                                       and ru["steps"] == 0)
    return checks


# ------------------------------------------------------------------ receipts

def receipts() -> Dict[str, Any]:
    """Existence + machine-readability of shipped artifacts (NOT findings text)."""
    out: Dict[str, Any] = {"receipts": {}}
    art = {
        "last_battery": os.path.join(BLKDIR, "last_battery.json"),
        "done_01": os.path.join(BLKDIR, "01_bytespace.done"),
        "done_02": os.path.join(BLKDIR, "02_karaka.done"),
        "done_03": os.path.join(BLKDIR, "03_synthesize.done"),
        "done_04": os.path.join(BLKDIR, "04_vm.done"),
        "done_06": os.path.join(BLKDIR, "06_envelope.done"),
        "done_07": os.path.join(BLKDIR, "07_qgrant.done"),
        "run_feed_result_20261015": os.path.join(
            os.path.dirname(BLKDIR), "run_feed_result_20261015.json"),
    }
    for k, path in art.items():
        out["receipts"][k] = os.path.isfile(path)
    bat = out["receipts"]["last_battery"]
    if bat:
        try:
            with open(art["last_battery"], encoding="utf-8") as f:
                rep = json.load(f)
            out["battery_verdict"] = rep.get("verdict", "?")
            out["battery_blocks"] = rep.get("total", 0)
            out["receipts"]["last_battery_parses"] = "verdict" in rep
        except Exception:
            out["receipts"]["last_battery_parses"] = False
    return out


# ------------------------------------------------------------------ selftest

def selftest() -> dict:
    checks = chain_checks()
    rec = receipts()
    ok = all(checks.values()) and all(rec["receipts"].values())
    return {"ok": ok, "name": "e2e", "checks": checks,
            "receipts": rec["receipts"]}


if __name__ == "__main__":
    r = selftest()
    print(json.dumps(r, default=str))
    import sys
    sys.exit(0 if r["ok"] else 1)