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
