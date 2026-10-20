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

const GV: &str = "../../rust_plan/golden_vectors.json";
const FZ: &str = "../../rust_plan/fuzz_corpus.json";

#[test]
fn skeleton_hashes_match_python() {
    let g = load(GV);
    let sk = g["skeletons"].as_array().unwrap();
    assert!(sk.len() >= 45);
    for s in sk {
        let m = s["module"].as_str().unwrap();
        let asm = format!("load_const r3, 'SKELETON:{m}'\nout r3\nload_const r0, 0\nhalt\n");
        let p = assemble(&asm, &format!("skel:{m}"), 8, &[Const::Str(format!("SKELETON:{m}"))]).unwrap();
        assert_eq!(content_hash(&p).unwrap(), s["content_hash"].as_str().unwrap(), "module {m}");
    }
}

#[test]
fn vm_program_hashes_match_python() {
    let g = load(GV);
    for v in g["vm"].as_array().unwrap() {
        let p = assemble(v["asm"].as_str().unwrap(), v["name"].as_str().unwrap(), 4, &consts(&v["const_extra"])).unwrap();
        assert_eq!(content_hash(&p).unwrap(), v["content_hash"].as_str().unwrap(), "{}", v["name"]);
    }
}

#[test]
fn fuzz_corpus_hashes_match_python() {
    let c = load(FZ);
    let arr = c.as_array().unwrap();
    assert!(arr.len() >= 200);
    for (i, e) in arr.iter().enumerate() {
        let p = assemble(
            e["asm"].as_str().unwrap(),
            &format!("fz{i}"),
            e["nlocals"].as_u64().unwrap() as u8,
            &consts(&e["const_extra"]),
        )
        .unwrap_or_else(|er| panic!("case {i}: {er:?}\n{}", e["asm"]));
        assert_eq!(content_hash(&p).unwrap(), e["content_hash"].as_str().unwrap(), "case {i}\n{}", e["asm"]);
    }
}
