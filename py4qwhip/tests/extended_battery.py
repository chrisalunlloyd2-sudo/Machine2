"""py4qwhip extended battery (Claude, 10-14). Complements blocks\05_testrunner.py.
Side-effect free: uses synth_skeleton/assemble/Machine only (never run_feed/submit).
Run: python -I C:\Viper\projects\py4qwhip\tests\extended_battery.py  -> last line = JSON verdict
"""
import glob, importlib.util, json, os, re

BLK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "blocks")
FEED = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "gap_feed.jsonl")
ENV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "alt", "envelope_claude.py")


def load(path, name):
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def main():
    checks, notes = {}, {}
    vm = load(os.path.join(BLK, "04_vm.py"), "pq_vm")
    b1, b3 = vm.b01, vm.b03
    jobs = [json.loads(l) for l in open(FEED, encoding="utf-8") if l.strip()]
    synth, hashes, fps, markers = [], {}, set(), True
    for j in jobs:
        try:
            s = b3.synth_skeleton(j); synth.append(s)
            hashes[j["module"]] = b1.content_hash(s["program"]); fps.add(s["fingerprint"])
            st = vm.Machine(s["program"], None, 1000).run()
            markers &= (st["status"] == "HALTED" and st["outs"] == ["SKELETON:%s" % j["module"]])
        except Exception as e:
            notes.setdefault("synth_errors", []).append("%s: %s" % (j.get("module"), e))
    checks["feed_all_synthesize"] = len(synth) == len(jobs) and len(jobs) > 0
    checks["feed_deterministic"] = all(b1.content_hash(b3.synth_skeleton(j)["program"]) == hashes.get(j["module"])
                                       for j in jobs if j["module"] in hashes)
    checks["fingerprints_distinct_per_gap"] = len(fps) == len({(j["kind"], j["module"]) for j in jobs})
    checks["skeleton_is_explicit_marker"] = bool(markers)
    notes["skeleton_note"] = "skeleton HALTs printing SKELETON:<module> (a marker, not a fake result); docstring says 'raises' -- mismatch"
    src = {os.path.basename(f): open(f, encoding="utf-8").read() for f in glob.glob(os.path.join(BLK, "0*.py"))}
    # ADVISORY (not pass/fail): sys.path edits are the very trick py4qwhip exists to remove.
    # Known: 03 inserts C:\Viper\scripts (to import code_ledger), 04 inserts its own dir.
    adv = {n: len(re.findall(r"sys\.path\.(?:insert|append)", t)) for n, t in src.items()}
    notes["advisory_sys_path_edits"] = {n: c for n, c in adv.items() if c}
    checks["no_network_imports"] = not any(re.search(r"^\s*(import|from)\s+(socket|urllib|requests|http|ssl|ftplib|smtplib)", t, re.M) for t in src.values())
    checks["all_blocks_marked_done"] = all(os.path.exists(f[:-3] + ".done") for f in glob.glob(os.path.join(BLK, "0*.py")))
    try:
        env = load(ENV, "pq_env")
        blob = env.encode(json.dumps(synth[0]["program"], sort_keys=True, default=str))
        bad = bytearray(blob); bad[-1] ^= 1
        try:
            env.decode(bytes(bad)); tamper = False
        except Exception:
            tamper = True
        checks["envelope_wraps_program_and_catches_tamper"] = tamper and env.decode(blob) == json.dumps(synth[0]["program"], sort_keys=True, default=str)
    except Exception as e:
        checks["envelope_wraps_program_and_catches_tamper"] = False; notes["envelope_error"] = str(e)[:120]
    ok = all(checks.values())
    print(json.dumps({"runner": "py4qwhip extended", "passed": sum(checks.values()), "total": len(checks), "advisory": notes.get("advisory_sys_path_edits", {}),
                      "verdict": "GREEN" if ok else "RED", "checks": checks, "notes": notes}))


if __name__ == "__main__":
    main()
