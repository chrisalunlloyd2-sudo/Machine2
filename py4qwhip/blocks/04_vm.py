"""py4qwhip block 04 — vm: the bytecode-eating runtime (loop-closure dispatch).

Design notes (Chris, verbatim, 2026-10-12):
  "py4qwhip is a runtime that *eats* bytecode on its way to Redox the 'main
   port,' with Rust owning the metal and Python riding as the guest world."
  "Every one of those is a crash in a normal runtime and a *synthesis job* in
   py4qwhip. Loop closure instead of ModuleNotFoundError, forever."

The VM executes block-01 programs (stdlib-only, deterministic, step-limited
— conventions from ledger id 1728). Its distinguishing op is IMPORT (0x0D):
   a normal runtime raises ModuleNotFoundError;
   this VM pauses with status 'SYNTH_PENDING' and asks the synthesize engine
   (block 03) to close the loop, then retries — ModuleNotFoundError, never.
No I/O, no network, no model calls. QW-7 credential tagging note: programs
are content-hashed (block 01); the hash is the grant key — to run someone's
bytecode you must be *handed* the hash (block 05 wires this into checks).

Author: Hermes (Hermes=dense-code lane, per tasks/py4qwhip_lanes_20261012.md)
"""
from __future__ import annotations

import json
import struct
import sys, os
from typing import Any, Dict, List, Optional, Tuple

import importlib.util  # 2026-10-14: sys.path edit removed; siblings load by file path


def _load_local(fname: str, modname: str):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), fname)
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


b01 = _load_local("01_bytespace.py", "pq4_b01")
b03 = _load_local("03_synthesize.py", "pq4_b03")
b07 = _load_local("07_qgrant.py", "pq4_b07")
b06_local = _load_local("06_envelope.py", "pq4_b06_04")


class VMError(Exception):
    """Deterministic VM fault (trapped at a pc, never a bare crash)."""


# Statuses (deterministic, part of the contract)
RUNNING = "RUNNING"
HALTED = "HALTED"
SYNTH_PENDING = "SYNTH_PENDING"   # IMPORT op needs loop closure
FAULT = "FAULT"

MAX_STEPS_DEFAULT = 100_000
MAX_SYNTH_RETRIES = 3
MAX_STR = 10_000  # string ops clamp (deterministic, no runaway builds)


class Machine:
    """One executing frame. nlocals registers; const_pool; IMPORT loop-closure."""

    def __init__(self, program: Dict[str, Any], inputs: Optional[List[Any]] = None,
                 max_steps: int = MAX_STEPS_DEFAULT):
        try:
            b01.validate(program)
        except Exception as e:          # hand-tampered bytecode: trap, don't crash
            self.regs = []
            self.program = program
            self.pool = []
            self.nlocals = 0
            self.pc = 0
            self.steps = 0
            self.max_steps = int(max_steps)
            self.status = FAULT
            self.fault = "validate: %s" % e
            self.pending_import = None
            self.synth_retries = 0
            self._outs: List[Any] = []
            self._inputs = []
            return
        self.program = program
        self.pool = list(program.get("const_pool", []))
        self.nlocals = int(program["nlocals"])
        self.regs: List[Any] = [None] * self.nlocals
        self.pc = 0
        self.steps = 0
        self.max_steps = int(max_steps)
        self.status = RUNNING
        self.fault: Optional[str] = None
        self.pending_import: Optional[str] = None
        self.synth_retries = 0
        self._outs: List[Any] = []
        self._inputs = list(inputs or [])

    # ---- helpers
    def out(self) -> List[Any]:
        return list(self._outs)

    def _const(self, idx: int) -> Any:
        if not (0 <= idx < len(self.pool)):
            raise VMError("const idx %d out of pool" % idx)
        return self.pool[idx]

    def _str(self, v: Any) -> str:
        s = "" if v is None else (v if isinstance(v, str) else json.dumps(v)
                                  if not isinstance(v, (int, float, bool)) else str(v))
        return s[:MAX_STR]

    # ---- the step function
    def step(self) -> None:
        code = self.program["code"]
        if self.pc >= len(code):
            self.status = HALTED
            return
        if self.pc < 0:
            raise IndexError("pc")   # 2026-10-14: a jump into mid-instruction bytes can go negative; never wrap
        opc = code[self.pc]
        name, kinds = b01.OPS[opc]
        off = self.pc + 1

        def _rd(o, fmt):
            if o < 0 or o + 2 > len(code):
                raise IndexError("operand")   # 2026-10-14: short read = IndexError (was struct.error, untrapped)
            return struct.unpack(fmt, code[o:o + 2])[0]
        u16 = lambda o: _rd(o, "<H")  # noqa: E731
        s16 = lambda o: _rd(o, "<h")  # noqa: E731

        if name == "NOP":
            pass
        elif name == "LOAD_CONST":
            self.regs[code[off]] = self._const(u16(off + 1)); off += 3
        elif name == "LOAD_LOCAL":
            slot = code[off]; dst = code[off + 1]; off += 2  # 2026-10-14: rd() was undefined (NameError on every LOAD_LOCAL)
            self.regs[dst] = self.regs[slot]
        elif name == "STORE_LOCAL":
            src = code[off]; slot = code[off + 1]; off += 2  # 2026-10-14: rd() was undefined (NameError on every STORE_LOCAL)
            self.regs[slot] = self.regs[src]
        elif name in ("ADD", "SUB", "MUL", "EQ", "LT"):
            d, a, b = code[off], code[off + 1], code[off + 2]; off += 3
            va, vb = self.regs[a], self.regs[b]
            if name == "ADD":
                v = (va + vb) if (va is not None and vb is not None) else None
            elif name == "SUB":
                v = (va - vb) if (va is not None and vb is not None) else None
            elif name == "MUL":
                if isinstance(va, (str, bytes)) or isinstance(vb, (str, bytes)):
                    raise TypeError("MUL on sequence")   # 2026-10-14 fuzz finding: str*huge-int hung the VM
                v = (va * vb) if (va is not None and vb is not None) else None
            elif name == "EQ":
                v = (va == vb)
            else:
                v = (va < vb) if (va is not None and vb is not None
                                  and isinstance(va, (int, float))
                                  and isinstance(vb, (int, float))) else None
            if name in ("ADD", "SUB", "MUL") and isinstance(v, int) and not isinstance(v, bool):
                if not (-(1 << 63) <= v < (1 << 63)):
                    raise OverflowError("i64")   # 2026-10-14: ints are i64 (spec for the Rust port); checked BEFORE the store, dest unchanged on fault
            self.regs[d] = v
        elif name == "JUMP":
            rel = s16(off); off += 2
            self.pc = self.pc + 3 + rel  # base = next-instr byte + signed rel
            return
        elif name == "JIF":
            r = code[off]; rel = s16(off + 1); off += 3
            if self.regs[r]:
                self.pc = self.pc + 1 + 1 + 2 + rel
                return
        elif name == "CALL":
            raise VMError("CALL unimplemented in block 04 (function frames land in block 06)")
        elif name == "RET":
            self.status = HALTED
            return
        elif name == "IMPORT":
            dst = code[off]; idx = u16(off + 1); off += 3
            modname = self._str(self._const(idx))
            self.pending_import = modname
            self.status = SYNTH_PENDING
            self.regs[dst] = None
            return
        elif name == "HALT":
            self.status = HALTED
            return
        elif name == "STRCAT":
            d, a, b = code[off], code[off + 1], code[off + 2]; off += 3
            self.regs[d] = self._str(self.regs[a]) + self._str(self.regs[b])
        elif name == "LEN":
            d, a = code[off], code[off + 1]; off += 2
            v = self.regs[a]
            self.regs[d] = 0 if v is None else (len(v) if hasattr(v, "__len__") else len(str(v)))
        elif name == "OUT":
            self._outs.append(self.regs[code[off]]); off += 1
        else:
            raise VMError("unhandled opcode %s" % name)
        self.pc = off

    def run(self) -> Dict[str, Any]:
        """Run to HALT/FAULT/step-limit. Returns final state (deterministic)."""
        # -- pq4 wrapper: delegate the run loop to the Rust pq.dll (C ABI) --
        # FILE-LEVEL swap per RUST_PORT_PLAN step 6 (2026-10-21): dict-form
        # program (str name, int nlocals, bytes code), int pc/steps/max_steps,
        # plain-string status, representable pool/regs/outs and encodable
        # strings route to the dll; everything else falls through to the
        # verbatim pure-Python body below so run()'s native behaviour is
        # preserved (D168 fall-through pattern, b01 mirror).
        _prog = self.program
        if (isinstance(_prog, dict) and isinstance(_prog.get("name"), str)
                and isinstance(_prog.get("nlocals"), int)
                and not isinstance(_prog.get("nlocals"), bool)
                and isinstance(_prog.get("code"), bytes)
                and isinstance(self.pc, int) and not isinstance(self.pc, bool)
                and isinstance(self.steps, int) and not isinstance(self.steps, bool)
                and isinstance(self.max_steps, int)
                and not isinstance(self.max_steps, bool)
                and isinstance(self.status, str)
                and (self.fault is None or isinstance(self.fault, str))
                and (self.pending_import is None
                     or isinstance(self.pending_import, str))
                and isinstance(self.pool, list)
                and isinstance(self.regs, list)
                and isinstance(self._outs, list)
                and all(v is None or isinstance(v, (bool, int, float, bytes, str))
                        for v in self.pool)
                and all(v is None or isinstance(v, (bool, int, float, bytes, str))
                        for v in self.regs)
                and all(v is None or isinstance(v, (bool, int, float, bytes, str))
                        for v in self._outs)):
            try:
                _prog["name"].encode("utf-8")
                self.status.encode("utf-8")
                if self.fault is not None:
                    self.fault.encode("utf-8")
                if self.pending_import is not None:
                    self.pending_import.encode("utf-8")
                for _v in self.pool:
                    if isinstance(_v, str):
                        _v.encode("utf-8")
                for _v in self.regs:
                    if isinstance(_v, str):
                        _v.encode("utf-8")
                for _v in self._outs:
                    if isinstance(_v, str):
                        _v.encode("utf-8")
            except UnicodeEncodeError:
                pass  # lone surrogates: only the pure-Python path can hold these
            else:
                import base64 as _b64
                import ctypes
                import sys
                import json as _json
                import os as _os

                def _to_wire(v):
                    if v is None:
                        return {"t": "n", "v": None}
                    if isinstance(v, bool):
                        return {"t": "z", "v": v}
                    if isinstance(v, int):
                        if -(2 ** 63) <= v <= 2 ** 63 - 1:
                            return {"t": "i", "v": v}
                        return {"t": "B", "v": str(v)}
                    if isinstance(v, float):
                        return {"t": "f",
                                "v": "0x%016x" % struct.unpack(
                                    "<Q", struct.pack("<d", v))[0]}
                    if isinstance(v, bytes):
                        return {"t": "b",
                                "v": _b64.b64encode(v).decode("ascii")}
                    return {"t": "s", "v": v}

                def _from_wire(e):
                    t, v = e["t"], e["v"]
                    if t == "n":
                        return None
                    if t == "z":
                        return True if v else False
                    if t in ("i", "B"):
                        return int(v)
                    if t == "f":
                        hx = v[2:] if v.startswith("0x") else v
                        return struct.unpack(">d", bytes.fromhex(hx))[0]
                    if t == "b":
                        return _b64.b64decode(v)
                    return v

                def _lib():
                    got = getattr(Machine.run, "_pq4_lib", None)
                    if got is not None:
                        return got
                    _path = _os.path.join(
                        _os.path.dirname(_os.path.dirname(
                            _os.path.abspath(__file__))),
                        "rust", "pq", "target", "release", "pq.dll")
                    if not _os.path.isfile(_path):
                        print("pq4: pq.dll not found; re-running"
                              " pure-Python body", file=sys.stderr)
                        return None
                    lib = ctypes.CDLL(str(_path))
                    lib.pq_vm_run_json.argtypes = [ctypes.c_char_p]
                    lib.pq_vm_run_json.restype = ctypes.c_void_p
                    lib.pq_free.argtypes = [ctypes.c_void_p]
                    lib.pq_free.restype = None
                    Machine.run._pq4_lib = lib
                    return lib

                req = _json.dumps({
                    "program": {
                        "name": _prog["name"],
                        "nlocals": int(_prog["nlocals"]),
                        "const_pool": [_to_wire(v) for v in self.pool],
                        "code_b64": _b64.b64encode(_prog["code"]).decode(
                            "ascii"),
                    },
                    "pc": self.pc,
                    "steps": self.steps,
                    "max_steps": self.max_steps,
                    "status": self.status,
                    "fault": self.fault,
                    "pending_import": self.pending_import,
                    "outs": [_to_wire(v) for v in self._outs],
                    "regs": [_to_wire(v) for v in self.regs],
                })
                lib = _lib()
                if lib is not None:
                    ptr = lib.pq_vm_run_json(req.encode("utf-8"))
                    if not ptr:
                        print("pq4: pq_vm_run_json returned null;"
                              " re-running pure-Python body", file=sys.stderr)
                    else:
                        _raw = ctypes.string_at(ptr)
                        lib.pq_free(ptr)
                        _resp = _json.loads(_raw.decode("utf-8"))
                        if "error" in _resp:
                            _err = _resp["error"]
                            _msg = (_err.get("message", _err)
                                    if isinstance(_err, dict) else _err)
                            print("pq4: dll refused (%s); re-running"
                                  " pure-Python body"
                                  % _json.dumps(_msg)[:120], file=sys.stderr)
                            # dll refused: fall through to the verbatim
                            # pure-Python body below so the native exception
                            # kind surfaces exactly as unpatched 04_vm would.
                        else:
                            self.pc = int(_resp["pc"])
                            self.steps = int(_resp["steps"])
                            self.status = str(_resp["status"])
                            self.fault = _resp["fault"]
                            self.pending_import = _resp["pending_import"]
                            self._outs = [_from_wire(e) for e in _resp["outs"]]
                            self.regs = [_from_wire(e) for e in _resp["regs"]]
                            return {"status": self.status,
                                    "steps": self.steps,
                                    "fault": self.fault,
                                    "pending_import": self.pending_import,
                                    "outs": self.out(),
                                    "regs": list(self.regs)}

        while self.status == RUNNING:
            self.steps += 1
            if self.steps > self.max_steps:
                self.status = FAULT
                self.fault = "step_limit_exceeded"
                break
            try:
                self.step()
            except VMError as e:
                self.status = FAULT
                self.fault = str(e)
                break
            except (TypeError, ValueError, ArithmeticError, IndexError, KeyError) as e:
                # 2026-10-14 (fuzz finding): operand type mismatch (e.g. SUB str-int) escaped as a bare
                # crash. Trap it as a deterministic fault; type NAME only so a Rust port can match it.
                self.status = FAULT
                self.fault = "trap:" + type(e).__name__
                break
        return {"status": self.status, "steps": self.steps,
                "fault": self.fault, "pending_import": self.pending_import,
                "outs": self.out(), "regs": list(self.regs)}


# ---- loop-closure driver: VM + synthesize engine working together

def resolve_and_run(program: Dict[str, Any],
                    inputs: Optional[List[Any]] = None,
                    max_steps: int = MAX_STEPS_DEFAULT,
                    feed_path: str = b03.GAP_FEED_DEFAULT,
                    grant: Optional[bytes] = None) -> Dict[str, Any]:
    """Run a program; on SYNTH_PENDING, synthesize+register the module, resume.

    This IS the loop closure: the VM never returns ModuleNotFoundError. It
    returns either HALTED (with outs) or FAULT (real faults only).

    grant (QW-7, block 07): when handed an 8-byte endcap, the machine verifies
    it against the program BEFORE executing a single step (docstring contract:
    "to run someone's bytecode you must be handed the hash"). grant=None keeps
    the owner/trusted-local lane ungated. Verification failure is a
    deterministic FAULT "grant: ..." — never an execute-then-fail.
    """
    if grant is not None:
        ok, reason = b07.verify(grant, program, require=True)
        if not ok:
            return {"status": FAULT, "steps": 0, "fault": reason,
                    "pending_import": None, "outs": [],
                    "regs": [], "synth_log": []}
    m = Machine(program, inputs, max_steps)
    synth_log: List[Dict[str, Any]] = []
    while True:
        state = m.run()
        if state["status"] != SYNTH_PENDING:
            state["synth_log"] = synth_log
            return state
        modname = state["pending_import"]
        job = {"kind": "MODULE_MISSING", "module": modname,
               "imported_by": ["py4qwhip_vm"], "gap_id": "MODULE_MISSING:%s" % modname}
        try:
            prior = b03.lookup_prior_art(job)
            synth = b03.synth_skeleton(job)
            b03.submit_synthesis(job, synth, prior)
            action = "synthesized"
        except Exception as e:
            action = "synth_error: %s" % e
        synth_log.append({"module": modname, "action": action,
                          "content_hash": b01.content_hash(synth["program"])
                          if action == "synthesized" else None})
        m.synth_retries += 1
        if m.synth_retries >= MAX_SYNTH_RETRIES:
            m.status = FAULT
            m.fault = "synth_retry_exhausted"
            state2 = m.run()
            state2["synth_log"] = synth_log
            return state2
        # resume: import placeholder resolves to a stub marker; pc moves past IMPORT
        m.pc += 1 + 1 + 2
        m.status = RUNNING
        m.pending_import = None


# ---------------------------------------------------------------- selftest

def selftest() -> dict:
    checks = {}
    # 1. arithmetic program
    p = b01.assemble("load_const r0, 6\n"
                     "load_const r1, 7\n"
                     "mul r2, r0, r1\n"
                     "out r2\n"
                     "halt\n", "t_mul", nlocals=4)
    st = resolve_and_run(p)
    checks["mul_6x7"] = (st["status"] == "HALTED" and st["outs"] == [42])
    # 2. loop closure: IMPORT triggers synthesis, run resumes, no ModuleNotFoundError
    p2 = b01.assemble("import r0, 'cpuinfo'\n"
                      "load_const r1, 'after'\n"
                      "out r1\n"
                      "halt\n", "t_import", nlocals=4,
                      const_extra=["cpuinfo", "after"])
    st2 = resolve_and_run(p2)
    checks["loop_closure"] = (st2["status"] == "HALTED"
                              and st2["synth_log"]
                              and st2["synth_log"][0]["module"] == "cpuinfo"
                              and st2["outs"] == ["after"])
    # 3. step limit (boundless spin)
    p3 = b01.assemble("load_const r0, 1\n"
                      "L:\n"
                      "jif r0, L\n", "t_spin", nlocals=4)
    st3 = resolve_and_run(p3, max_steps=1000)
    checks["step_limit"] = (st3["status"] == "FAULT"
                            and st3["fault"] == "step_limit_exceeded")
    # 4. jump semantics: backward loop that terminates
    p4 = b01.assemble("load_const r0, 3\n"
                      "loop:\n"
                      "load_const r1, 1\n"
                      "sub r0, r0, r1\n"
                      "load_const r2, 0\n"
                      "jif r2, done\n"
                      "jif r0, loop\n"
                      "done:\n"
                      "out r0\n"
                      "halt\n", "t_loop", nlocals=4)
    st4 = resolve_and_run(p4)
    checks["loop_term"] = (st4["status"] == "HALTED" and st4["outs"] == [0])
    # 5. fault trapping: hand-tampered bytecode -> FAULT status, never a raise
    bad = {"magic": "PY4QW01", "version": 1, "name": "bad", "nlocals": 2,
           "const_pool": [5, 6], "code": bytes([0x01, 0x00, 0x00])}
    st5 = resolve_and_run(bad)
    checks["fault_trapped"] = (st5["status"] == "FAULT"
                               and str(st5["fault"]).startswith("validate:"))
    # 6. determinism: same program twice -> same outs
    st6a = resolve_and_run(p)
    st6b = resolve_and_run(p)
    checks["deterministic"] = (st6a["outs"] == st6b["outs"]
                               and st6a["steps"] == st6b["steps"])
    # 7. QW-7 grant gate (block 07): pre-execution verification
    cap = b07.grant(p)
    st7a = resolve_and_run(p, grant=cap)
    checks["grant_ok_runs"] = (st7a["status"] == "HALTED" and st7a["outs"] == [42])
    st7b = resolve_and_run(p, grant=b"\x11" * 8)
    checks["grant_wrong_refused"] = (st7b["status"] == "FAULT"
                                     and st7b["fault"].startswith("grant:")
                                     and st7b["steps"] == 0 and st7b["outs"] == [])
    st7c = resolve_and_run(p, grant=b"\x00" * 8)
    checks["grant_zero_refused"] = (st7c["status"] == "FAULT"
                                    and "zero endcap" in st7c["fault"])
    checks["grant_binds_body"] = (resolve_and_run(
        dict(p, code=p["code"] + b"\x18\x00"), grant=cap)["status"] == "FAULT")
    # 8. end-to-end chain 01->06->07->04: assemble -> grant -> envelope with
    # endcap -> blob gates pass -> decode program back -> VM runs gr blob.
    ptxt = b07._canonical_text(p)
    blob = b06_local.encode(ptxt, endcap=b07.grant_text(ptxt))
    gate = b07.check_blob(blob, require=True, decode=True)
    prog_rt = b07.program_from_text(gate["decoded"])
    st8 = resolve_and_run(prog_rt, grant=b07.grant(prog_rt))
    checks["chain_01060704"] = (gate["ok"] is True and st8["status"] == "HALTED"
                                and st8["outs"] == [42])
    ok = all(checks.values())
    return {"ok": ok, "name": "vm", "checks": checks}


if __name__ == "__main__":
    r = selftest()
    print(json.dumps(r, default=str))
    sys.exit(0 if r["ok"] else 1)