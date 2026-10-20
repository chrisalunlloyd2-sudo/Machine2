//! pq -- py4qwhip block 01 (byte-space), Rust port. Reference: ../../blocks/01_bytespace.py
//! Deterministic, no I/O. Must reproduce the Python content_hash byte-for-byte (golden vectors).
use sha2::{Digest, Sha256};
use std::collections::HashMap;

pub mod envelope;
pub mod graph;
pub mod karaka;
pub mod vm;

pub const MAGIC: &[u8] = b"PY4QW01";
pub const VERSION: u8 = 1;
const MAX_POOL: usize = 65535;
pub const MAX_LOCALS: usize = 255;

#[derive(Debug, Clone)]
pub enum Const {
    Int(i64),
    Bool(bool),
    Str(String),
    Bytes(Vec<u8>),
    /// Canonical decimal string (digits, optional leading '-', optional '.N' fraction);
    /// holds values outside i64 range. Numeric-equal to Int under PartialEq.
    Bigint(String),
    Float(f64),
}

impl PartialEq for Const {
    fn eq(&self, other: &Self) -> bool {
        match (self, other) {
            (Const::Int(a), Const::Int(b)) => a == b,
            // Bool is type-distinct from Int (Python: True != 1 in the b01 pool dedupe).
            (Const::Bool(a), Const::Bool(b)) => a == b,
            (Const::Str(a), Const::Str(b)) => a == b,
            (Const::Bytes(a), Const::Bytes(b)) => a == b,
            (Const::Float(a), Const::Float(b)) => a == b,
            // Int <-> Bigint merge numerically (Python: 10**30 == its decimal twin).
            (Const::Bigint(s), Const::Int(i)) | (Const::Int(i), Const::Bigint(s)) => {
                big_decimal_eq(s, *i)
            }
            (Const::Bigint(a), Const::Bigint(b)) => a == b,
            // Distinct types never merge (Bool vs Int, Str vs Bytes, ...).
            _ => false,
        }
    }
}

/// Decimal-string (canonical, from py_int_parse) == i64, no panics.
fn big_decimal_eq(s: &str, i: i64) -> bool {
    match s.parse::<i64>() {
        Ok(v) => v == i,
        Err(_) => false, // outside i64: can never equal an Int
    }
}

#[derive(Debug, Clone)]
pub struct Program {
    pub name: String,
    pub nlocals: u8,
    pub pool: Vec<Const>,
    pub code: Vec<u8>,
}

#[derive(Debug, PartialEq)]
pub struct PqError(pub String);
fn err<T>(m: impl Into<String>) -> Result<T, PqError> {
    Err(PqError(m.into()))
}


pub fn py_int_parse(s: &str) -> Result<Const, PqError> {
    let b = s.as_bytes();
    let mut i = 0usize;
    if i < b.len() && (b[i] == b'+' || b[i] == b'-') {
        i += 1;
    }
    let ds = i; // digits start
    while i < b.len() {
        let c = b[i];
        if c.is_ascii_digit() {
            i += 1;
        } else if c == b'_'
            && i > ds
            && b[i - 1].is_ascii_digit()
            && i + 1 < b.len()
            && b[i + 1].is_ascii_digit()
        {
            i += 1;
        } else {
            break;
        }
    }
    if i != b.len() || i == ds {
        return err(format!(
            "invalid literal for int() with base 10: {}",
            py_repr(s)
        ));
    }
    let digits: String = s[ds..i].chars().filter(|c| *c != '_').collect();
    let neg = ds == 1 && b[0] == b'-';
    let mag = digits.trim_start_matches('0');
    let canon = if mag.is_empty() { "0" } else { mag };
    if canon == "0" {
        return Ok(Const::Int(0));
    }
    if neg {
        let fits = canon.len() < 19
            || (canon.len() == 19 && canon.as_bytes() <= b"9223372036854775808".as_slice());
        if fits {
            if let Ok(v) = format!("-{}", canon).parse::<i64>() {
                return Ok(Const::Int(v));
            }
        }
        return Ok(Const::Bigint(format!("-{}", canon)));
    }
    let fits = canon.len() < 19
        || (canon.len() == 19 && canon.as_bytes() <= b"9223372036854775807".as_slice());
    if fits {
        if let Ok(v) = canon.parse::<i64>() {
            return Ok(Const::Int(v));
        }
    }
    Ok(Const::Bigint(canon.to_string()))
}

/// Python repr() of a list of str tokens: ['a', "it's"]
pub fn py_repr_list(v: &[String]) -> String {
    let mut o = String::from("[");
    for (i, s) in v.iter().enumerate() {
        if i > 0 { o.push_str(", "); }
        o.push_str(&py_repr(s));
    }
    o.push(']');
    o
}

/// Python int(token): optional +/-, underscores BETWEEN digits allowed,
/// arbitrary precision (out-of-i64 -> Const::Bigint canonical decimal).
/// Python repr() of a str, narrow form: smart quote choice (double quotes only
/// when the string holds a `'` and no `"`), backslash/control escapes. Covers
/// the repr forms block 01 embeds in error text (copied verbatim from graph.rs).
fn py_repr(s: &str) -> String {
    let quote = if s.contains('\'') && !s.contains('"') {
        '"'
    } else {
        '\''
    };
    let mut o = String::new();
    o.push(quote);
    for c in s.chars() {
        match c {
            '\\' => o.push_str("\\\\"),
            '\n' => o.push_str("\\n"),
            '\r' => o.push_str("\\r"),
            '\t' => o.push_str("\\t"),
            _ if c == quote => {
                o.push('\\');
                o.push(c);
            }
            c if (c as u32) < 0x20 => o.push_str(&format!("\\x{:02x}", c as u32)),
            c if (c as u32) == 0x7f => o.push_str("\\x7f"),
            _ => o.push(c),
        }
    }
    o.push(quote);
    o
}

#[derive(Clone, Copy, PartialEq)]
enum K {
    R,
    C,
    J,
}

const NAMES: [&str; 18] = [
    "NOP", "LOAD_CONST", "LOAD_LOCAL", "STORE_LOCAL", "ADD", "SUB", "MUL", "EQ", "LT", "JUMP", "JIF", "CALL", "RET",
    "IMPORT", "HALT", "STRCAT", "LEN", "OUT",
];

fn kinds_of(opc: u8) -> Option<&'static [K]> {
    use K::*;
    Some(match opc {
        0x00 => &[],
        0x01 => &[R, C],
        0x02 => &[R, R],
        0x03 => &[R, R],
        0x04..=0x08 => &[R, R, R],
        0x09 => &[J],
        0x0A => &[R, J],
        0x0B => &[R, R, R],
        0x0C => &[R],
        0x0D => &[R, C],
        0x0E => &[],
        0x0F => &[R, R, R],
        0x10 => &[R, R],
        0x11 => &[R],
        _ => return None,
    })
}

fn op_by_name(n: &str) -> Option<(u8, &'static [K])> {
    let i = NAMES.iter().position(|x| *x == n)? as u8;
    kinds_of(i).map(|k| (i, k))
}

fn op_size(kinds: &[K]) -> usize {
    1 + kinds.iter().map(|k| if *k == K::R { 1 } else { 2 }).sum::<usize>()
}

/// Mirrors _parse_line: strip '#' comment; label = single token ending ':' with no ','.
enum Line {
    Skip,
    Label(String),
    Instr(String, Vec<String>),
}

fn parse_line(raw: &str) -> Line {
    let s = raw.splitn(2, '#').next().unwrap_or("").trim();
    if s.is_empty() {
        return Line::Skip;
    }
    if s.ends_with(':') && !s.contains(',') && s.split_whitespace().count() == 1 {
        return Line::Label(s[..s.len() - 1].to_string());
    }
    let parts: Vec<String> = s.replace(',', " ").split_whitespace().map(String::from).collect();
    Line::Instr(parts[0].to_uppercase(), parts[1..].to_vec())
}

fn is_py_digits(a: &str) -> bool {
    let t = a.trim_start_matches('-');
    !t.is_empty() && t.chars().all(|c| c.is_ascii_digit())
}

pub fn assemble(text: &str, name: &str, nlocals: u8, const_extra: &[Const]) -> Result<Program, PqError> {
    let mut labels: HashMap<String, usize> = HashMap::new();
    let mut ins: Vec<(String, Vec<String>)> = Vec::new();
    for raw in text.lines() {
        match parse_line(raw) {
            Line::Skip => {}
            Line::Label(l) => {
                if labels.contains_key(&l) {
                    return err(format!("duplicate label '{}'", l));
                }
                labels.insert(l, ins.len());
            }
            Line::Instr(o, a) => ins.push((o, a)),
        }
    }
    if ins.is_empty() && labels.is_empty() {
        return err("empty program");
    }
    let mut ins_bytes = Vec::new();
    let mut off = 0usize;
    for (o, _) in &ins {
        let (_, kinds) = match op_by_name(o) {
            Some(x) => x,
            None => return err(format!("unknown op '{}'", o)),
        };
        ins_bytes.push(off);
        off += op_size(kinds);
    }
    let mut label_byte: HashMap<&str, usize> = HashMap::new();
    for (l, idx) in &labels {
        label_byte.insert(l.as_str(), if *idx >= ins.len() { off } else { ins_bytes[*idx] });
    }
    let mut pool: Vec<Const> = const_extra.to_vec();
    let mut code: Vec<u8> = Vec::new();
    for (idx, (o, args)) in ins.iter().enumerate() {
        let (opc, kinds) = op_by_name(o).unwrap();
        if args.len() != kinds.len() {
            return err(format!("{o} wants {} operands, got {}", kinds.len(), py_repr_list(args)));
        }
        code.push(opc);
        let after = (ins_bytes[idx] + op_size(kinds)) as i64;
        for (k, a) in kinds.iter().zip(args.iter()) {
            match k {
                K::R => {
                    let m = if a.starts_with('r') { &a[1..] } else { a.as_str() };
                    let n = match py_int_parse(m)? {
                        Const::Int(v) => v,
                        Const::Bigint(big) => {
                            return err(format!("operand out of range: {}", big))
                        }
                        _ => unreachable!("digit parse yields int/bigint"),
                    };
                    if !(0..=(MAX_LOCALS as i64)).contains(&n) {
                        return err(format!("operand out of range: {n}"));
                    }
                    code.push(n as u8);
                }
                K::C => {
                    let mut s = a.as_str();
                    if s.len() >= 2 {
                        let b = s.as_bytes();
                        if b[0] == b[s.len() - 1] && (b[0] == b'\'' || b[0] == b'"') {
                            s = &s[1..s.len() - 1];
                        }
                    }
                    let v = if is_py_digits(s) {
                        py_int_parse(s)?
                    } else {
                        Const::Str(s.to_string())
                    };
                    if let Const::Str(t) = &v {
                        if t.starts_with('r') {
                            return err(format!("const slot got register {}", py_repr(s)));
                        }
                    }
                    let i = match pool.iter().position(|e| *e == v) {
                        Some(i) => i,
                        None => {
                            if pool.len() > MAX_POOL {
                                return err("const pool overflow");
                            }
                            pool.push(v);
                            pool.len() - 1
                        }
                    };
                    if i > MAX_POOL {
                        return err(format!("const index out of range: {}", i));
                    }
                    code.extend_from_slice(&(i as u16).to_le_bytes());
                }
                K::J => {
                    let t = match label_byte.get(a.as_str()) {
                        Some(t) => *t as i64,
                        None => return err(format!("unknown label {}", py_repr(a))),
                    };
                    let rel = t - after;
                    if !(-32768..=32767).contains(&rel) {
                        return err(format!("jump offset out of range: {}", rel));
                    }
                    code.extend_from_slice(&(rel as i16).to_le_bytes());
                }
            }
        }
    }
    let p = Program { name: name.to_string(), nlocals, pool, code };
    validate(&p)?;
    Ok(p)
}

/// Mirrors validate(): jump base = NEXT instruction; target may equal len(code).
pub fn validate(p: &Program) -> Result<(), PqError> {
    let code = &p.code;
    let mut pc = 0usize;
    while pc < code.len() {
        let opc = code[pc];
        let kinds = match kinds_of(opc) {
            Some(k) => k,
            None => return err(format!("bad opcode 0x{opc:02x} at {pc}")),
        };
        let size = op_size(kinds);
        if pc + size > code.len() {
            return err(format!("truncated instruction at {pc}"));
        }
        let mut oi = pc + 1;
        for k in kinds {
            match k {
                K::R => {
                    if code[oi] >= p.nlocals {
                        return err(format!("{}: reg/slot {} >= nlocals at {pc}", NAMES[opc as usize], code[oi]));
                    }
                    oi += 1;
                }
                K::C => {
                    if u16::from_le_bytes([code[oi], code[oi + 1]]) as usize >= p.pool.len() {
                        return err(format!("{}: const idx out of pool at {pc}", NAMES[opc as usize]));
                    }
                    oi += 2;
                }
                K::J => {
                    let rel = i16::from_le_bytes([code[oi], code[oi + 1]]) as i64;
                    let tgt = pc as i64 + size as i64 + rel;
                    if tgt < 0 || tgt > code.len() as i64 {
                        return err(format!("{}: jump target out of program at {pc}", NAMES[opc as usize]));
                    }
                    oi += 2;
                }
            }
        }
        pc += size;
    }
    Ok(())
}

/// Byte-exact canonical serialization (content address = sha256 of this).
/// Mirrors b01 canonical_bytes L108–134 failure gates: a big int pool value
/// (Const::Bigint) misses struct `<q` -> raw struct.error "argument out of
/// range"; overlong name/pool/code miss `<H`/`<I` likewise. (Internal Program
/// path: nlocals is u8 and always fits `<B`; the magic/nlocals/canonicity
/// gates belong to the dict-level C-ABI layer.)
pub fn canonical_bytes(p: &Program) -> Result<Vec<u8>, PqError> {
    if p.name.len() > 65535 {
        return err("argument out of range"); // struct <H (name byte length)
    }
    if p.pool.len() > 65535 {
        return err("argument out of range"); // struct <H (pool length)
    }
    let mut o = Vec::new();
    o.extend_from_slice(MAGIC);
    o.push(VERSION);
    o.extend_from_slice(&(p.name.len() as u16).to_le_bytes());
    o.extend_from_slice(p.name.as_bytes());
    o.push(p.nlocals);
    o.extend_from_slice(&(p.pool.len() as u16).to_le_bytes());
    for v in &p.pool {
        match v {
            Const::Int(i) => {
                o.push(0);
                o.extend_from_slice(&8u32.to_le_bytes());
                o.extend_from_slice(&i.to_le_bytes());
            }
            // Python canonical_pool_value: bool -> ("i", int(v)) FIRST.
            Const::Bool(b) => {
                let n = if *b { 1i64 } else { 0i64 };
                o.push(0);
                o.extend_from_slice(&8u32.to_le_bytes());
                o.extend_from_slice(&n.to_le_bytes());
            }
            Const::Str(s) => {
                o.push(1);
                o.extend_from_slice(&(s.len() as u32).to_le_bytes());
                o.extend_from_slice(s.as_bytes());
            }
            Const::Bytes(b) => {
                o.push(2);
                o.extend_from_slice(&(b.len() as u32).to_le_bytes());
                o.extend_from_slice(b);
            }
            Const::Float(f) => {
                o.push(3);
                o.extend_from_slice(&8u32.to_le_bytes());
                o.extend_from_slice(&f.to_bits().to_le_bytes());
            }
            // struct.pack("<q", 10**30) -> raw struct.error (probe a31).
            Const::Bigint(_) => return err("argument out of range"),
        }
    }
    o.extend_from_slice(&(p.code.len() as u32).to_le_bytes());
    o.extend_from_slice(&p.code);
    Ok(o)
}

pub fn content_hash(p: &Program) -> Result<String, PqError> {
    let bytes = canonical_bytes(p)?;
    let d = Sha256::digest(&bytes);
    Ok(d.iter().take(8).map(|b| format!("{b:02x}")).collect())
}
// ===== C-ABI exports (step 6) =====
// JSON-in/JSON-out; error channel {"ok":false,"error":{"kind","message"}}.
// Dict-level gates (magic/version/nlocals range/pool cap/type checks) stay
// Python-side in the wrapper (verbatim b01 clone); the DLL owns assemble
// text-pipeline, opcode-walk validate, canonical+sha256 only.
// validate-success parity: success reply is bare null; the wrapper maps it to Python None.

pub mod c_abi {
    use super::{Const, PqError, Program, assemble, content_hash, err, validate};
        pub const PQ_ABI_VERSION: i32 = 1;

    #[no_mangle]
    pub extern "C" fn pq_abi_version() -> i32 { PQ_ABI_VERSION }

    // Boxed-trap guard: any Rust panic in an FFI entry (unwrap on non-UTF8,
    // out-of-bounds on malformed struct slices) aborts into this hook instead
    // of unwinding across the FFI boundary. Message preserved for telemetry;
    // the caller ALWAYS receives valid JSON ({"ok":false,"error":...}).
    #[no_mangle]
    pub extern "C" fn pq_panic_hook() {
        std::panic::set_hook(Box::new(|info| {
            let m = if let Some(s) = info.payload().downcast_ref::<&str>() {
                (*s).to_string()
            } else if let Some(s) = info.payload().downcast_ref::<String>() {
                s.clone()
            } else {
                "ffi panic".to_string()
            };
            eprintln!("pq_panic_hook: {}", m);
        }));
    }

    #[no_mangle]
    pub extern "C" fn pq_free(ptr: *mut std::os::raw::c_char) {
        // Called by ctypes exactly once per pq_*_json call.
        use std::ffi::CString;
        unsafe { if !ptr.is_null() { drop(CString::from_raw(ptr)); } }
    }

    // ---- std base64 (no codebase dep churn; wire needs exact std b64+) ----
    fn b64_encode(data: &[u8]) -> String {
        const T: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
        let mut out = String::with_capacity((data.len() + 2) / 3 * 4);
        for ch in data.chunks(3) {
            let n = ((ch[0] as u32) << 16)
                | ((*ch.get(1).unwrap_or(&0) as u32) << 8)
                | (*ch.get(2).unwrap_or(&0) as u32);
            out.push(T[(n >> 18) as usize & 63] as char);
            out.push(T[(n >> 12) as usize & 63] as char);
            out.push(if ch.len() > 1 { T[(n >> 6) as usize & 63] as char } else { '=' });
            out.push(if ch.len() > 2 { T[n as usize & 63] as char } else { '=' });
        }
        out
    }

    fn b64_val(c: u8) -> Option<u32> {
        match c {
            b'A'..=b'Z' => Some((c - b'A') as u32),
            b'a'..=b'z' => Some((c - b'a' + 26) as u32),
            b'0'..=b'9' => Some((c - b'0' + 52) as u32),
            b'+' => Some(62),
            b'/' => Some(63),
            _ => None,
        }
    }

    fn b64_decode(s: &str) -> Option<Vec<u8>> {
        let b = s.as_bytes();
        if b.len() % 4 != 0 { return None; }
        let mut body_end = b.len();
        while body_end > 0 && b[body_end - 1] == b'=' { body_end -= 1; }
        if b.len() - body_end >= 3 { return None; }
        let mut out = Vec::with_capacity(b.len() / 4 * 3);
        let mut i = 0usize;
        while i < body_end {
            let take = core::cmp::min(4, body_end - i);
            if take < 2 { return None; }
            let v0 = b64_val(b[i])?;
            let v1 = b64_val(b[i + 1])?;
            let v2 = if take > 2 { b64_val(b[i + 2])? } else { 0u32 };
            let v3 = if take > 3 { b64_val(b[i + 3])? } else { 0u32 };
            let acc: u32 = (v0 << 18) | (v1 << 12) | (v2 << 6) | v3;
            out.push((acc >> 16) as u8);
            if take > 2 { out.push((acc >> 8) as u8); }
            if take > 3 { out.push(acc as u8); }
            i += take;
        }
        Some(out)
    }

    // ---- pool item codec ----
    // Python dict {"t","v"}; canonical_pool_value tag order: i before f/s/b.
    // "i" values that miss i64 cross as {"t":"B","v":"<decimal>"} (marker
    // convention) -- JSON never silently clamps a bigint to f64.
    fn const_to_json(v: &Const) -> serde_json::Value {
        match v {
            Const::Int(i) => serde_json::json!({"t": "i", "v": i}),
            Const::Bool(b) => serde_json::json!({"t": "z", "v": *b}),
            Const::Str(s) => serde_json::json!({"t": "s", "v": s}),
            Const::Bytes(b) => serde_json::json!({"t": "b", "v": b64_encode(b)}),
            Const::Float(f) => serde_json::json!({"t": "f", "v": format!("0x{:016x}", f.to_bits())}),
            Const::Bigint(d) => serde_json::json!({"t": "B", "v": d}),
        }
    }

    fn const_from_json(it: &serde_json::Value) -> Result<Const, PqError> {
        let t = match it.get("t").and_then(|x| x.as_str()) {
            Some(t) => t,
            None => return err("const item missing 't'"),
        };
        let v = match it.get("v") {
            Some(v) => v,
            None => return err("const item missing 'v'"),
        };
        match t {
            "i" => {
                if let Some(n) = v.as_i64() { return Ok(Const::Int(n)); }
                err("invalid const value")
            }
            "z" => match v.as_bool() {
                Some(b) => Ok(Const::Bool(b)),
                None => err("invalid const value"),
            },
            "B" => match v.as_str() {
                Some(d) => Ok(Const::Bigint(d.to_string())),
                None => err("invalid const value"),
            },
            "s" => match v.as_str() {
                Some(s) => Ok(Const::Str(s.to_string())),
                None => err("invalid const value"),
            },
            "b" => match v.as_str().and_then(b64_decode) {
                Some(b) => Ok(Const::Bytes(b)),
                None => err("invalid const value"),
            },
            "f" => {
                let bits = v.as_str()
                    .and_then(|h| u64::from_str_radix(h.trim_start_matches("0x"), 16).ok());
                match bits {
                    Some(bits) => Ok(Const::Float(f64::from_bits(bits))),
                    None => err("invalid const value"),
                }
            }
            _ => err("invalid const tag"),
        }
    }

    fn pool_from_json(v: &serde_json::Value) -> Result<Vec<Const>, PqError> {
        let arr = match v.as_array() {
            Some(a) => a,
            None => return err("const_pool must be an array"),
        };
        arr.iter().map(const_from_json).collect()
    }

    fn program_from_json(v: &serde_json::Value) -> Result<Program, PqError> {
        let name = match v.get("name").and_then(|x| x.as_str()) {
            Some(s) => s.to_string(),
            None => return err("name must be a string"),
        };
        let nl = match v.get("nlocals").and_then(|x| x.as_i64()) {
            Some(n) => n,
            None => return err("nlocals must be an integer"),
        };
        // Defensive only: the wrapper owns the dict-level nlocals gate (b01
        // L305-307, byte-exact message). Never clamp: a clamped value would
        // silently diverge content_hash from what Python produces.
        if !(0..=255).contains(&nl) { return err("nlocals out of range"); }
        let nl_u8 = nl as u8;
        let pool_v = v.get("const_pool").cloned().unwrap_or(serde_json::Value::Array(Vec::new()));
        let pool = pool_from_json(&pool_v)?;
        let code_b64 = match v.get("code_b64").and_then(|x| x.as_str()) {
            Some(s) => s,
            None => return err("code_b64 must be a string"),
        };
        let code = match b64_decode(code_b64) {
            Some(c) => c,
            None => return err("invalid base64 in code_b64"),
        };
        Ok(Program { name, nlocals: nl_u8, pool, code })
    }

    fn pool_to_json(pool: &[Const]) -> Vec<serde_json::Value> {
        pool.iter().map(const_to_json).collect()
    }

    fn program_to_json(p: &Program) -> serde_json::Value {
        serde_json::json!({
            "name": p.name,
            "nlocals": p.nlocals,
            "const_pool": pool_to_json(&p.pool),
            "code_b64": b64_encode(&p.code),
        })
    }

    fn err_json(e: &PqError) -> serde_json::Value {
        // Freeze-contract error kinds: ONLY canonical-path overflows surface as
        // struct.error; every PqError from assemble/validate is BytespaceError.
        let kind = if e.0 == "argument out of range" { "struct.error" } else { "BytespaceError" };
        serde_json::json!({"ok": false, "error": {"kind": kind, "message": e.0}})
    }

    fn out_json(v: Result<serde_json::Value, PqError>) -> *mut std::os::raw::c_char {
        let s = match v {
            Ok(v) => v.to_string(),
            Err(e) => err_json(&e).to_string(),
        };
        out_str(&s)
    }

    fn out_str(s: &str) -> *mut std::os::raw::c_char {
        use std::ffi::CString;
        match CString::new(s.to_owned()) {
            Ok(c) => c.into_raw(),
            Err(_) => {
                // NUL inside an internal string: impossible for serde_json output.
                let f = CString::new("{\"ok\":false,\"error\":{\"kind\":\"InternalError\",\"message\":\"nul in out_json\"}}").unwrap();
                f.into_raw()
            }
        }
    }

    fn panic_err(payload: Box<dyn std::any::Any + Send>) -> PqError {
        let m = if let Some(s) = payload.downcast_ref::<&str>() {
            (*s).to_string()
        } else if let Some(s) = payload.downcast_ref::<String>() {
            s.clone()
        } else {
            "ffi panic".to_string()
        };
        PqError(format!("ffi panic: {}", m))
    }

    fn req_json<'a>(req: *const std::os::raw::c_char) -> Result<serde_json::Value, PqError> {
        use std::ffi::CStr;
        let v: serde_json::Value = unsafe {
            if req.is_null() { return err("null request"); }
            let s = CStr::from_ptr(req).to_str().map_err(|e| PqError(format!("bad utf8: {}", e)))?;
            serde_json::from_str(s)
        }.map_err(|e| PqError(format!("bad json: {}", e)))?;
        Ok(v)
    }

    #[no_mangle]
    pub extern "C" fn pq_ops_json() -> *mut std::os::raw::c_char {
        // Wire shape (freeze contract): [["NOP",...],["LOAD_CONST","RC"],...]
        use super::{K, NAMES, kinds_of};
        let out = std::panic::catch_unwind(std::panic::AssertUnwindSafe(
            || -> Result<serde_json::Value, PqError> {
            let mut ops = Vec::new();
            for (i, n) in NAMES.iter().enumerate() {
                let kinds = match kinds_of(i as u8) {
                    Some(k) => k,
                    None => { continue; }
                };
                let k: String = kinds.iter().map(|x| match x {
                    K::R => "R",
                    K::C => "C",
                    K::J => "J",
                }).collect();
                ops.push(serde_json::json!([n, k]));
            }
            Ok(serde_json::json!(ops))
            },
        ));
        let out = match out {
            Ok(v) => v,
            Err(payload) => Err(panic_err(payload)),
        };
        out_json(out)
    }

    #[no_mangle]
    pub extern "C" fn pq_program_json(req: *const std::os::raw::c_char) -> *mut std::os::raw::c_char {
        // Contract: takes the b01 PROGRAM DICTIONARY over the wire
        // (code as code_b64); emits it back canonicalized with NO
        // content_hash (the hash lives in pq_content_hash_json -- seam parity).
        let out = std::panic::catch_unwind(std::panic::AssertUnwindSafe(
            || -> Result<serde_json::Value, PqError> {
            let req = req_json(req)?;
            let p = program_from_json(&req)?;
            Ok(program_to_json(&p))
            },
        ));
        let out = match out {
            Ok(v) => v,
            Err(payload) => Err(panic_err(payload)),
        };
        out_json(out)
    }

    #[no_mangle]
    pub extern "C" fn pq_assemble_json(req: *const std::os::raw::c_char) -> *mut std::os::raw::c_char {
        // Contract: {"text","name","nlocals","const_extra"} in, PROGRAM DICTIONARY
        // out (NO content_hash: Python b01.assemble never computes one; the
        // hash lives in its own export -- seam parity).
        let out = std::panic::catch_unwind(std::panic::AssertUnwindSafe(
            || -> Result<serde_json::Value, PqError> {
            let req = req_json(req)?;
            let text = match req.get("text").and_then(|x| x.as_str()) {
                Some(s) => s,
                None => return err("text must be a string"),
            };
            let name = match req.get("name").and_then(|x| x.as_str()) {
                Some(s) => s,
                None => return err("name must be a string"),
            };
            let nl = match req.get("nlocals").and_then(|x| x.as_i64()) {
                Some(n) => n,
                None => return err("nlocals must be an integer"),
            };
            if !(0..=255).contains(&nl) { return err("nlocals out of range"); }
            let nl_u8 = nl as u8;
            let pool_v = req.get("const_extra").cloned().unwrap_or(serde_json::Value::Array(Vec::new()));
            let extra = pool_from_json(&pool_v)?;
            let p = assemble(text, name, nl_u8, &extra)?;
            Ok(program_to_json(&p))
            },
        ));
        let out = match out {
            Ok(v) => v,
            Err(payload) => Err(panic_err(payload)),
        };
        out_json(out)
    }

    #[no_mangle]
    pub extern "C" fn pq_validate_json(req: *const std::os::raw::c_char) -> *mut std::os::raw::c_char {
        // Contract: program dict in; Ok(None) on success, Error on failure.
        // Rust result is null on Ok; the wrapper maps to Python None and
        // Error on !ok.
        let out = std::panic::catch_unwind(std::panic::AssertUnwindSafe(
            || -> Result<serde_json::Value, PqError> {
            let req = req_json(req)?;
            let p = program_from_json(&req)?;
            validate(&p)?;
            Ok(serde_json::Value::Null)
            },
        ));
        let out = match out {
            Ok(v) => v,
            Err(payload) => Err(panic_err(payload)),
        };
        out_json(out)
    }

    #[no_mangle]
    pub extern "C" fn pq_content_hash_json(req: *const std::os::raw::c_char) -> *mut std::os::raw::c_char {
        // Contract: program dict in -> 16-hex content_hash string out.
        let out = std::panic::catch_unwind(std::panic::AssertUnwindSafe(
            || -> Result<serde_json::Value, PqError> {
            let req = req_json(req)?;
            let p = program_from_json(&req)?;
            Ok(serde_json::json!(content_hash(&p)?))
            },
        ));
        let out = match out {
            Ok(v) => v,
            Err(payload) => Err(panic_err(payload)),
        };
        out_json(out)
    }

    #[no_mangle]
    pub extern "C" fn pq_version() -> *mut std::os::raw::c_char {
        // pq.dll build stamp; format!(...) is re-derived from Cargo.toml
        // pkg:version on every rebuild, so the string cannot rot.
        out_str(concat!("pq c_abi v", env!("CARGO_PKG_VERSION")))
    }
}