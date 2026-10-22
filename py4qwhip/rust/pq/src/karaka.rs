//! pq::karaka -- py4qwhip block 02 (role -> slot table), Rust port. Reference: ../../blocks/02_karaka.py
//! Error text mirrors Python (%r of a str is rendered with single quotes).
use serde_json::Value;
use std::collections::BTreeMap;

pub const ROLES: [&str; 6] = ["AGT", "PAT", "KRN", "DST", "SRC", "RCP"];

#[derive(Debug, PartialEq)]
pub struct KarakaError(pub String);
fn err<T>(m: String) -> Result<T, KarakaError> {
    Err(KarakaError(m))
}

fn is_role(r: &str) -> bool {
    ROLES.contains(&r)
}

#[derive(Debug, Clone, PartialEq, Default)]
pub struct KarakaTable {
    m: BTreeMap<String, u8>,
}

impl KarakaTable {
    pub fn new() -> Self {
        Self::default()
    }

    /// Mirrors __init__(binding): iterates in the given order.
    pub fn from_pairs(pairs: &[(&str, i64)]) -> Result<Self, KarakaError> {
        let mut m = BTreeMap::new();
        for (role, slot) in pairs {
            let r = role.to_uppercase();
            if !is_role(&r) {
                return err(format!("unknown role '{role}'"));
            }
            if !(0..=255).contains(slot) {
                return err(format!("slot out of range: {slot}"));
            }
            if m.contains_key(&r) {
                return err(format!("duplicate role '{r}'"));
            }
            m.insert(r, *slot as u8);
        }
        Ok(KarakaTable { m })
    }

    pub fn get(&self, role: &str) -> Option<u8> {
        self.m.get(&role.to_uppercase()).copied()
    }

    pub fn require(&self, role: &str) -> Result<u8, KarakaError> {
        self.get(role).ok_or_else(|| KarakaError(format!("required role missing: {role}")))
    }

    pub fn bind(&mut self, role: &str, slot: i64) -> Result<&mut Self, KarakaError> {
        let r = role.to_uppercase();
        if !is_role(&r) {
            return err(format!("unknown role '{role}'"));
        }
        if !(0..=255).contains(&slot) {
            return err(format!("slot out of range: {slot}"));
        }
        if self.m.contains_key(&r) {
            return err(format!("re-bind refused (frozen): {r}"));
        }
        self.m.insert(r, slot as u8);
        Ok(self)
    }

    pub fn roles(&self) -> Vec<String> {
        self.m.keys().cloned().collect()
    }

    /// json.dumps(m, sort_keys=True): {"AGT": 0, "PAT": 1}
    pub fn to_json(&self) -> String {
        let parts: Vec<String> = self.m.iter().map(|(k, v)| format!("\"{k}\": {v}")).collect();
        format!("{{{}}}", parts.join(", "))
    }

    pub fn from_json(s: &str) -> Result<Self, KarakaError> {
        let v: Value = serde_json::from_str(s).map_err(|e| KarakaError(format!("json: {e}")))?;
        let obj = v.as_object().ok_or_else(|| KarakaError("json: not an object".into()))?;
        let mut pairs: Vec<(String, i64)> = Vec::new();
        for (k, val) in obj {
            let n = val.as_i64().ok_or_else(|| KarakaError(format!("json: slot for {k} is not an int")))?;
            pairs.push((k.clone(), n));
        }
        let refs: Vec<(&str, i64)> = pairs.iter().map(|(k, n)| (k.as_str(), *n)).collect();
        Self::from_pairs(&refs)
    }
}

impl std::fmt::Display for KarakaTable {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "KarakaTable({})", self.to_json())
    }
}

/// Positional args -> roles in ROLES order. More than 6 args is an error; absent roles stay absent.
pub fn parse_arguments<T: Clone>(args: &[T]) -> Result<BTreeMap<&'static str, T>, KarakaError> {
    if args.len() > ROLES.len() {
        return err(format!("too many args: {} > {}", args.len(), ROLES.len()));
    }
    Ok(ROLES.iter().zip(args.iter()).map(|(r, v)| (*r, v.clone())).collect())
}

/// Layer overrides over base. A role already in base always refuses (bind refuses re-bind),
/// frozen or not -- the frozen branch only changes the message. Faithful to the Python.
pub fn merge_tables(base: &KarakaTable, overrides: &KarakaTable, frozen_roles: Option<&[&str]>) -> Result<KarakaTable, KarakaError> {
    let mut merged = base.clone();
    for role in overrides.roles() {
        if let Some(fr) = frozen_roles {
            if fr.contains(&role.as_str()) && merged.get(&role).is_some() {
                return err(format!("frozen role refuse override: {role}"));
            }
        }
        let slot = overrides.require(&role)?;
        merged.bind(&role, slot as i64)?;
    }
    Ok(merged)
}
// ---- pq4 wire lane (milestone 6): block 02 ops behind pq_karaka_json (C
// ABI export in lib.rs mod c_abi). Stateless by design (D250): every
// request carries the table snapshot as [role, slot] pairs (JSON arrays,
// so insertion order survives; JSON objects would sort in serde's map),
// and responses carry the resulting snapshot the same way. No ambient
// state. Python side: ANY ok:false response is treated as dll-refused and
// falls through to the verbatim pure-Python body, so native KarakaError
// text (D168) and int() slot semantics are preserved even though these
// ops mirror the same messages byte-for-byte (unit-tested in
// tests/karaka.rs against the Python's exact %r/%s renderings).

/// Wire slot value -> i64. bool maps through int() (True->1) exactly as
/// the Python ctor/bind does; i64 numbers pass; anything else is a wire
/// fault (the wrapper never sends it -- fall-through covers it anyway).
fn parse_wire_slot(v: &serde_json::Value) -> Result<i64, KarakaError> {
    match v {
        serde_json::Value::Number(n) => match n.as_i64() {
            Some(i) => Ok(i),
            None => err("wire: slot number out of range".into()),
        },
        serde_json::Value::Bool(b) => Ok(if *b { 1 } else { 0 }),
        _ => err("wire: slot must be int or bool".into()),
    }
}

/// [role, slot] wire pairs -> KarakaTable, in the GIVEN order (faithful to
/// KarakaTable.__init__, which iterates dict(binding).items() in that
/// order; the Python wrapper sends its snapshot as arrays precisely so
/// this order survives JSON).
pub fn table_from_wire(pairs: &[serde_json::Value]) -> Result<KarakaTable, KarakaError> {
    let mut refs: Vec<(&str, i64)> = Vec::new();
    for p in pairs {
        let kv = p.as_array()
            .ok_or_else(|| KarakaError("wire: pair must be [role, slot]".into()))?;
        if kv.len() != 2 {
            return err("wire: pair must be [role, slot]".into());
        }
        let role = kv[0].as_str()
            .ok_or_else(|| KarakaError("wire: role must be a string".into()))?;
        let slot = parse_wire_slot(&kv[1])?;
        refs.push((role, slot));
    }
    KarakaTable::from_pairs(&refs)
}

/// KarakaTable -> [role, slot] wire pairs (BTreeMap order = sorted, which
/// is exactly the order roles()/to_json expose).
pub fn table_to_wire(t: &KarakaTable) -> serde_json::Value {
    serde_json::Value::Array(
        t.roles()
            .iter()
            .map(|r| serde_json::json!([r, t.get(r).unwrap_or(0)]))
            .collect(),
    )
}

fn ok_table(t: &KarakaTable) -> serde_json::Value {
    serde_json::json!({"ok": true, "table_pairs": table_to_wire(t)})
}

fn wire_req_val<'a>(
    req: &'a serde_json::Value,
    key: &str,
) -> Result<&'a serde_json::Value, KarakaError> {
    req.get(key).ok_or_else(|| KarakaError(format!("wire: missing '{}'", key)))
}

fn wire_req_str<'a>(req: &'a serde_json::Value, key: &str) -> Result<&'a str, KarakaError> {
    wire_req_val(req, key)?
        .as_str()
        .ok_or_else(|| KarakaError(format!("wire: '{}' must be a string", key)))
}

fn wire_req_pairs<'a>(
    req: &'a serde_json::Value,
    key: &str,
) -> Result<&'a Vec<serde_json::Value>, KarakaError> {
    wire_req_val(req, key)?
        .as_array()
        .ok_or_else(|| KarakaError(format!("wire: '{}' must be an array", key)))
}

/// The block-02 op dispatch (D247): from_pairs (serves __init__ AND
/// from_json -- the JSON decode itself stays Python-side so a raw
/// JSONDecodeError propagates un-wrapped), bind, get, require, roles,
/// to_json, parse_arguments, merge_tables. Success payloads carry
/// "ok": true plus op-specific fields; any domain fault comes back as
/// KarakaError and is wrapped at the export boundary as
/// {"ok": false, "error": {"kind": "KarakaError", ...}} (D251).
pub fn karaka_op(req: &serde_json::Value) -> Result<serde_json::Value, KarakaError> {
    let op = req
        .get("op")
        .and_then(serde_json::Value::as_str)
        .ok_or_else(|| KarakaError("wire: missing 'op'".into()))?;
    match op {
        "from_pairs" => {
            let t = table_from_wire(wire_req_pairs(req, "pairs")?)?;
            Ok(ok_table(&t))
        }
        "bind" => {
            let mut t = table_from_wire(wire_req_pairs(req, "table_pairs")?)?;
            let role = wire_req_str(req, "role")?;
            let slot = parse_wire_slot(wire_req_val(req, "slot")?)?;
            t.bind(role, slot)?;
            Ok(ok_table(&t))
        }
        "get" => {
            let t = table_from_wire(wire_req_pairs(req, "table_pairs")?)?;
            let role = wire_req_str(req, "role")?;
            Ok(match t.get(role) {
                Some(slot) => serde_json::json!({"ok": true, "found": true, "slot": slot}),
                None => serde_json::json!({"ok": true, "found": false, "slot": null}),
            })
        }
        "require" => {
            let t = table_from_wire(wire_req_pairs(req, "table_pairs")?)?;
            let role = wire_req_str(req, "role")?;
            let slot = t.require(role)?;
            Ok(serde_json::json!({"ok": true, "slot": slot}))
        }
        "roles" => {
            let t = table_from_wire(wire_req_pairs(req, "table_pairs")?)?;
            Ok(serde_json::json!({"ok": true, "roles": t.roles()}))
        }
        "to_json" => {
            let t = table_from_wire(wire_req_pairs(req, "table_pairs")?)?;
            Ok(serde_json::json!({"ok": true, "table_json": t.to_json()}))
        }
        "parse_arguments" => {
            let args = req
                .get("args")
                .and_then(serde_json::Value::as_array)
                .ok_or_else(|| KarakaError("wire: missing 'args'".into()))?;
            if args.len() > ROLES.len() {
                return err(format!("too many args: {} > {}", args.len(), ROLES.len()));
            }
            let pairs: Vec<serde_json::Value> = ROLES
                .iter()
                .zip(args.iter())
                .map(|(r, v)| serde_json::json!([*r, v]))
                .collect();
            Ok(serde_json::json!({"ok": true, "pairs": pairs}))
        }
        "merge_tables" => {
            let base = table_from_wire(wire_req_pairs(req, "base_pairs")?)?;
            let over = table_from_wire(wire_req_pairs(req, "overrides_pairs")?)?;
            let frozen: Option<Vec<&str>> = match req.get("frozen") {
                None | Some(serde_json::Value::Null) => None,
                Some(serde_json::Value::Array(a)) => {
                    let mut v = Vec::new();
                    for f in a {
                        v.push(f.as_str().ok_or_else(|| {
                            KarakaError("wire: frozen roles must be strings".into())
                        })?);
                    }
                    Some(v)
                }
                Some(_) => return err("wire: 'frozen' must be an array or null".into()),
            };
            let m = merge_tables(&base, &over, frozen.as_deref())?;
            Ok(ok_table(&m))
        }
        _ => err(format!("wire: unknown op '{}'", op)),
    }
}
