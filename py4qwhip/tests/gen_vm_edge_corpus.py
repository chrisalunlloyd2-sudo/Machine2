r"""Writes rust_plan/vm_edge_corpus.json: hand-built edge programs + random raw-bytecode programs (validate-clean,
jump rel unconstrained so targets land mid-instruction). Expected values come from the Python 04_vm (the spec).
Run: python -I tests\gen_vm_edge_corpus.py"""
import importlib.util, json, os, random, struct, collections
HERE = os.path.dirname(os.path.abspath(__file__)); BLK = os.path.join(HERE, "..", "blocks")
def load(f, n):
    s = importlib.util.spec_from_file_location(n, os.path.join(BLK, f)); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
vm = load("04_vm.py", "pq_vm"); b1 = vm.b01
cases = []
def rec(code, pool, nl=6):
    p = {"magic": "PY4QW01", "version": 1, "name": "e", "nlocals": nl, "const_pool": list(pool), "code": bytes(code)}
    s = vm.Machine(p, None, 500).run()
    cases.append({"nlocals": nl, "pool": list(pool), "code_hex": bytes(code).hex(), "status": s["status"], "fault": s["fault"],
                  "steps": s["steps"], "pending_import": s["pending_import"], "outs": s["outs"], "regs": s["regs"]})
def asm(text, extra):
    p = b1.assemble(text, "e", nlocals=6, const_extra=extra); rec(p["code"], p["const_pool"])
MAX = 9223372036854775807
asm("load_const r0, 9223372036854775807\nload_const r1, 1\nadd r2, r0, r1\nout r2\nhalt\n", [])
asm("load_const r0, 9223372036854775807\nload_const r1, 2\nmul r2, r0, r1\nout r2\nhalt\n", [])
asm("load_const r0, -9223372036854775807\nload_const r1, 3\nsub r2, r0, r1\nout r2\nhalt\n", [])
asm("load_const r0, 9223372036854775807\nload_const r1, 1\nsub r2, r0, r1\nout r2\nhalt\n", [])
asm("eq r0, r1, r1\nload_const r2, 5\nadd r3, r0, r2\nlt r4, r0, r2\nlen r5, r0\nstrcat r1, r0, r2\nout r3\nout r4\nout r5\nout r1\nhalt\n", [])
asm("load_const r0, 'ab'\nload_const r1, 'cd'\nadd r2, r0, r1\nout r2\nsub r3, r0, r1\nhalt\n", [])
asm("load_const r0, 'ab'\nmul r1, r0, r2\nhalt\n", [])
asm("load_const r0, 'ab'\nload_const r1, 3\nadd r2, r0, r1\nhalt\n", [])
asm("import r0, 'cpuinfo'\nout r0\nhalt\n", [])
asm("call r0, r1, r2\nhalt\n", [])
asm("load_const r0, 'héllo世'\nlen r1, r0\nload_const r2, -12345\nlen r3, r2\nout r1\nout r3\nhalt\n", [])
asm("load_const r0, 'x'\n" + "strcat r0, r0, r0\n" * 14 + "strcat r1, r0, r0\nlen r2, r1\nlen r3, r0\nout r2\nout r3\nhalt\n", [])
asm("lt r0, r1, r1\neq r2, r1, r1\nload_const r3, 4\neq r4, r2, r3\nlt r5, r2, r3\nout r0\nout r2\nout r4\nout r5\nhalt\n", [])
asm("load_const r0, 7\nload_local r1, r0\nstore_local r1, r2\nout r2\nretx\n".replace("retx\n", "ret r0\n"), [])
rng = random.Random(20261014)
SZ = {0:1,1:4,2:3,3:3,4:4,5:4,6:4,7:4,8:4,9:3,10:4,11:4,12:2,13:4,14:1,15:4,16:3,17:2}
KIND = {0:"",1:"RC",2:"RR",3:"RR",4:"RRR",5:"RRR",6:"RRR",7:"RRR",8:"RRR",9:"J",10:"RJ",11:"RRR",12:"R",13:"RC",14:"",15:"RRR",16:"RR",17:"R"}
pool = [0, 1, -1, 7, 9, 255, "a", "bc", "", 9223372036854775807, -5, 3]
tries = 0
while len([c for c in cases if True]) < 14 + 400 and tries < 200000:
    tries += 1
    code = bytearray()
    for _ in range(rng.randint(2, 9)):
        op = rng.choice([1,1,1,2,3,4,5,6,7,8,9,10,10,11,13,15,16,17,17,0,12,14])
        code.append(op)
        for k in KIND[op]:
            if k == "R": code.append(rng.randint(0, 5))
            elif k == "C": code += struct.pack("<H", rng.randint(0, len(pool) - 1))
            else: code += struct.pack("<h", rng.randint(-9, 9))
    try:
        b1.validate({"magic": "PY4QW01", "version": 1, "name": "e", "nlocals": 6, "const_pool": pool, "code": bytes(code)})
    except Exception:
        continue
    rec(code, pool)
c = collections.Counter(((x["fault"] or "")[:26] or x["status"]) for x in cases[14:])
print(len(cases), dict(c.most_common(12)))
json.dump(cases, open(os.path.join(HERE, "..", "rust_plan", "vm_edge_corpus.json"), "w"), indent=0)
