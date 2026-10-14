//! Differential: Rust VM vs Python 04_vm on fuzz_corpus.json (valid programs) and
//! fuzz_tamper_corpus.json (flipped-byte bytecode: validate faults, traps, step limit).
use pq::vm::{Machine, RunState};
use pq::*;
use serde_json::Value;

fn load(path: &str) -> Value {
    serde_json::from_str(&std::fs::read_to_string(path).unwrap_or_else(|e| panic!("{path}: {e}"))).unwrap()
}
fn consts(v: &Value) -> Vec<Const> {
    v.as_array()
        .unwrap()
        .iter()
        .map(|c| match c {
            Value::String(s) => Const::Str(s.clone()),
            Value::Number(n) => Const::Int(n.as_i64().unwrap()),
            _ => panic!("const type"),
        })
        .collect()
}
fn expect(case: &str, s: &RunState, e: &Value) {
    assert_eq!(s.fault.as_deref(), e["fault"].as_str(), "{case}: fault");
    assert_eq!(s.status.as_str(), e["status"].as_str().unwrap(), "{case}: status");
    assert_eq!(s.steps, e["steps"].as_u64().unwrap(), "{case}: steps");
    assert_eq!(s.pending_import.as_deref(), e["pending_import"].as_str(), "{case}: pending_import");
    let outs: Vec<Value> = s.outs.iter().map(|v| v.to_json()).collect();
    assert_eq!(Value::Array(outs), e["outs"], "{case}: outs");
    let regs: Vec<Value> = s.regs.iter().map(|v| v.to_json()).collect();
    assert_eq!(Value::Array(regs), e["regs"], "{case}: regs");
}

#[test]
fn vm_matches_python_on_fuzz_corpus() {
    let c = load("../../rust_plan/fuzz_corpus.json");
    let arr = c.as_array().unwrap();
    assert!(arr.len() >= 200);
    for (i, e) in arr.iter().enumerate() {
        let p = assemble(e["asm"].as_str().unwrap(), &format!("fz{i}"), e["nlocals"].as_u64().unwrap() as u8, &consts(&e["const_extra"])).unwrap();
        let s = Machine::new(&p, 500).run();
        expect(&format!("case {i}\n{}", e["asm"]), &s, e);
    }
}

#[test]
fn vm_matches_python_on_tampered_bytecode() {
    let c = load("../../rust_plan/fuzz_tamper_corpus.json");
    let arr = c.as_array().unwrap();
    assert!(arr.len() >= 100);
    for (i, e) in arr.iter().enumerate() {
        let hex = e["code_hex"].as_str().unwrap();
        let code: Vec<u8> = (0..hex.len() / 2).map(|k| u8::from_str_radix(&hex[2 * k..2 * k + 2], 16).unwrap()).collect();
        let p = Program { name: format!("t{i}"), nlocals: e["nlocals"].as_u64().unwrap() as u8, pool: consts(&e["pool"]), code };
        let s = Machine::new(&p, 500).run();
        expect(&format!("tamper {i} code={hex}"), &s, e);
    }
}

#[test]
fn vm_midinstruction_jumps_match_python() {
    // hand-built: validate-clean programs that jump into operand bytes (Python traps, never wraps)
    let c = load("../../rust_plan/vm_edge_corpus.json");
    for (i, e) in c.as_array().unwrap().iter().enumerate() {
        let hex = e["code_hex"].as_str().unwrap();
        let code: Vec<u8> = (0..hex.len() / 2).map(|k| u8::from_str_radix(&hex[2 * k..2 * k + 2], 16).unwrap()).collect();
        let p = Program { name: format!("e{i}"), nlocals: e["nlocals"].as_u64().unwrap() as u8, pool: consts(&e["pool"]), code };
        expect(&format!("edge {i} {hex}"), &Machine::new(&p, 500).run(), e);
    }
}
