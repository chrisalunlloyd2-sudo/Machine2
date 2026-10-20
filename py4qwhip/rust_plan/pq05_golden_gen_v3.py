"""pq05_golden_gen_v3.py -- golden vectors for the Rust step-5 graph-core port.

Generates rust\\graph_golden.json from the LIVE Python reference
(C:\\Viper\\projects\\BDI_FSM_AGENT\\bdi_fsm): reachability.py + planner_proofs.py.
Deterministic: no randomness, no timestamps; edge order fixed by construction.
Rust must reproduce every result object and error string byte-for-byte.

Run (PY311, isolated):  C:\\...\\Python311\\python.exe -I pq05_golden_gen_v3.py
Last line of stdout = JSON verdict.
"""
import json
import os
import sys

sys.path.insert(0, r"C:\Viper\projects\BDI_FSM_AGENT")
from bdi_fsm import reachability as rc, planner_proofs as pp  # noqa: E402

OUT = r"C:\Viper\projects\py4qwhip\rust_plan\graph_golden.json"
SCRATCH = r"C:\Users\viper\AppData\Local\hermes\cache\scratch"
ERR = (rc.ReachabilityError, IndexError, KeyError, ValueError)


class Duck:
    """Duck-types bdi_fsm FSM: _transitions[state][event] = (to, guard)."""

    def __init__(self, state, trans):
        self.state = state
        self._transitions = trans


def mk(edges, state="RUNNING"):
    trans = {}
    for f, ev, t, g in edges:
        trans.setdefault(f, {})[ev] = (t, g)
    return Duck(state, trans)


def run_op(name, fn, *args, **kw):
    try:
        r = fn(*args, **kw)
        return {"op": name, "posargs": ["<" + type(a).__name__ + ">" if a is None else a
                                        for a in args[1:]],
                "args": kw, "result": json.loads(json.dumps(r)), "error": None}
    except ERR as e:
        return {"op": name, "posargs": ["<" + type(a).__name__ + ">" if a is None else a
                                        for a in args[1:]],
                "args": kw, "result": None, "error": str(e)}


def formula_cases():
    cases = []
    formulas = [
        "a", "~a | b", "a & b | ~b", "a -> b", "a <-> b",
        "a & (b | ~c) -> d", "p & ~p", "a | ~a", "a & ~b",
        "a & (b -> c) <-> (~d | e)", "a0 & b_x | ~Y9",
        "((a", "a)", "a & & b", "~", "", "a @ b", "1",
    ]
    cases.append({"formula": None, "tt": None, "error": None,
                  "verdict": rc.guard_verdict(None)[0], "verdict_tt": None})
    for f in formulas:
        c = {"formula": f, "tt": None, "error": None, "verdict": None, "verdict_tt": None}
        try:
            c["tt"] = json.loads(json.dumps(rc.truth_table(f)))
        except ERR as e:
            c["error"] = str(e)
        try:
            verdict, tt2 = rc.guard_verdict(f)
            c["verdict"] = verdict
            c["verdict_tt"] = json.loads(json.dumps(tt2)) if tt2 is not None else None
        except ERR as e:
            c["verdict"] = "ERROR"
            c["verdict_tt"] = str(e)
        cases.append(c)
    return cases


def graph_cases():
    cases = []

    def add(name, edges, state, ops):
        cases.append({"name": name, "edges": edges, "state": state, "ops": ops})

    # G1: the py4qwhip VM status graph (vm_graph_proof ModelFSM shape)
    vm_edges = [
        ["RUNNING", "step_ok", "RUNNING", None],
        ["RUNNING", "halt_or_ret_or_pc_end", "HALTED", None],
        ["RUNNING", "vmerror_or_trap_or_step_limit", "FAULT", None],
        ["RUNNING", "import_op", "SYNTH_PENDING", None],
        ["SYNTH_PENDING", "resolved", "RUNNING", None],
        ["SYNTH_PENDING", "retry_exhausted", "FAULT", None],
    ]
    f1 = mk(vm_edges, "RUNNING")
    t = ["HALTED", "FAULT"]
    add("vm_status", vm_edges, "RUNNING", [
        run_op("audit", pp.planner_audit, f1, goals=t),
        run_op("verify_path", rc.verify_path, f1, "HALTED", start="RUNNING"),
        run_op("verify_path", rc.verify_path, f1, "FAULT", start="RUNNING"),
        run_op("prove_exit", rc.prove_exit, f1, goals=t),
        run_op("deadlock", pp.deadlock_report, f1, terminals=t),
        run_op("liveness", pp.liveness, f1, terminals=t),
        run_op("liveness", pp.liveness, f1),
        run_op("termination", pp.termination, f1),
    ])

    # G2: guarded graph with self-loop + UNSAT-guarded sink
    g2 = [
        ["IDLE", "go", "WORK", "ready"],
        ["WORK", "done", "DONE", None],
        ["WORK", "skip", "IDLE", None],
        ["WORK", "back", "WORK", None],
        ["IDLE", "blocked", "NOGO", "p & ~p"],
        ["NOGO", "wake", "WORK", "ready"],
    ]
    f2 = mk(g2, "IDLE")
    add("guarded_loop", g2, "IDLE", [
        run_op("deadlock", pp.deadlock_report, f2, terminals=["DONE"]),
        run_op("liveness", pp.liveness, f2, goals=["DONE"]),
        run_op("termination", pp.termination, f2, goals=["DONE"]),
        run_op("verify_path", rc.verify_path, f2, "DONE", start="IDLE"),
        run_op("verify_path", rc.verify_path, f2, "NOGO", start="IDLE"),
        run_op("prove_exit", rc.prove_exit, f2, start="IDLE", goals=["DONE"]),
        run_op("audit", pp.planner_audit, f2, terminals=["DONE"]),
    ])

    # G3: liveness/dreadlock blocked by an UNSAT guard
    g3 = [["A", "go", "B", "p & ~p"]]
    f3 = mk(g3, "A")
    add("unsat_blocked", g3, "A", [
        run_op("deadlock", pp.deadlock_report, f3),
        run_op("liveness", pp.liveness, f3),
        run_op("verify_path", rc.verify_path, f3, "B", start="A"),
        run_op("termination", pp.termination, f3),
    ])

    # G4: cyclic control loop, no terminals
    g4 = [["RUNNING", "tick", "RUNNING", "go"]]
    f4 = mk(g4, "RUNNING")
    add("no_terminals", g4, "RUNNING", [
        run_op("liveness", pp.liveness, f4),
        run_op("prove_exit", rc.prove_exit, f4),
        run_op("deadlock", pp.deadlock_report, f4, terminals=[]),
        run_op("termination", pp.termination, f4),
        run_op("audit", pp.planner_audit, f4),
    ])

    # G5: path depth limits, missing start state, start==goal, cyclic mid-graph
    g5 = [["A", "e1", "B", "x | y"], ["B", "e2", "C", None], ["C", "e3", "B", None]]
    f5 = mk(g5, "A")
    add("paths", g5, "A", [
        run_op("verify_path", rc.verify_path, f5, "C", start="A", max_depth=1),
        run_op("verify_path", rc.verify_path, f5, "C", start="A"),
        run_op("verify_path", rc.verify_path, f5, "C"),
        run_op("verify_path", rc.verify_path, f5, "C", start="C"),
        run_op("path_to", rc.path_to, f5, "C", start="A"),
        run_op("prove_exit", rc.prove_exit, f5, start="A", goals=["C"]),
    ])

    # G6: UNSAT-guarded only exit
    g6 = [["S", "e", "T", "~q"]]
    f6 = mk(g6, "S")
    add("unsat_only", g6, "S", [
        run_op("deadlock", pp.deadlock_report, f6),
        run_op("liveness", pp.liveness, f6),
        run_op("termination", pp.termination, f6),
        run_op("total", pp.total_correctness, f6, goals=["T"]),
        run_op("audit", pp.planner_audit, f6),
    ])
    return cases


def main():
    doc = {"generator": "pq05_golden_gen_v3.py",
           "reference": "BDI_FSM_AGENT bdi_fsm reachability.py + planner_proofs.py",
           "note": ("Rust port graph.rs must reproduce every result VALUE exactly; "
                    "objects compare as parsed JSON (key order free), "
                    "error strings byte-for-byte."),
           "formula_cases": formula_cases(),
           "graph_cases": graph_cases()}
    os.makedirs(SCRATCH, exist_ok=True)
    tmp = os.path.join(SCRATCH, "pq05_gen_out.json")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, sort_keys=True)
    os.replace(tmp, OUT)
    n_f = len(doc["formula_cases"])
    n_ops = sum(len(c["ops"]) for c in doc["graph_cases"])
    errs = sum(1 for c in doc["formula_cases"] if c["error"]) + \
           sum(1 for c in doc["graph_cases"] for o in c["ops"] if o["error"])
    print(json.dumps({"generator": "pq05_golden_gen_v3", "verdict": "GREEN",
                      "file": OUT, "bytes": os.path.getsize(OUT),
                      "formula_cases": n_f, "graph_cases": len(doc["graph_cases"]),
                      "ops": n_ops, "error_cases": errs}))


if __name__ == "__main__":
    main()