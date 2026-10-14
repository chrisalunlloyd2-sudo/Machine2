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
