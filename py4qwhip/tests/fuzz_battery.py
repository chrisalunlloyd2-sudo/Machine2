"""py4qwhip differential/property fuzz (Claude 10-14). Deterministic (seeded), side-effect free.
Properties per random program: assemble+validate ok; hash stable; assemble(disassemble(p)) same hash;
VM deterministic and terminates (HALTED/FAULT); tampered code never hangs or raises non-trapped errors.
Also emits fuzz_corpus.json (programs + expected hash/status/outs) = Rust differential-fuzz input.
Run: python -I tests\fuzz_battery.py [N]   last line = JSON verdict
"""
import importlib.util, json, os, random, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
BLK = os.path.join(HERE, "..", "blocks")


def load(f, n):
    s = importlib.util.spec_from_file_location(n, os.path.join(BLK, f))
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def gen(rng):
    n = rng.randint(3, 14)
    lines, labels = ["S0:"], 0     # S0 = program start: backward jumps to offset 0 must validate
    for i in range(n):
        k = rng.random()
        r = lambda: "r%d" % rng.randint(0, 5)
        if k < 0.30:
            lines.append("load_const %s, %d" % (r(), rng.randint(-50, 50)))
        elif k < 0.55:
            lines.append("%s %s, %s, %s" % (rng.choice(["add", "sub", "mul", "eq", "lt"]), r(), r(), r()))
        elif k < 0.70:
            lines.append(rng.choice(["out %s" % r(), "load_local %s, %s" % (r(), r()), "store_local %s, %s" % (r(), r()), "strcat %s, %s, %s" % (r(), r(), r()), "len %s, %s" % (r(), r())]))
        elif k < 0.80:
            lines.append("jif %s, L%d" % (r(), labels)); lines.append("load_const %s, 1" % r())
            lines.append("L%d:" % labels); labels += 1
        elif k < 0.88:
            lines.append("jump L%d" % labels); lines.append("load_const %s, 2" % r())
            lines.append("L%d:" % labels); labels += 1
        elif k < 0.94:
            lines.append("jif %s, S0" % r())
        else:
            lines.append("load_const %s, 'fz%d'" % (r(), rng.randint(0, 3)))
    lines.append("halt")
    return "\n".join(lines) + "\n"


def main(N):
    import faulthandler; faulthandler.dump_traceback_later(60, exit=True)   # a hang must print its stack and stop, never block the hive cell
    vm = load("04_vm.py", "pq_vm"); b1 = vm.b01
    rng = random.Random(20261014)
    bad = {"assemble": 0, "hash_unstable": 0, "roundtrip": 0, "vm_nondeterministic": 0,
           "vm_not_terminating": 0, "tamper_untrapped": 0}
    first_fail, corpus, tcorpus, t0 = {}, [], [], time.time()
    stat = {"HALTED": 0, "FAULT": 0, "other": 0}
    for i in range(N):
        asm = gen(rng)
        pool = ["fz0", "fz1", "fz2", "fz3"]
        try:
            p = b1.assemble(asm, "fz%d" % i, nlocals=6, const_extra=pool); b1.validate(p)
        except Exception as e:
            bad["assemble"] += 1; first_fail.setdefault("assemble", (asm, str(e)[:100])); continue
        h = b1.content_hash(p)
        if h != b1.content_hash(p): bad["hash_unstable"] += 1
        try:
            if b1.content_hash(b1.assemble(b1.disassemble(p), "fz%d" % i, nlocals=6, const_extra=pool)) != h:
                bad["roundtrip"] += 1; first_fail.setdefault("roundtrip", (asm, "hash differs"))
        except Exception as e:
            bad["roundtrip"] += 1; first_fail.setdefault("roundtrip", (asm, str(e)[:100]))
        a = vm.Machine(p, None, 500).run(); b = vm.Machine(p, None, 500).run()
        if (a["status"], a["outs"]) != (b["status"], b["outs"]): bad["vm_nondeterministic"] += 1
        if a["status"] not in ("HALTED", "FAULT"): bad["vm_not_terminating"] += 1; stat["other"] += 1
        else: stat[a["status"]] += 1
        if i % 4 == 0 and p["code"]:
            t = dict(p); c = bytearray(p["code"]); c[rng.randrange(len(c))] ^= rng.randint(1, 255); t["code"] = bytes(c)
            try:
                s = vm.Machine(t, None, 500).run()
                if len(tcorpus) < 400:
                    tcorpus.append({"nlocals": 6, "pool": t["const_pool"], "code_hex": t["code"].hex(), "status": s["status"],
                                    "fault": s["fault"], "steps": s["steps"], "pending_import": s["pending_import"],
                                    "outs": s["outs"], "regs": s["regs"]})
                if s["status"] not in ("HALTED", "FAULT", "SYNTH_PENDING"): bad["tamper_untrapped"] += 1   # a flipped byte may become IMPORT
            except Exception as e:
                bad["tamper_untrapped"] += 1; first_fail.setdefault("tamper", (asm, "%s: %s" % (type(e).__name__, str(e)[:80])))
        if i < 200:
            corpus.append({"asm": asm, "const_extra": pool, "nlocals": 6, "content_hash": h,
                           "status": a["status"], "outs": a["outs"],
                           "fault": a["fault"], "steps": a["steps"], "regs": a["regs"]})
    try:
        json.dump(corpus, open(os.path.join(HERE, "..", "rust_plan", "fuzz_corpus.json"), "w"), indent=0)
        json.dump(tcorpus, open(os.path.join(HERE, "..", "rust_plan", "fuzz_tamper_corpus.json"), "w"), indent=0)
    except Exception:
        pass
    ok = not any(bad.values())
    print(json.dumps({"runner": "py4qwhip fuzz", "n": N, "secs": round(time.time() - t0, 1),
                      "verdict": "GREEN" if ok else "RED", "bad": bad, "vm_status": stat,
                      "first_fail": {k: [v[0][:200], v[1]] for k, v in first_fail.items()}}))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 2000)
