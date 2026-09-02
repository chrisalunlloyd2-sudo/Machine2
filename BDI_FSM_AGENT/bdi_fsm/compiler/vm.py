"""vm.py — a tiny interpreter for the target ISA (for end-to-end tests).

Deterministic, stdlib-only. Not part of the compile pipeline; it is the
EXECUTION surface that proves the generated assembly is correct.
"""

from __future__ import annotations

from typing import Dict, List

from .errors import CompileError


def run(asm: str, stack_size: int = 1024, max_steps: int = 100000):
    """Execute assembly; returns the list of printed values."""
    regs: Dict[str, int] = {f"r{i}": 0 for i in range(4)}
    flags = {"lt": False, "eq": False, "gt": False}
    stack = [0] * stack_size
    pc = 0
    output: List[int] = []
    lines = [ln for ln in asm.splitlines() if ln.strip()]
    labels: Dict[str, int] = {}
    for i, ln in enumerate(lines):
        s = ln.strip()
        if s.endswith(":") and not s.startswith("  "):
            labels[s[:-1]] = i

    def cmp_flags(x, y):
        flags["lt"] = x < y
        flags["eq"] = x == y
        flags["gt"] = x > y

    steps = 0
    while pc < len(lines):
        steps += 1
        if steps > max_steps:
            raise CompileError("VM: step limit exceeded (possible infinite loop)")
        raw = lines[pc].strip()
        pc += 1
        if raw.endswith(":"):
            continue
        parts = raw.replace(",", " ").split()
        op = parts[0]
        if op == "halt":
            return output
        if op == "mov":
            if parts[2].lstrip("-").isdigit():
                regs[parts[1]] = int(parts[2])
            else:
                regs[parts[1]] = regs[parts[2]]
        elif op in ("add", "sub", "mul", "div", "mod", "and", "or", "xor"):
            a, b = regs[parts[2]], regs[parts[3]]
            if op == "add":
                regs[parts[1]] = a + b
            elif op == "sub":
                regs[parts[1]] = a - b
            elif op == "mul":
                regs[parts[1]] = a * b
            elif op == "div":
                regs[parts[1]] = a // b
            elif op == "mod":
                regs[parts[1]] = a % b
            elif op == "and":
                regs[parts[1]] = 1 if (a and b) else 0
            elif op == "or":
                regs[parts[1]] = 1 if (a or b) else 0
            elif op == "xor":
                regs[parts[1]] = 1 if (a != b) else 0
        elif op in ("neg", "not"):
            regs[parts[1]] = -regs[parts[2]] if op == "neg" else (0 if regs[parts[2]] else 1)
        elif op == "cmp":
            def _v(x):
                return regs[x] if x in regs else int(x)
            cmp_flags(_v(parts[1]), _v(parts[2]))
        elif op in ("setlt", "setle", "setgt", "setge", "seteq", "setne"):
            f = {"setlt": "lt", "setle": lambda: flags["lt"] or flags["eq"],
                 "setgt": "gt", "setge": lambda: flags["gt"] or flags["eq"],
                 "seteq": "eq", "setne": lambda: not flags["eq"]}[op]
            if callable(f):
                regs[parts[1]] = 1 if f() else 0
            else:
                regs[parts[1]] = 1 if flags[f] else 0
        elif op == "load":
            off = int(parts[2].split("+")[1].strip().strip("]"))
            regs[parts[1]] = stack[off // 4]
        elif op == "store":
            off = int(parts[1].split("+")[1].strip().strip("]"))
            stack[off // 4] = regs[parts[2]]
        elif op == "print":
            output.append(regs[parts[1]])
        elif op == "jmp":
            pc = labels[parts[1]]
        elif op in ("jlt", "jle", "jgt", "jge", "jeq", "jne"):
            cond = {"jlt": flags["lt"], "jle": flags["lt"] or flags["eq"],
                    "jgt": flags["gt"], "jge": flags["gt"] or flags["eq"],
                    "jeq": flags["eq"], "jne": not flags["eq"]}[op]
            if cond:
                pc = labels[parts[1]]
        else:
            raise CompileError(f"VM: unknown op {op!r}")
    return output
