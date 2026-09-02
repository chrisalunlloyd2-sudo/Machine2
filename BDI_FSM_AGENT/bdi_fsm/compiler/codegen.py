"""codegen.py — back-end: instruction selection + register allocation + output.

Maps IR to a 4-register machine (r0-r3, r3 reserved as spill scratch) via
linear-scan register allocation, spilling excess temps to the stack, then emits
assembly. Deterministic, stdlib-only.

Target ISA:
  mov rX, imm | mov rX, rY | add/sub/mul/div/mod/and/or/xor rX,rY,rZ
  neg/not rX, rY | cmp rX, rY | setlt/setle/setgt/setge/seteq/setne rX
  load rX, [sp+k] | store [sp+k], rX | print rX | halt
  label: | jmp label | jlt/jle/jgt/jge/jeq/jne label
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .errors import CompileError
from .ir import dest as _dest, uses as _uses

_SCRATCH = "r3"
_CMPSET = {"<": "setlt", ">": "setgt", "<=": "setle", ">=": "setge",
           "==": "seteq", "!=": "setne"}
_ARITH = {"+": "add", "-": "sub", "*": "mul", "/": "div", "%": "mod",
          "&&": "and", "||": "or"}


def allocate_registers(instrs, num_regs: int = 3):
    """Linear-scan register allocation.

    Returns (reg_map {temp: reg_index}, spilled {temp}). Each temp's live
    interval is [def_idx, last_use_idx]; intervals sorted by start, spilled
    when registers exhaust (evict the live temp with the farthest end).
    """
    live = {}
    for idx, ins in enumerate(instrs):
        d = _dest(ins)
        if d:
            live.setdefault(d, [idx, idx])[1] = idx
        for u in _uses(ins):
            live.setdefault(u, [idx, idx])[1] = idx

    order = sorted(live.items(), key=lambda kv: kv[1][0])
    active = []  # list of (end, temp, reg)
    reg_map: Dict[str, int] = {}
    spilled = set()
    for temp, (start, end) in order:
        active = [(e, t, r) for (e, t, r) in active if e >= start]
        used_regs = {r for (_, _, r) in active}
        free = [r for r in range(num_regs) if r not in used_regs]
        if free:
            r = free[0]
            reg_map[temp] = r
            active.append((end, temp, r))
        else:
            active.sort(key=lambda x: -x[0])
            e, t, r = active[0]
            if e > end:
                # evict the far-end temp, give its register to current
                spilled.add(t)
                reg_map.pop(t, None)
                reg_map[temp] = r
                active[0] = (end, temp, r)
            else:
                spilled.add(temp)
    return reg_map, spilled


class CodeGen:
    def __init__(self, instrs, vars_):
        self.instrs = instrs
        self.vars = vars_
        self.var_offset = {v: i * 4 for i, v in enumerate(vars_)}
        self.reg_map, self.spilled = allocate_registers(instrs)
        base = len(vars_) * 4
        self.spill_slots = {}
        for t in sorted(self.spilled):
            self.spill_slots[t] = base
            base += 4
        self.asm: List[str] = []
        self._lbl = 0

    def fresh_label(self, p="L") -> str:
        l = f"{p}{self._lbl}"
        self._lbl += 1
        return l

    # -- register helpers -------------------------------------------------
    def reg(self, t) -> Optional[str]:
        r = self.reg_map.get(t)
        return f"r{r}" if r is not None else None

    def load_spilled(self, t) -> str:
        off = self.spill_slots[t]
        self.asm.append(f"  load {_SCRATCH}, [sp+{off}]")
        return _SCRATCH

    def operand(self, t, alt=None) -> str:
        """Register holding t. Spilled temps load into r3 (or alt reg)."""
        r = self.reg(t)
        if r is not None:
            return r
        if alt is not None:
            off = self.spill_slots[t]
            self.asm.append(f"  load {alt}, [sp+{off}]")
            return alt
        return self.load_spilled(t)

    def commit(self, t, rd) -> None:
        """If t is spilled, store rd to its slot."""
        if t in self.spilled:
            off = self.spill_slots[t]
            self.asm.append(f"  store [sp+{off}], {rd}")

    def dest_reg(self, t) -> str:
        r = self.reg(t)
        return r if r is not None else _SCRATCH

    # -- emission ---------------------------------------------------------
    def generate(self) -> str:
        for ins in self.instrs:
            op = ins[0]
            if op == "const":
                self.emit_const(ins[1], ins[2])
            elif op == "binop":
                self.emit_binop(ins[1], ins[2], ins[3], ins[4])
            elif op == "unop":
                self.emit_unop(ins[1], ins[2], ins[3])
            elif op == "load":
                self.emit_load(ins[1], ins[2])
            elif op == "store":
                self.emit_store(ins[1], ins[2])
            elif op == "branch":
                self.emit_branch(ins[1], ins[2], ins[3])
            elif op == "jump":
                self.asm.append(f"  jmp {ins[1]}")
            elif op == "label":
                self.asm.append(f"{ins[1]}:")
            elif op == "print":
                self.asm.append(f"  print {self.operand(ins[1])}")
            else:
                raise CompileError(f"unknown IR op {op!r}")
        self.asm.append("  halt")
        return "\n".join(self.asm)

    def emit_const(self, d, v):
        rd = self.dest_reg(d)
        self.asm.append(f"  mov {rd}, {v}")
        self.commit(d, rd)

    def emit_binop(self, d, op, a, b):
        if op in _CMPSET:
            # comparisons: cmp + set (materialize bool from flags)
            ra = self.operand(a)
            rb = self.operand(b)
            self.asm.append(f"  cmp {ra}, {rb}")
            rd = self.dest_reg(d)
            self.asm.append(f"  {_CMPSET[op]} {rd}")
            self.commit(d, rd)
            return
        mop = _ARITH[op]
        rd = self.dest_reg(d)
        if a in self.spilled and b in self.spilled and rd == _SCRATCH:
            # rare: dest + both operands spilled; use a scratch stack slot
            sa = self.spill_slots[a]
            off = self.spill_slots[b]
            self.asm.append(f"  load {_SCRATCH}, [sp+{sa}]")
            self.asm.append(f"  store [sp+{max(self.spill_slots.values()) + 4}], {_SCRATCH}")
            self.asm.append(f"  load {_SCRATCH}, [sp+{off}]")
            self.asm.append(f"  load r0, [sp+{max(self.spill_slots.values()) + 4}]")
            self.asm.append(f"  {mop} {_SCRATCH}, r0, {_SCRATCH}")
            self.commit(d, _SCRATCH)
            return
        ra = self.operand(a, alt=rd)
        rb = self.operand(b, alt=rd)
        self.asm.append(f"  {mop} {rd}, {ra}, {rb}")
        self.commit(d, rd)

    def emit_unop(self, d, op, a):
        rd = self.dest_reg(d)
        ra = self.operand(a, alt=rd)
        mop = "neg" if op == "-" else "not"
        self.asm.append(f"  {mop} {rd}, {ra}")
        self.commit(d, rd)

    def emit_load(self, d, var):
        rd = self.dest_reg(d)
        off = self.var_offset[var]
        self.asm.append(f"  load {rd}, [sp+{off}]")
        self.commit(d, rd)

    def emit_store(self, var, src):
        off = self.var_offset[var]
        rs = self.operand(src)
        self.asm.append(f"  store [sp+{off}], {rs}")

    def emit_branch(self, c, tl, fl):
        rc = self.operand(c)
        self.asm.append(f"  cmp {rc}, 0")
        self.asm.append(f"  jne {tl}")
        self.asm.append(f"  jmp {fl}")


def generate(instrs, vars_) -> str:
    return CodeGen(instrs, vars_).generate()
