use pq::karaka::*;

#[test]
fn selftest_mirror() {
    let mut t = KarakaTable::new();
    t.bind("AGT", 0).unwrap().bind("PAT", 1).unwrap().bind("KRN", 2).unwrap();
    assert!(t.get("agt") == Some(0) && t.require("PAT") == Ok(1));
    assert!(t.bind("AGT", 9).is_err()); // rebind refused
    assert!(t.bind("BOGUS", 3).is_err());
    assert_eq!(t.to_json(), "{\"AGT\": 0, \"KRN\": 2, \"PAT\": 1}");
    assert_eq!(KarakaTable::from_json(&t.to_json()).unwrap(), t);
    let m = parse_arguments(&["alice", "bob", "wrench"]).unwrap();
    assert_eq!(m.len(), 3);
    assert_eq!((m["AGT"], m["PAT"], m["KRN"]), ("alice", "bob", "wrench"));
    assert!(parse_arguments(&["a"; 7]).is_err());
    let ov = KarakaTable::from_pairs(&[("DST", 5)]).unwrap();
    let mg = merge_tables(&t, &ov, Some(&["AGT"])).unwrap();
    assert!(mg.get("DST") == Some(5) && mg.get("AGT") == Some(0));
    let clash = KarakaTable::from_pairs(&[("AGT", 9)]).unwrap();
    assert_eq!(merge_tables(&t, &clash, Some(&["AGT"])), Err(KarakaError("frozen role refuse override: AGT".into())));
    assert!(merge_tables(&t, &KarakaTable::from_pairs(&[("AGT", 3)]).unwrap(), None).is_err());
}

#[test]
fn error_text_and_ranges() {
    assert_eq!(KarakaTable::from_pairs(&[("BOGUS", 1)]), Err(KarakaError("unknown role 'BOGUS'".into())));
    assert!(KarakaTable::from_pairs(&[("AGT", 256)]).is_err());
    assert!(KarakaTable::from_pairs(&[("AGT", -1)]).is_err());
    assert!(KarakaTable::from_pairs(&[("AGT", 1), ("agt", 2)]).is_err()); // duplicate after upper()
    assert_eq!(KarakaTable::new().require("SRC"), Err(KarakaError("required role missing: SRC".into())));
    assert_eq!(KarakaTable::from_json("{\"rcp\": 4}").unwrap().roles(), vec!["RCP".to_string()]);
}
#[test]
fn wire_lane_roundtrip() {
    use serde_json::json;
    // from_pairs via wire (order preserved through arrays)
    let resp = pq::karaka::karaka_op(&json!({
        "op": "from_pairs",
        "pairs": [["AGT", 0], ["PAT", 1], ["KRN", 2]]
    })).unwrap();
    assert_eq!(resp["ok"], json!(true));
    assert_eq!(resp["table_pairs"].as_array().unwrap().len(), 3);
    assert_eq!(resp["table_pairs"][0][0], json!("AGT"));
    assert_eq!(resp["table_pairs"][0][1], json!(0));
    // bind via wire (true->1 through int() parity)
    let resp = pq::karaka::karaka_op(&json!({
        "op": "bind",
        "table_pairs": resp["table_pairs"],
        "role": "DST",
        "slot": true
    })).unwrap();
    let pairs = resp["table_pairs"].as_array().unwrap();
    assert_eq!(pairs.len(), 4);
    assert_eq!(pairs[1][0], json!("DST")); // BTreeMap order AGT<DST<KRN<PAT
    assert_eq!(pairs[1][1], json!(1)); // int(True) == 1
    assert_eq!(pairs[3][0], json!("PAT"));
    // get hit + miss
    let resp = pq::karaka::karaka_op(&json!({
        "op": "get", "table_pairs": pairs, "role": "agt"
    })).unwrap();
    assert_eq!(resp["found"], json!(true));
    assert_eq!(resp["slot"], json!(0));
    let resp = pq::karaka::karaka_op(&json!({
        "op": "get", "table_pairs": pairs, "role": "RCP"
    })).unwrap();
    assert_eq!(resp["found"], json!(false));
    assert_eq!(resp["slot"], json!(null));
    // require hit
    let resp = pq::karaka::karaka_op(&json!({
        "op": "require", "table_pairs": pairs, "role": "pat"
    })).unwrap();
    assert_eq!(resp["slot"], json!(1));
    // require miss -> KarakaError with the Python's exact %s text
    assert_eq!(
        pq::karaka::karaka_op(&json!({
            "op": "require", "table_pairs": pairs, "role": "SRC"
        })),
        Err(pq::karaka::KarakaError(
            "required role missing: SRC".into()
        ))
    );
    // roles
    let resp = pq::karaka::karaka_op(&json!({
        "op": "roles", "table_pairs": pairs
    })).unwrap();
    assert_eq!(resp["roles"], json!(["AGT", "DST", "KRN", "PAT"]));
    // to_json byte-exact vs json.dumps(sort_keys=True)
    let resp = pq::karaka::karaka_op(&json!({
        "op": "to_json", "table_pairs": pairs
    })).unwrap();
    assert_eq!(
        resp["table_json"],
        json!("{\"AGT\": 0, \"DST\": 1, \"KRN\": 2, \"PAT\": 1}")
    );
    // parse_arguments: values pass through VERBATIM as wire values
    let resp = pq::karaka::karaka_op(&json!({
        "op": "parse_arguments",
        "args": [{"t": "s", "v": "alice"}, {"t": "i", "v": 7}]
    })).unwrap();
    let got = resp["pairs"].as_array().unwrap();
    assert_eq!(got[0][0], json!("AGT"));
    assert_eq!(got[0][1], json!({"t": "s", "v": "alice"}));
    assert_eq!(got[1][0], json!("PAT"));
    assert_eq!(got[1][1], json!({"t": "i", "v": 7}));
    // arity fault carries the Python's exact %d>%d text
    assert_eq!(
        pq::karaka::karaka_op(&json!({
            "op": "parse_arguments",
            "args": [0, 1, 2, 3, 4, 5, 6]
        })),
        Err(pq::karaka::KarakaError("too many args: 7 > 6".into()))
    );
    // merge_tables: frozen conflict (exact %s text), plain merge OK,
    // re-bind conflict via bind()'s frozen message through the merge path
    let base = json!({"op": "from_pairs", "pairs": [["AGT", 0], ["PAT", 1], ["KRN", 2]]});
    let base_pairs = pq::karaka::karaka_op(&base).unwrap()["table_pairs"].clone();
    assert_eq!(
        pq::karaka::karaka_op(&json!({
            "op": "merge_tables",
            "base_pairs": base_pairs,
            "overrides_pairs": [["AGT", 9]],
            "frozen": ["AGT"]
        })),
        Err(pq::karaka::KarakaError(
            "frozen role refuse override: AGT".into()
        ))
    );
    assert_eq!(
        pq::karaka::karaka_op(&json!({
            "op": "merge_tables",
            "base_pairs": base_pairs,
            "overrides_pairs": [["AGT", 3]],
            "frozen": null
        })),
        Err(pq::karaka::KarakaError(
            "re-bind refused (frozen): AGT".into()
        ))
    );
    let resp = pq::karaka::karaka_op(&json!({
        "op": "merge_tables",
        "base_pairs": base_pairs,
        "overrides_pairs": [["DST", 5]],
        "frozen": ["AGT"]
    })).unwrap();
    let merged = resp["table_pairs"].as_array().unwrap();
    assert_eq!(merged.len(), 4);
    // BTreeMap order: AGT(0) < DST(5) < KRN(2) < PAT(1)
    assert_eq!(merged[1][0], json!("DST"));
    assert_eq!(merged[1][1], json!(5));
    assert_eq!(merged[3][0], json!("PAT"));
    assert_eq!(merged[3][1], json!(1));
    // wire faults: unknown op + bad slot type
    assert!(pq::karaka::karaka_op(&json!({"op": "nope"})).is_err());
    assert!(pq::karaka::karaka_op(&json!({
        "op": "from_pairs", "pairs": [["AGT", "x"]]
    })).is_err());
}
