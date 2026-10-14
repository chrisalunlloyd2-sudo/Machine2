"""py4qwhip block 01 — byte-space: content-addressed bytecode for the QWhip runtime.

Design notes (Chris, verbatim, 2026-10-12):
  "Every [missing-module crash] is a crash in a normal runtime and a *synthesis
   job* in py4qwhip. Loop closure instead of ModuleNotFoundError, forever."
  "Rust owns the metal and Python riding as the guest world."
  "credentials tagged to the bytecode itself, 'to steal it you have to be
   handed it'".

This block is the DATA layer: instruction encoding, assembler, disassembler,
canonical hashing (ties to ledger id 5076 bytecode_normalizer conventions).
Deterministic, stdlib-only, no I/O, no network. Local-only by construction.

Instruction format (fixed layout, 1 byte opcode):
    0x00 NOP                 -
    0x01 LOAD_CONST  r, idx:u16
    0x02 LOAD_LOCAL  r, slot
    0x03 STORE_LOCAL r, slot
    0x04 ADD   dst, a, b      0x05 SUB  0x06 MUL  0x07 EQ  0x08 LT
    0x09 JUMP  rel:s16 (relative to next instruction)
    0x0a JIF   r, rel:s16
    0x0b CALL  dst, fnreg, argc
    0x0c RET   src
    0x0d IMPORT dst, nameidx:u16   <- the loop-closure op (block 04 consumes)
    0x0e HALT
    0x0f STRCAT dst, a, b
    0x10 LEN   dst, a
    0x11 OUT   src

Author: Hermes (Hermes=dense-code lane, per tasks/py4qwhip_lanes_20261012.md)
"""
from __future__ import annotations

import hashlib
import json
import struct
from typing import Any, Dict, List, Optional, Tuple

MAGIC = b"PY4QW01"
VERSION = 1
MAX_POOL = 65535
MAX_LOCALS = 255
MAX_ARity = 255

# op -> (mnemonic, operand kinds)
#   kinds: R = 1-byte reg/slot/argc, C = u16 const index, J = s16 jump offset
OPS: Dict[int, Tuple[str, Tuple[str, ...]]] = {
    0x00: ("NOP", ()),
    0x01: ("LOAD_CONST", ("R", "C")),
    0x02: ("LOAD_LOCAL", ("R", "R")),
    0x03: ("STORE_LOCAL", ("R", "R")),
    0x04: ("ADD", ("R", "R", "R")),
    0x05: ("SUB", ("R", "R", "R")),
    0x06: ("MUL", ("R", "R", "R")),
    0x07: ("EQ", ("R", "R", "R")),
    0x08: ("LT", ("R", "R", "R")),
    0x09: ("JUMP", ("J",)),
    0x0A: ("JIF", ("R", "J")),
    0x0B: ("CALL", ("R", "R", "R")),
    0x0C: ("RET", ("R",)),
    0x0D: ("IMPORT", ("R", "C")),
    0x0E: ("HALT", ()),
    0x0F: ("STRCAT", ("R", "R", "R")),
    0x10: ("LEN", ("R", "R")),
    0x11: ("OUT", ("R",)),
}
BY_NAME = {name: (code, kinds) for code, (name, kinds) in OPS.items()}
OP_SIZE = {code: 1 + sum(2 if k == "C" or k == "J" else 1 for k in kinds)
           for code, (name, kinds) in OPS.items()}

POOL_TYPES = {"i": 0, "s": 1, "b": 2, "f": 3}


class BytespaceError(Exception):
    """Deterministic bytecode fault (validation / encoding)."""


def _pack_operand(kind: str, val: int) -> bytes:
    if kind in ("R",):
        if not (0 <= val <= MAX_LOCALS):
            raise BytespaceError("operand out of range: %r" % (val,))
        return bytes((val,))
    if kind == "C":
        if not (0 <= val <= MAX_POOL):
            raise BytespaceError("const index out of range: %r" % (val,))
        return struct.pack("<H", val)
    if kind == "J":
        if not (-32768 <= val <= 32767):
            raise BytespaceError("jump offset out of range: %r" % (val,))
        return struct.pack("<h", val)
    raise BytespaceError("bad operand kind %r" % (kind,))


def canonical_pool_value(v: Any) -> Tuple[str, Any]:
    if isinstance(v, bool):
        return "i", int(v)
    if isinstance(v, int):
        return "i", v
    if isinstance(v, float):
        return "f", float(v)
    if isinstance(v, str):
        return "s", v
    if isinstance(v, (bytes, bytearray)):
        return "b", bytes(v)
    raise BytespaceError("unsupported const pool type: %s" % type(v).__name__)


def canonical_bytes(program: Dict[str, Any]) -> bytes:
    """Byte-exact canonical serialization (content address = sha256 of this)."""
    if program.get("magic") != MAGIC.decode("ascii"):
        raise BytespaceError("magic mismatch")
    code = bytes(program.get("code", b""))
    out = bytearray()
    out += MAGIC
    out += struct.pack("<B", VERSION)
    name = str(program.get("name", "")).encode("utf-8")
    out += struct.pack("<H", len(name)) + name
    out += struct.pack("<B", int(program.get("nlocals", 0)))
    pool = list(program.get("const_pool", []))
    out += struct.pack("<H", len(pool))
    for v in pool:
        tag, val = canonical_pool_value(v)
        if tag == "i":
            payload = struct.pack("<q", val)
        elif tag == "f":
            payload = struct.pack("<d", val)
        elif tag == "s":
            payload = val.encode("utf-8")
        else:
            payload = val
        out += struct.pack("<B", POOL_TYPES[tag])
        out += struct.pack("<I", len(payload)) + payload
    out += struct.pack("<I", len(code)) + code
    return bytes(out)


def content_hash(program: Dict[str, Any]) -> str:
    return hashlib.sha256(canonical_bytes(program)).hexdigest()[:16]


# ---------------------------------------------------------------- assembler

def _parse_line(line: str, lineno: int):
    s = line.split("#", 1)[0].strip()
    if not s:
        return None, None
    if s.endswith(":") and "," not in s and len(s.split()) == 1:
        return ("label", s[:-1]), None
    parts = [p for p in s.replace(",", " ").split()]
    op = parts[0].upper()
    args = parts[1:]
    return ("instr", op, args), lineno


def assemble(text: str, name: str = "prog", nlocals: int = 8,
             const_extra: Optional[List[Any]] = None) -> Dict[str, Any]:
    """Assemble asm text -> program dict. Labels become resolved BYTE jumps.

    Two-pass: pass 1 sizes every instruction (labels included as zero-width),
    pass 2 emits code with rel = target_byte - after_instr_byte.
    """
    labels: Dict[str, int] = {}      # label -> instruction index
    ins: List[Tuple[str, List[str]]] = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        item, _ = _parse_line(raw, lineno)
        if item is None:
            continue
        if item[0] == "label":
            lbl = item[1]
            if lbl in labels:
                raise BytespaceError("duplicate label %r" % lbl)
            labels[lbl] = len(ins)
        else:
            ins.append((item[1], item[2]))
    if not ins and not labels:
        raise BytespaceError("empty program")

    # pass 1: instruction index -> byte offset
    ins_bytes: List[int] = []
    off = 0
    for (opname, args) in ins:
        if opname not in BY_NAME:
            raise BytespaceError("unknown op %r" % opname)
        ins_bytes.append(off)
        opc, kinds = BY_NAME[opname]
        off += OP_SIZE[opc]
    label_byte: Dict[str, int] = {}
    for lbl, idx in labels.items():
        if idx >= len(ins):
            label_byte[lbl] = off       # label past last instruction = EOF
        else:
            label_byte[lbl] = ins_bytes[idx]

    pool: List[Any] = list(const_extra or [])
    code = bytearray()

    def reg_or(tok: str) -> int:
        if not tok.startswith("r"):
            raise BytespaceError("expected register, got %r" % tok)
        return int(tok[1:])

    def const_idx(v: Any) -> int:
        for i, existing in enumerate(pool):
            if type(existing) is type(v) and existing == v:
                return i
        if len(pool) > MAX_POOL:
            raise BytespaceError("const pool overflow")
        pool.append(v)
        return len(pool) - 1

    for idx, (opname, args) in enumerate(ins):
        opc, kinds = BY_NAME[opname]
        if len(args) != len(kinds):
            raise BytespaceError("%s wants %d operands, got %r"
                                 % (opname, len(kinds), args))
        code.append(opc)
        after_byte = ins_bytes[idx] + OP_SIZE[opc]
        for k, a in zip(kinds, args):
            if k == "R":
                code += _pack_operand("R", reg_or(a) if a.startswith("r")
                                      else int(a))
            elif k == "C":
                if len(a) >= 2 and a[0] == a[-1] and a[0] in ("'", '"'):
                    a = a[1:-1]      # string literal: strip quotes (dedupe in pool)
                v: Any = int(a) if a.lstrip("-").isdigit() else a
                if isinstance(v, str) and v.startswith("r"):
                    raise BytespaceError("const slot got register %r" % a)
                code += _pack_operand("C", const_idx(v))
            else:  # J: rel in BYTES relative to the next instruction
                if a not in label_byte:
                    raise BytespaceError("unknown label %r" % a)
                rel = label_byte[a] - after_byte
                code += _pack_operand("J", rel)
    prog = {"magic": MAGIC.decode("ascii"), "version": VERSION, "name": name,
            "nlocals": int(nlocals), "const_pool": pool,
            "code": bytes(code)}
    validate(prog)
    return prog


def disassemble(program: Dict[str, Any]) -> str:
    """Program -> asm text (round-trips through assemble)."""
    code = bytes(program["code"])
    lines: List[Tuple[int, str, List[str]]] = []  # (instr_idx, name, vals)
    pc = 0
    while pc < len(code):
        opc = code[pc]
        if opc not in OPS:
            raise BytespaceError("bad opcode 0x%02x at %d" % (opc, pc))
        name, kinds = OPS[opc]
        size = OP_SIZE[opc]
        operands = code[pc + 1:pc + size]
        vals: List[str] = []
        oi = 0
        for k in kinds:
            if k == "R":
                vals.append("r%d" % operands[oi]); oi += 1
            elif k == "C":
                iv = struct.unpack("<H", operands[oi:oi + 2])[0]
                pool_v = (program["const_pool"][iv]
                          if iv < len(program["const_pool"]) else iv)
                vals.append(repr(pool_v) if isinstance(pool_v, str) else str(pool_v))
                oi += 2
            else:
                rel = struct.unpack("<h", operands[oi:oi + 2])[0]
                vals.append("@%d" % (pc + size + rel))  # rel is from the NEXT instruction (2026-10-14 fuzz fix; was pc+rel)
                oi += 2
        lines.append((len(lines), name, vals))
        pc += size
    # labels sit at any byte offset a jump targets
    label_at: Dict[int, str] = {}
    for (_, name2, vals2) in lines:
        for v in vals2:
            if v.startswith("@"):
                label_at[int(v[1:])] = "L%d" % int(v[1:])
    # byte offset of each instruction, for matching labels to lines
    out: List[str] = []
    for (idx, name2, vals2) in lines:
        # recompute this instruction's byte offset by walking sizes
        off = 0
        for (j, n3, _) in lines[:idx]:
            off += OP_SIZE[BY_NAME[n3][0]]
        if off in label_at:
            out.append("%s:" % label_at[off])
        fixed = []
        for v in vals2:
            if v.startswith("@"):
                fixed.append(label_at[int(v[1:])])
            else:
                fixed.append(v)
        body = "  %s" % name2 + (" " + ", ".join(fixed) if fixed else "")
        out.append(body)
    if len(code) in label_at:           # jump to end of program (2026-10-14 fuzz fix)
        out.append("%s:" % label_at[len(code)])
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- validation

def validate(program: Dict[str, Any]) -> None:
    if program.get("magic") != MAGIC.decode("ascii"):
        raise BytespaceError("magic mismatch")
    if int(program.get("version", 0)) != VERSION:
        raise BytespaceError("version mismatch")
    nl = int(program.get("nlocals", 0))
    if not (0 <= nl <= MAX_LOCALS):
        raise BytespaceError("nlocals out of range")
    pool = program.get("const_pool", [])
    if len(pool) > MAX_POOL + 1:
        raise BytespaceError("const pool too large")
    for v in pool:
        canonical_pool_value(v)
    code = bytes(program.get("code", b""))
    pc = 0
    while pc < len(code):
        opc = code[pc]
        if opc not in OPS:
            raise BytespaceError("bad opcode 0x%02x at %d" % (opc, pc))
        name, kinds = OPS[opc]
        size = OP_SIZE[opc]
        if pc + size > len(code):
            raise BytespaceError("truncated instruction at %d" % pc)
        oi = pc + 1
        for k in kinds:
            if k == "R" and code[oi] >= nl:
                raise BytespaceError("%s: reg/slot %d >= nlocals at %d"
                                     % (name, code[oi], pc))
            if k == "C" and struct.unpack("<H", code[oi:oi + 2])[0] >= len(pool):
                raise BytespaceError("%s: const idx out of pool at %d" % (name, pc))
            if k == "J":
                rel = struct.unpack("<h", code[oi:oi + 2])[0]
                tgt = pc + size + rel   # 2026-10-14 fuzz/port finding: base is the NEXT instruction (was pc + rel)
                if tgt < 0 or tgt > len(code):   # == len(code) = jump to end-of-program, which assemble() allows
                    raise BytespaceError("%s: jump target out of program at %d"
                                         % (name, pc))
            oi += 2 if k in ("C", "J") else 1
        pc += size


def selftest() -> dict:
    checks = {}
    # 1. roundtrip + hash stability
    p = assemble("load_const r0, 41\n"
                 "load_const r1, 1\n"
                 "add r2, r0, r1\n"
                 "out r2\n"
                 "halt\n",
                 name="t1", nlocals=4)
    validate(p)
    h1 = content_hash(p)
    p2 = assemble(disassemble(p), name="t1", nlocals=4)
    checks["roundtrip_hash_equal"] = (h1 == content_hash(p2))
    # 2. tamper detection
    bad = dict(p)
    bad["code"] = bytearray(p["code"]); bad["code"][1] ^= 0xFF
    bad["code"] = bytes(bad["code"])
    try:
        validate(bad)
        checks["tamper_caught"] = False
    except BytespaceError:
        checks["tamper_caught"] = True
    # 3. canonical bytes deterministic
    checks["hash_deterministic"] = content_hash(p) == content_hash(
        assemble(disassemble(p), name="t1", nlocals=4))
    # 4. jump assembly + validation
    jmp = assemble("load_const r0, 3\n"
                   "jif r0, end\n"
                   "load_const r1, 'never'\n"
                   "out r1\n"
                   "end:\n"
                   "halt\n", name="t2", nlocals=4,
                   const_extra=["never"])
    checks["jump_validates"] = (validate(jmp) is None)
    ok = all(checks.values())
    return {"ok": ok, "name": "bytespace", "checks": checks,
            "content_hash_sample": h1,
            "loc": __doc__.count("\n") + len(open(__file__, encoding="utf-8")
                                          .read().splitlines())}


if __name__ == "__main__":
    import sys
    r = selftest()
    print(json.dumps(r, default=str))
    sys.exit(0 if r["ok"] else 1)