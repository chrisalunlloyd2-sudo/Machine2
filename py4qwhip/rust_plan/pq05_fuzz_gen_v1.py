#!/usr/bin/env python3
"""pq05_fuzz_gen_v1.py -- differential-fuzz corpus generator (plan step-5 fuzz gate).

Mirrors pq05_golden_gen_v3.py's harness exactly (sys.path setup, ERR tuple =
(rc.ReachabilityError, IndexError, KeyError, ValueError), Duck/mk() collapse,
run_op shape, formula-case try blocks), but generates 10,000 cases: 5,000
formula cases + 5,000 graph cases (first 9 graph groups are the GOLDEN G1-G6
anchors verbatim plus falsy-chain stress anchors; the rest are seeded-random).

Corpus exclusions (documented, deliberate):
  * zero-edge FSMs: liveness crashes via next(iter(adj)) -> StopIteration,
    outside the ERR tuple (generation would die). Golden graphs all have edges.
  * duplicate (from,event) pairs: mk() would silently overwrite the tuple;
    excluded so the Rust edge-order reconstruction sees the same FSM.
  * None goals: only nonsense calls.

Differential rule (same as golden): result objects equal as parsed JSON (key
order free), error strings byte-for-byte.

Run (PY311, isolated):  C:\\...\\Python311\\python.exe -I pq05_fuzz_gen_v1.py
Last line of stdout = JSON verdict.
"""
import json
import os
import random
import sys

sys.path.insert(0, r"C:\Viper\projects\BDI_FSM_AGENT")
from bdi_fsm import reachability as rc, planner_proofs as pp  # noqa: E402

OUT = r"C:\Viper\projects\py4qwhip\rust_plan\graph_fuzz_corpus.json"


ERR = (rc.ReachabilityError, IndexError, KeyError, ValueError)
SEED = 20261016


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


def formula_case(f, cases):
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


def formula_cases(rng, total=5000):
    cases = []
    cases.append({"formula": None, "tt": None, "error": None,
                  "verdict": rc.guard_verdict(None)[0], "verdict_tt": None})
    stress = [
        "1", "a @ b", "~", "a & & b", "()", "", "((a", "a)",
        "& a", "a &", "a |", "| a", "a ->", "-> a", "a <-> <-> b",
        "()()", "a ()", "  ", "a  b", "(()~", "~ ~",
        "a & ( b ) )", "((((((((a))))))))", "a&b", "a|b", "a->b", "a<->b",
        "a & b & c & (d | ~e) -> f", "p & ~p", "x | y", "done",
    ]
    for f in stress:
        formula_case(f, cases)

    def rnd_atom():
        return rng.choice(["a", "b", "c", "d", "p", "q", "x", "y",
                           "ready", "go", "done", "a0", "b_x", "Y9"])

    def build(depth):
        r = rng.random()
        if depth <= 0 or r < 0.35:
            a = rnd_atom()
            return ("~" * rng.randint(0, 2) + a) if rng.random() < 0.3 else a
        if r < 0.5:
            return "~(" + build(depth - 1) + ")"
        if r < 0.75:
            return "(" + build(depth - 1) + ")"
        return build(depth - 1) + " " + rng.choice(["&", "|", "->", "<->"]) + \
            " " + build(depth - 1)

    while len(cases) < total:
        r = rng.random()
        if r < 0.05:
            formula_case(build(1), cases)
        elif r < 0.10:
            base = build(4)
            pos = rng.randint(0, len(base))
            formula_case(base[:pos] + rng.choice("@1#()~&|-><->$") + base[pos:], cases)
        else:
            formula_case(build(3), cases)
    return cases


STATES = ["A", "B", "C", "D", "E", "IDLE", "RUNNING", "WORK", "DONE", "NOGO",
          "HALTED", "FAULT", "T"]
EVENTS = ["e1", "e2", "e3", "go", "done", "skip", "back", "wake", "step_ok",
          "halt_or_ret_or_pc_end", "vmerror_or_trap_or_step_limit", "tick"]
GUARDS = [None, None, None, "ready", "p & ~p", "x | y", "~q", "~go",
          "a & b -> c", "", "?", "a ->", "(a | b) & ~c", "done"]


def rnd_terminals(rng, states):
    r = rng.random()
    if r < 0.25:
        return None
    if r < 0.45:
        return []
    return rng.sample(states, rng.randint(1, min(3, len(states))))


def rnd_goals(rng, states):
    r = rng.random()
    if r < 0.25:
        return None
    if r < 0.45:
        return []
    return rng.sample(states, rng.randint(1, min(3, len(states))))


def rnd_fsm(rng):
    states = rng.sample(STATES, rng.choice([2, 2, 3, 3, 4, 5]))
    edges = []
    pairs = set()
    for _ in range(rng.choice([1, 1, 2, 2, 3, 4, 5, 6, 8])):
        f, t = rng.choice(states), rng.choice(states)
        ev = rng.choice(EVENTS)
        if (f, ev) in pairs:            # mk() would collapse; exclude instead
            continue
        pairs.add((f, ev))
        edges.append([f, ev, t, rng.choice(GUARDS)])
    if not edges:
        edges.append([states[0], "go", rng.choice(states), None])
    state = None if rng.random() < 0.10 else rng.choice(states)
    return states, edges, state


def graph_cases(rng, total=5000):
    cases = []

    def emit(name, edges, state, ops):
        cases.append({"name": name, "edges": edges, "state": state, "ops": ops})

    # ---- G1..G6: verbatim golden anchors (same edges / states / ops as V3) ----
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
    emit("vm_status", vm_edges, "RUNNING", [
        run_op("audit", pp.planner_audit, f1, goals=t),
        run_op("verify_path", rc.verify_path, f1, "HALTED", start="RUNNING"),
        run_op("verify_path", rc.verify_path, f1, "FAULT", start="RUNNING"),
        run_op("prove_exit", rc.prove_exit, f1, goals=t),
        run_op("deadlock", pp.deadlock_report, f1, terminals=t),
        run_op("liveness", pp.liveness, f1, terminals=t),
        run_op("liveness", pp.liveness, f1),
        run_op("termination", pp.termination, f1),
    ])

    g2 = [
        ["IDLE", "go", "WORK", "ready"],
        ["WORK", "done", "DONE", None],
        ["WORK", "skip", "IDLE", None],
        ["WORK", "back", "WORK", None],
        ["IDLE", "blocked", "NOGO", "p & ~p"],
        ["NOGO", "wake", "WORK", "ready"],
    ]
    f2 = mk(g2, "IDLE")
    emit("guarded_loop", g2, "IDLE", [
        run_op("deadlock", pp.deadlock_report, f2, terminals=["DONE"]),
        run_op("liveness", pp.liveness, f2, goals=["DONE"]),
        run_op("termination", pp.termination, f2, goals=["DONE"]),
        run_op("verify_path", rc.verify_path, f2, "DONE", start="IDLE"),
        run_op("verify_path", rc.verify_path, f2, "NOGO", start="IDLE"),
        run_op("prove_exit", rc.prove_exit, f2, start="IDLE", goals=["DONE"]),
        run_op("audit", pp.planner_audit, f2, terminals=["DONE"]),
    ])

    g3 = [["A", "go", "B", "p & ~p"]]
    f3 = mk(g3, "A")
    emit("unsat_blocked", g3, "A", [
        run_op("deadlock", pp.deadlock_report, f3),
        run_op("liveness", pp.liveness, f3),
        run_op("verify_path", rc.verify_path, f3, "B", start="A"),
        run_op("termination", pp.termination, f3),
    ])

    g4 = [["RUNNING", "tick", "RUNNING", "go"]]
    f4 = mk(g4, "RUNNING")
    emit("no_terminals", g4, "RUNNING", [
        run_op("liveness", pp.liveness, f4),
        run_op("prove_exit", rc.prove_exit, f4),
        run_op("deadlock", pp.deadlock_report, f4, terminals=[]),
        run_op("termination", pp.termination, f4),
        run_op("audit", pp.planner_audit, f4),
    ])

    g5 = [["A", "e1", "B", "x | y"], ["B", "e2", "C", None], ["C", "e3", "B", None]]
    f5 = mk(g5, "A")
    emit("paths", g5, "A", [
        run_op("verify_path", rc.verify_path, f5, "C", start="A", max_depth=1),
        run_op("verify_path", rc.verify_path, f5, "C", start="A"),
        run_op("verify_path", rc.verify_path, f5, "C"),
        run_op("verify_path", rc.verify_path, f5, "C", start="C"),
        run_op("path_to", rc.path_to, f5, "C", start="A"),
        run_op("prove_exit", rc.prove_exit, f5, start="A", goals=["C"]),
    ])

    g6 = [["S", "e", "T", "~q"]]
    f6 = mk(g6, "S")
    emit("unsat_only", g6, "S", [
        run_op("deadlock", pp.deadlock_report, f6),
        run_op("liveness", pp.liveness, f6),
        run_op("termination", pp.termination, f6),
        run_op("total", pp.total_correctness, f6, goals=["T"]),
        run_op("audit", pp.planner_audit, f6),
    ])

    # ---- falsy-chain stress anchors ----
    g7 = [["A", "e1", "B", None], ["B", "e2", "C", ""]]
    f7 = mk(g7, "A")
    emit("empty_guard", g7, "A", [
        run_op("verify_path", rc.verify_path, f7, "C", start=""),
        run_op("verify_path", rc.verify_path, f7, "C", start=None),
        run_op("deadlock", pp.deadlock_report, f7, terminals=[]),
        run_op("liveness", pp.liveness, f7),
    ])
    g8 = [["S", "e", "T", "q"]]
    f8 = mk(g8, None)
    emit("null_state", g8, None, [
        run_op("verify_path", rc.verify_path, f8, "T"),
        run_op("verify_path", rc.verify_path, f8, "IDLE"),
        run_op("path_to", rc.path_to, f8, "T"),
        run_op("total", pp.total_correctness, f8, goals=["T"]),
    ])
    g9 = [["A", "loop", "A", "go"]]
    f9 = mk(g9, "A")
    emit("depth_stress", g9, "A", [
        run_op("verify_path", rc.verify_path, f9, "A", start="A", max_depth=0),
        run_op("verify_path", rc.verify_path, f9, "A", start="A", max_depth=-1),
        run_op("path_to", rc.path_to, f9, "A", start="A"),
    ])

    # ---- seeded-random fill ----
    def random_case(idx):
        states, edges, state = rnd_fsm(rng)
        fsm = mk(edges, state)
        ops = []
        for _ in range(rng.randint(1, 4)):
            opname = rng.choice(["audit", "verify_path", "prove_exit", "deadlock",
                                 "liveness", "termination", "path_to", "total"])
            terms = rnd_terminals(rng, states)
            goals = rnd_goals(rng, states)
            if opname == "audit":
                kw = {}
                if rng.random() < 0.5:
                    kw["terminals"] = terms
                if rng.random() < 0.5:
                    kw["goals"] = goals
                ops.append(run_op("audit", pp.planner_audit, fsm, **kw))
            elif opname == "deadlock":
                kw = {} if rng.random() < 0.3 else {"terminals": terms}
                ops.append(run_op("deadlock", pp.deadlock_report, fsm, **kw))
            elif opname == "liveness":
                kw = {}
                if rng.random() < 0.4:
                    kw["terminals"] = terms
                if rng.random() < 0.6:
                    kw["goals"] = goals
                ops.append(run_op("liveness", pp.liveness, fsm, **kw))
            elif opname == "termination":
                kw = {} if rng.random() < 0.3 else {"goals": goals}
                ops.append(run_op("termination", pp.termination, fsm, **kw))
            elif opname == "prove_exit":
                kw = {}
                if rng.random() < 0.5:
                    kw["goals"] = goals
                if rng.random() < 0.4:
                    kw["start"] = rng.choice([None, ""] + states)
                ops.append(run_op("prove_exit", rc.prove_exit, fsm, **kw))
            elif opname == "total":
                ops.append(run_op("total", pp.total_correctness, fsm, goals=goals))
            else:
                goal = rng.choice(states + ["MISSING"])
                kw = {}
                r = rng.random()
                if r < 0.15:
                    kw["start"] = None
                elif r < 0.25:
                    kw["start"] = ""
                elif r < 0.40:
                    kw["start"] = rng.choice(states + ["MISSING"])
                if rng.random() < 0.5:
                    kw["max_depth"] = rng.choice([None, 0, 1, 2, 3, -1])
                fn = rc.verify_path if opname == "verify_path" else rc.path_to
                ops.append(run_op(opname, fn, fsm, goal, **kw))
        emit("fz%05d" % idx, edges, state, ops)

    for i in range(total - 9):
        random_case(i)
    return cases


def main():
    rng = random.Random(SEED)
    doc = {"generator": "pq05_fuzz_gen_v1.py",
           "reference": "BDI_FSM_AGENT bdi_fsm reachability.py + planner_proofs.py",
           "seed": SEED,
           "note": ("differential corpus: Rust graph_fuzz.rs must reproduce every "
                    "result VALUE exactly; objects compare as parsed JSON (key "
                    "order free), error strings byte-for-byte. Same harness as "
                    "pq05_golden_gen_v3: ERR tuple, mk() collapse, run_op shape."),
           "formula_cases": formula_cases(rng),
           "graph_cases": graph_cases(rng)}
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, separators=(",", ":"))
    os.replace(tmp, OUT)
    n_f = len(doc["formula_cases"])
    n_ops = sum(len(c["ops"]) for c in doc["graph_cases"])
    errs = sum(1 for c in doc["formula_cases"] if c["error"]) + \
        sum(1 for c in doc["graph_cases"] for o in c["ops"] if o["error"])
    print(json.dumps({"generator": "pq05_fuzz_gen_v1", "verdict": "GREEN",
                      "file": OUT, "bytes": os.path.getsize(OUT),
                      "formula_cases": n_f, "graph_cases": len(doc["graph_cases"]),
                      "ops": n_ops, "error_cases": errs}))


if __name__ == "__main__":
    main()