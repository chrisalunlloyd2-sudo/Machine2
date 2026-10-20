//! envelope conformance -- block 06 port vs the Python reference (blocks/06_envelope.py).
//! Vectors: ../../rust_plan/envelope_golden.json (generated from PY311 reference 2026-10-16).
//! Same gate as steps 1-3: byte-for-byte blob equality + exact error strings.
use pq::envelope::{decode_source, encode_source, inspect, HEADER_ENDCAP_RESERVED};
use serde_json::Value;

fn load(path: &str) -> Value {
    serde_json::from_str(&std::fs::read_to_string(path).unwrap_or_else(|e| panic!("{path}: {e}"))).unwrap()
}

const EG: &str = "../../rust_plan/envelope_golden.json";

fn hex(s: &str) -> Vec<u8> {
    (0..s.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(&s[i..i + 2], 16).unwrap())
        .collect()
}

fn to_hex(b: &[u8]) -> String {
    b.iter().map(|x| format!("{x:02x}")).collect()
}

#[test]
fn envelope_blob_bytes_match_python() {
    let g = load(EG);
    for case in g["ok"].as_array().unwrap() {
        let text = case["text"].as_str().unwrap();
        let ec_hex = case["endcap"].as_str().unwrap();
        let mut ec = [0u8; 8];
        ec.copy_from_slice(&hex(ec_hex));
        let blob = encode_source(text, &ec).unwrap();
        assert_eq!(to_hex(&blob), case["blob"].as_str().unwrap(), "case {}", case["name"]);
        let (kind, endcap, body) = inspect(&blob).unwrap();
        assert_eq!(kind, 0);
        assert_eq!(&to_hex(&endcap), ec_hex);
        assert_eq!(body, text.as_bytes());
        assert_eq!(decode_source(&blob).unwrap(), text);
    }
}

#[test]
fn envelope_corrupt_errors_match_python() {
    let g = load(EG);
    for case in g["corrupt"].as_array().unwrap() {
        let blob = hex(case["blob"].as_str().unwrap());
        let want_inspect = case["inspect_error"].as_str();
        let want_decode = case["decode_error"].as_str();
        let got_inspect = inspect(&blob).err().map(|e| e.0);
        let got_decode = decode_source(&blob).err().map(|e| e.0);
        assert_eq!(got_inspect.as_deref(), want_inspect, "case {} (inspect)", case["name"]);
        assert_eq!(got_decode.as_deref(), want_decode, "case {} (decode)", case["name"]);
    }
}

#[test]
fn envelope_reserved_endcap_and_tamper() {
    // reserved endcap 00000000 + the two design pins from the Python selftest
    let blob = encode_source("print(\"hi\")\n", &HEADER_ENDCAP_RESERVED).unwrap();
    let (_, endcap, _) = inspect(&blob).unwrap();
    assert_eq!(endcap, HEADER_ENDCAP_RESERVED);
    let mut digest_flip = blob.clone();
    digest_flip[26] ^= 1;
    assert!(inspect(&digest_flip).unwrap_err().0.contains("checksum mismatch"));
    let mut endcap_flip = blob.clone();
    endcap_flip[7] ^= 1;
    let (_, flipped, _) = inspect(&endcap_flip).unwrap();
    assert_ne!(flipped, HEADER_ENDCAP_RESERVED);
}