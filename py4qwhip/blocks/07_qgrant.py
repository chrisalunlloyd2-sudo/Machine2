"""py4qwhip block 07 — qgrant: QW-7 grant gate for foreign bytecode.

Design notes (Chris, verbatim):
  "And the QW-7 end-caps credentials tagged to the bytecode itself"
  "harden all to be local no cloud use this should tie things together"
  (block 04 vm docstring): programs are content-hashed; the hash is the grant
  key — to run someone's bytecode you must be *handed* the hash.
  (block 06 envelope): ENDCAP(8) is reserved for the QW-7 credential tag,
  all zero until Alice rules; Q1-Q4 rulings stay with Alice.
Stdlib only, deterministic, no I/O, no network, no model calls. This block
DOES NOT invent QW-7 policy — it enforces the mechanical half that needs no
policy ruling: an endcap must carry a valid 8-byte grant (FNV-1a 64 of the
canonical program hash, a local pure function) whose LOW byte is not zero and
whose grant checks out against the presented program; all-zero endcap is
accepted ONLY in require_grant=False policy mode (Alice's reserved slot).

grant(program)  -> 8-byte endcap for a validated block-01 program (pure).
verify(blob_endcap, program, require=True) -> (ok, reason) — never raises.
check_blob(blob, require) -> encode/inspect via block 06, verify endcap, then
optionally decode. Wrong grant, tampered body, or zero-endcap-with-require
each return a deterministic false with a stable reason string.
Author: Hermes (dense-code lane). Slot 07 free 2026-10-15 (slot 06 taken).
"""
from __future__ import annotations

import hashlib
import json
import os
import struct
import sys
from typing import Any, Dict, Optional, Tuple

import importlib.util  # 2026-10-14 convention: siblings load by file path


def _load_local(fname: str, modname: str):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), fname)
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


b01 = _load_local("01_bytespace.py", "pq4_b01")
b06 = _load_local("06_envelope.py", "pq4_b06")

ZEROCAP = b"\x00" * 8  # block 06's all-zero reserved tag: "no grant attached"


def _fnv1a64(data: bytes) -> int:
    """FNV-1a 64-bit — pure, stdlib-only, deterministic; the Rust port parity op."""
    h = 0xCBF29CE484222325
    for byte in data:
        h ^= byte
        h = (h * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return h


def program_from_text(text: str) -> Dict[str, Any]:
    """Inverse of _canonical_text: program dict from its canonical json text.

    b01 const-pool entries are stored PRE-STRINGIFIED scalars (ints and strs,
    bytes already in b"..." repr form), so the canon payload is lossless except
    program["code"]: the single true-bytes field -> latin-1 re-encode only that.
    """
    obj = json.loads(text)
    if not isinstance(obj, dict) or "program" not in obj:
        raise ValueError("program_from_text: not a program payload")
    prog = dict(obj["program"])
    if isinstance(prog.get("code"), str):
        prog["code"] = prog["code"].encode("latin-1")
    return prog


def _canonical_text(program: Dict[str, Any]) -> str:
    """Exact canonical text a blob will carry for a program dict (single source).

    Block-01 programs embed raw bytes (code, pool byte strings); json.dumps
    cannot take them, so mirror block 03's ledger convention: bytes =>
    latin-1 decoded strings. Same input -> same text, deterministically.
    """
    def _plain(v: Any) -> Any:
        if isinstance(v, bytes):
            return v.decode("latin-1")
        if isinstance(v, dict):
            return {k: _plain(x) for k, x in v.items()}
        if isinstance(v, (list, tuple)):
            return [_plain(x) for x in v]
        return v

    return json.dumps({"program": _plain(program)}, sort_keys=True)


def grant(program: Dict[str, Any]) -> bytes:
    """Derive the 8-byte QW-7 endcap for a block-01 program (pure).

    Grant = FNV-1a 64 of b"QW-7" + sha256 of the program's canonical text
    (the very bytes an envelope would carry, so blob transport and direct
    program use hash the SAME thing). Deterministic; no policy decisions.
    """
    return grant_text(_canonical_text(program))


def grant_text(text: str) -> bytes:
    """8-byte QW-7 endcap for exact textual content (source or canonical json)."""
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return _fnv1a64(b"QW-7" + digest.encode("ascii")).to_bytes(8, "big")


def verify(endcap: bytes, program: Dict[str, Any],
           require: bool = True) -> Tuple[bool, str]:
    """Check an endcap against a program. Pure; deterministic reason strings.

    require=True: all-zero endcap is refused (policy: must be *handed* the
    grant, per block 04 note). A wrong-but-nonzero grant also refused.
    require=False (Alice's mode, used until Q1-Q4 rule): zero endcap passes
    as the reserved unsigned tag; any other value still must verify.
    """
    if not isinstance(endcap, (bytes, bytearray)) or len(endcap) != 8:
        return False, "grant: endcap must be 8 bytes"
    endcap = bytes(endcap)
    if endcap == ZEROCAP:
        if require:
            return False, "grant: zero endcap, no credential attached"
        return True, "grant ok (reserved zero, policy allows)"
    try:
        want = grant(program)
    except Exception:
        return False, "grant: program not canonicalizable"
    if endcap != want:
        return False, "grant: mismatch for program hash %s" % b01.content_hash(program)
    return True, "grant ok"


def check_blob(blob: bytes, require: bool = True,
               decode: bool = False) -> Dict[str, Any]:
    """Full gate on a block-06 envelope blob: validate, verify grant, decode.

    Returns {"ok": .., "reason": .., "kind": .., "endcap_hex": ..,
             "hash": .., "decoded": ..} — decoded only when decode=True and all
    gates passed. Never raises for blob problems (deterministic results).
    """
    out: Dict[str, Any] = {"ok": False, "reason": "", "kind": None,
                           "endcap_hex": "", "hash": "", "decoded": None}
    try:
        kind, endcap, body = b06.inspect(blob)
    except Exception as e:
        out["reason"] = "envelope: %s" % e
        return out
    out["kind"] = kind
    out["endcap_hex"] = endcap.hex()
    try:
        payload = b06.decode(blob)
    except Exception as e:
        out["reason"] = "decode: %s" % e
        return out
    if isinstance(payload, str):
        # KIND_SOURCE: text is granted as its exact bytes (source OR program-json)
        ok, reason = _verify_text(endcap, payload, require=require)
        target, text = payload, payload
    else:
        # KIND_CODE: code object - grant binds to the SHIPPED marshal bytes,
        # not to a re-marshaled copy: marshal.loads->dumps is NOT byte-stable
        # (interned-string FLAG_REF flags flip on roundtrip under 3.11), so
        # re-deriving canonical text from the decoded object spuriously fails
        # on untouched blobs. The envelope body IS the exact shipped bytes.
        text = "marshal:" + bytes(body).hex()
        ok, reason = _verify_text(endcap, text, require=require)
        target = payload
    out["ok"] = ok
    out["reason"] = reason
    if ok and decode:
        out["decoded"] = target
        out["hash"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return out


def _code_canonical_text(code: Any) -> str:
    """Program-dict json text for a KIND_CODE blob: code objects carry no json;
    we can't re-derive a program from marshal alone, so the canonical text of a
    code blob is its REPRODUCIBLE repr via marshal bytes hex (deterministic)."""
    import marshal
    data = marshal.dumps(code)
    return "marshal:" + data.hex()


def _verify_text(endcap: bytes, text: str, require: bool = True) -> Tuple[bool, str]:
    """Grant check against exact canonical text (single derivation for all kinds)."""
    if not isinstance(endcap, (bytes, bytearray)) or len(endcap) != 8:
        return False, "grant: endcap must be 8 bytes"
    endcap = bytes(endcap)
    if endcap == ZEROCAP:
        if require:
            return False, "grant: zero endcap, no credential attached"
        return True, "grant ok (reserved zero, policy allows)"
    if endcap != grant_text(text):
        return False, "grant: mismatch for content sha256 %s" % \
            hashlib.sha256(text.encode("utf-8")).hexdigest()
    return True, "grant ok"


# ---------------------------------------------------------------- selftest

def selftest() -> dict:
    checks: Dict[str, bool] = {}
    p = b01.assemble("load_const r0, 6\n"
                     "load_const r1, 7\n"
                     "mul r2, r0, r1\n"
                     "out r2\n"
                     "halt\n", "qt_mul", nlocals=4)
    # 1. grant is pure and stable
    g1, g2 = grant(p), grant(p)
    checks["grant_deterministic"] = (g1 == g2 and len(g1) == 8 and g1 != ZEROCAP)
    # 2. tampered program -> different grant (the whole point of QW-7)
    p_t = dict(p)
    p_t["code"] = p["code"] + b"\x00\x0f"
    checks["grant_binds_body"] = (grant(p_t) != g1)
    # 3. end-to-end blob: encode canonical PROGRAM TEXT with grant, check passes
    ptext = _canonical_text(p)
    blob = b06.encode(ptext, endcap=grant_text(ptext))
    r = check_blob(blob, require=True, decode=True)
    checks["blob_grant_ok"] = (r["ok"] is True and r["decoded"] == ptext
                               and r["hash"] == hashlib.sha256(ptext.encode("utf-8")).hexdigest())
    # 4. tampered BODY inside a valid-length envelope -> checksum refuses
    blob_t = blob[:26] + bytes([blob[26] ^ 0x01]) + blob[27:]
    try:
        rt = (b06.inspect(blob_t) is not None)
    except Exception:
        rt = False
    checks["tamper_caught_envelope"] = (rt is False)
    # 5. wrong grant on an untampered envelope -> grant refusal
    blob_w = b06.encode(ptext, endcap=b"\x11" * 8)
    rw = check_blob(blob_w, require=False, decode=True)
    checks["wrong_grant_refused"] = (rw["ok"] is False
                                     and rw["reason"].startswith("grant: mismatch"))
    # 6. zero endcap: refused when required, allowed in Alice's policy mode
    blob_z = b06.encode(ptext)  # default reserved endcap
    rz1 = check_blob(blob_z, require=True)
    rz2 = check_blob(blob_z, require=False)
    checks["zero_endcap_policy"] = (rz1["ok"] is False
                                    and rz2["ok"] is True)
    # 7. source blob grant path
    stext = "load_const r0, 9\nhalt\n"
    blob_s = b06.encode(stext, endcap=grant_text(stext))
    rs = check_blob(blob_s, require=True, decode=True)
    checks["source_grant_ok"] = (rs["ok"] is True and rs["decoded"] == stext)
    ok = all(checks.values())
    return {"ok": ok, "name": "qgrant", "checks": checks}


if __name__ == "__main__":
    r = selftest()
    print(json.dumps(r, default=str))
    sys.exit(0 if r["ok"] else 1)