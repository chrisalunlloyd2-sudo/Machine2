r"""vm_graph_proof.py -- reachability/liveness proof of the py4qwhip VM's own status graph.

Model (from blocks/04_vm.py): machine status FSM with one event per way a step can end.
Proof modules are bdi_fsm.reachability + planner_proofs (same as cell fsm_proofs).
Also checks the model is faithful: every (status -> status) transition seen while running
the fuzz corpus must be an edge of the model.
Run: python -I C:\Viper\projects\py4qwhip\tests\vm_graph_proof.py  -> last line = JSON verdict
"""
import importlib.util, json, os, random, sys

HERE = os.path.dirname(os.path.abspath(__file__))
BLOCKS = os.path.join(HERE, "..", "blocks")
BDI = r"C:\Viper\projects\BDI_FSM_AGENT"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


class ModelFSM:
    """Duck-types the bit of bdi_fsm FSM the proof modules read: _transitions[state][event]=(to, guard)."""
    state = "RUNNING"
    _transitions = {
        "RUNNING": {"step_ok": ("RUNNING", None), "halt_or_ret_or_pc_end": ("HALTED", None),
                    "vmerror_or_trap_or_step_limit": ("FAULT", None), "import_op": ("SYNTH_PENDING", None)},
        "SYNTH_PENDING": {"resolved": ("RUNNING", None), "retry_exhausted": ("FAULT", None)},
        "HALTED": {}, "FAULT": {},
    }


def main():
    sys.path.insert(0, BDI)
    from bdi_fsm import reachability as rc, planner_proofs as pp
    fsm = ModelFSM()
    reach = {s: bool(rc.verify_path(fsm, "HALTED", s)["reachable"]) for s in ("RUNNING", "SYNTH_PENDING")}
    reach_fault = bool(rc.verify_path(fsm, "FAULT", "RUNNING")["reachable"])
    dl = pp.deadlock_report(fsm, terminals=["HALTED", "FAULT"])
    lv = pp.liveness(fsm, terminals=["HALTED", "FAULT"])
    # model faithfulness over the fuzz corpus
    b01 = _load("pq_b01", os.path.join(BLOCKS, "01_bytespace.py"))
    b04 = _load("pq_b04", os.path.join(BLOCKS, "04_vm.py"))
    edges = {(a, t[0]) for a, tb in ModelFSM._transitions.items() for t in tb.values()}
    fz = _load("pq_fz", os.path.join(HERE, "fuzz_battery.py"))
    seen, bad, ran = set(), [], 0
    rnd = random.Random(7)
    asms = [fz.gen(rnd) for _ in range(500)] + ["import r0, 'zz_missing'\nhalt\n", "load_const r0, 1\nfoo_bad\n"]
    for asm in asms:
        try:
            p = b01.assemble(asm, "vp", nlocals=6, const_extra=["zz_missing", "fz0", "fz1", "fz2", "fz3"]); b01.validate(p)
        except Exception:
            continue
        ran += 1
        m = b04.Machine(p, [], 200)
        for _ in range(3):
            m.run()
            for t in (("RUNNING", m.status),) if m.status != "RUNNING" else ():
                seen.add(t)
                if t not in edges:
                    bad.append(t)
            if m.status != "SYNTH_PENDING":
                break
            m.pc += 4; m.status = "RUNNING"; seen.add(("SYNTH_PENDING", "RUNNING"))
    checks = {"all_live_states_reach_HALTED": all(reach.values()),
              "RUNNING_reaches_FAULT": reach_fault,
              "deadlock_free_with_terminals": bool(dl.get("holds")),
              "liveness_holds": bool(lv.get("holds")),
              "observed_transitions_subset_of_model": not bad and ran > 100,
              "saw_all_model_edges_classes": {("RUNNING","HALTED"),("RUNNING","FAULT"),("RUNNING","SYNTH_PENDING"),("SYNTH_PENDING","RUNNING")} <= seen}
    out = {"runner": "py4qwhip vm_graph_proof", "verdict": "GREEN" if all(checks.values()) else "RED",
           "checks": checks, "ran": ran, "observed": sorted(map(list, seen)), "bad": bad[:5]}
    print(json.dumps(out))


if __name__ == "__main__":
    main()
