//! Differential fuzz — 10,000-case corpus replayed in Rust (plan step-5 gate).
//!
//! Vectors: ../../rust_plan/graph_fuzz_corpus.json (pq05_fuzz_gen_v1.py, PY311,
//! generated against the live reference the same way as pq05_golden_gen_v3.py:
//! ERR tuple (rc.ReachabilityError, IndexError, KeyError, ValueError), Duck/mk
//! collapse, run_op shape). Differential rule identical to graph_golden.rs:
//! result objects compare as parsed JSON (key order free), error strings
//! byte-for-byte. The first 9 graph anchors are the golden G1-G6 VM/loop cases
//! verbatim plus falsy-chain stress (empty guard, null start, max_depth 0/-1);
//! the rest are seeded-random (SEED 20261016).
//!
//! Corpus exclusions (pinned in the generator): no zero-edge FSMs (reference
//! liveness crashes StopIteration outside the ERR tuple), no duplicate
//! (from,event) pairs (asserted below), no None goals.

use pq::graph::{
    deadlock_report, guard_verdict_str, liveness, path_to, planner_audit, prove_exit,
    termination, total_correctness, truth_table, verify_path, Edge, Graph, ReachabilityError,
};
use serde_json::{json, Value};
use std::fs;

const FG: &str = "../../rust_plan/graph_fuzz_corpus.json";

fn load_corpus() -> Value {
    let text = fs::read_to_string(FG).unwrap_or_else(|e| {
        panic!("cannot read fuzz corpus {FG}: {e} — run pq05_fuzz_gen_v1.py")
    });
    serde_json::from_str(&text).expect("fuzz corpus must parse as JSON")
}

/// Extract kwargs exactly as JSON arrived: null/missing both map to None;
/// explicit values survive — including empty lists, whose None-vs-[]
/// distinction the reference pins by truthiness. (Identical to graph_golden.rs.)
fn opt_str<'a>(args: &'a Value, key: &str) -> Option<&'a str> {
    args.get(key).and_then(|v| v.as_str())
}
fn opt_i64(args: &Value, key: &str) -> Option<i64> {
    args.get(key).and_then(|v| v.as_i64())
}
fn opt_list(args: &Value, key: &str) -> Option<Vec<String>> {
    match args.get(key) {
        Some(Value::Array(items)) => Some(
            items
                .iter()
                .map(|v| v.as_str().expect("list kwarg entries are strings").to_string())
                .collect(),
        ),
        _ => None,
    }
}

/// Same canonical edge order as graph_golden.rs: mk() collapses the raw list
/// into trans[state][event] (duplicate (from,event) would overwrite — the
/// corpus excludes those), and the reference re-flattens grouped by from-state
/// (first appearance), each state's events in first-appearance order.
fn graph_from_case(case: &Value) -> Graph {
    let mut groups: Vec<(String, Vec<Edge>)> = Vec::new();
    for item in case["edges"].as_array().expect("edges array") {
        let a = item.as_array().expect("edge tuple [from, event, to, guard]");
        assert_eq!(a.len(), 4, "edge tuple shape");
        let e = Edge {
            from: a[0].as_str().unwrap().to_string(),
            event: a[1].as_str().unwrap().to_string(),
            to: a[2].as_str().unwrap().to_string(),
            guard: a[3].as_str().map(|g| g.to_string()),
        };
        match groups.iter_mut().find(|(s, _)| *s == e.from) {
            Some((_, es)) => es.push(e),
            None => groups.push((e.from.clone(), vec![e])),
        }
    }
    let edges: Vec<Edge> = groups.into_iter().flat_map(|(_, es)| es).collect();
    Graph {
        state: case["state"].as_str().map(|s| s.to_string()),
        edges,
    }
}

/// Op shape guard: the generator records exactly this call shape.
fn check_shape(name: &str, posargs: &[Value]) {
    match name {
        "verify_path" | "path_to" => {
            assert_eq!(posargs.len(), 1, "{name} takes exactly one posarg (goal)");
        }
        "audit" | "deadlock" | "liveness" | "termination" | "total" | "prove_exit" => {
            assert!(posargs.is_empty(), "{name} takes no posargs");
        }
        other => panic!("unknown fuzz op {other}"),
    }
}

/// Fuzz op-name -> Rust call (identical mapping to graph_golden.rs run_op).
fn run_op(g: &Graph, op: &Value) -> Result<Value, ReachabilityError> {
    let name = op["op"].as_str().expect("op name");
    let posargs = op["posargs"].as_array().cloned().unwrap_or_default();
    let args = &op["args"];
    check_shape(name, &posargs);
    match name {
        "verify_path" => verify_path(
            g,
            posargs[0].as_str().unwrap(),
            opt_str(args, "start"),
            opt_i64(args, "max_depth"),
        ),
        "path_to" => Ok(match path_to(
            g,
            posargs[0].as_str().unwrap(),
            opt_str(args, "start"),
            opt_i64(args, "max_depth"),
        ) {
            Some(edges) => Value::Array(
                edges
                    .iter()
                    .map(|e| {
                        json!({"from": &e.from, "event": &e.event, "to": &e.to,
                               "guard": &e.guard})
                    })
                    .collect(),
            ),
            None => Value::Null,
        }),
        "prove_exit" => prove_exit(
            g,
            opt_list(args, "goals").as_deref(),
            opt_str(args, "start"),
        ),
        "deadlock" => deadlock_report(g, opt_list(args, "terminals").as_deref()),
        "liveness" => {
            let terminals = opt_list(args, "terminals");
            let goals = opt_list(args, "goals");
            liveness(g, terminals.as_deref(), goals.as_deref())
        }
        "termination" => {
            let goals = opt_list(args, "goals");
            termination(g, goals.as_deref())
        }
        "total" => {
            let goals = opt_list(args, "goals");
            total_correctness(g, goals.as_deref())
        }
        "audit" => {
            let terminals = opt_list(args, "terminals");
            let goals = opt_list(args, "goals");
            planner_audit(g, terminals.as_deref(), goals.as_deref())
        }
        _ => unreachable!("shape guard rejected unknown ops"),
    }
}

#[test]
fn fuzz_formula_cases_match_python() {
    let doc = load_corpus();
    let cases = doc["formula_cases"].as_array().expect("formula_cases");
    assert_eq!(cases.len(), 5000, "fuzz corpus formula case count");
    for c in cases {
        let formula = c["formula"].as_str();
        let want_tt = &c["tt"];
        let want_err = &c["error"];
        let want_verdict = &c["verdict"];
        let want_vtt = &c["verdict_tt"];

        let (got_tt, got_err) = match formula {
            // guard is None: python guard_verdict short-circuits; no tt exists
            None => (Value::Null, None),
            Some(f) => match truth_table(f) {
                Ok(tt) => (tt, None),
                Err(e) => (Value::Null, Some(e.0)),
            },
        };
        assert_eq!(&got_tt, want_tt, "truth_table drift for {c:?}");
        match want_err {
            Value::Null => assert!(got_err.is_none(), "unexpected error for {c:?}"),
            want => assert_eq!(
                got_err.as_deref(),
                want.as_str(),
                "error string must match byte-for-byte for {c:?}"
            ),
        }

        let (got_verdict, got_vtt) = match formula {
            None => ("TAUTOLOGY".to_string(), Value::Null),
            Some(f) => match guard_verdict_str(f) {
                Ok((v, Some(tt))) => (v, tt),
                Ok((v, None)) => (v, Value::Null),
                Err(e) => ("ERROR".to_string(), json!(&e.0)),
            },
        };
        assert_eq!(want_verdict, &json!(&got_verdict), "verdict for {c:?}");
        assert_eq!(want_vtt, &got_vtt, "verdict_tt for {c:?}");
    }
}

#[test]
fn fuzz_graph_ops_match_python() {
    let doc = load_corpus();
    let cases = doc["graph_cases"].as_array().expect("graph_cases");
    assert_eq!(cases.len(), 5000, "fuzz corpus graph case count");
    for case in cases {
        // corpus invariant: no duplicate (from,event) pairs (mk would overwrite)
        let mut seen: Vec<(String, String)> = Vec::new();
        for item in case["edges"].as_array().expect("edges array") {
            let a = item.as_array().expect("edge tuple");
            let key = (
                a[0].as_str().unwrap().to_string(),
                a[1].as_str().unwrap().to_string(),
            );
            assert!(!seen.contains(&key), "duplicate (from,event) in case {case:?}");
            seen.push(key);
        }

        let g = graph_from_case(case);
        let gname = case["name"].as_str().unwrap();
        for op in case["ops"].as_array().expect("ops") {
            let res = run_op(&g, op);
            let got_result: Value = match &res {
                Ok(v) => v.clone(),
                Err(_) => Value::Null,
            };
            let got_err = res.as_ref().err().map(|e| e.0.clone());
            assert_eq!(
                &got_result,
                &op["result"],
                "result drift: case {gname} op {}",
                op["op"]
            );
            match &op["error"] {
                Value::Null => assert!(
                    got_err.is_none(),
                    "unexpected error in case {gname} op {}: {got_err:?}",
                    op["op"]
                ),
                want => assert_eq!(
                    got_err.as_deref(),
                    want.as_str(),
                    "error drift in case {gname} op {}",
                    op["op"]
                ),
            }
        }
    }
}