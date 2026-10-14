//! pq -- py4qwhip block 01 (byte-space), Rust port. Reference: ../../blocks/01_bytespace.py
//! Deterministic, no I/O. Must reproduce the Python content_hash byte-for-byte (golden vectors).
use sha2::{Digest, Sha256};
use std::collections::HashMap;

pub mod karaka;
pub mod vm;

pub const MAGIC: &[u8] = b"PY4QW01";
pub const VERSION: u8 = 1;
const MAX_POOL: usize = 65535;
const MAX_LOCALS: i64 = 255;

#[derive(Debug, Clone, PartialEq)]
pub enum Const {
    Int(i64),
    Str(String),
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
                    return err(format!("duplicate label {l:?}"));
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
            None => return err(format!("unknown op {o:?}")),
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
            return err(format!("{o} wants {} operands, got {}", kinds.len(), args.len()));
        }
        code.push(opc);
        let after = (ins_bytes[idx] + op_size(kinds)) as i64;
        for (k, a) in kinds.iter().zip(args.iter()) {
            match k {
                K::R => {
                    let parsed = if a.starts_with('r') { a[1..].parse::<i64>() } else { a.parse::<i64>() };
                    let n = parsed.map_err(|_| PqError(format!("bad register {a:?}")))?;
                    if !(0..=MAX_LOCALS).contains(&n) {
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
                        Const::Int(s.parse::<i64>().map_err(|_| PqError(format!("bad int {s:?}")))?)
                    } else {
                        Const::Str(s.to_string())
                    };
                    if let Const::Str(t) = &v {
                        if t.starts_with('r') {
                            return err(format!("const slot got register {a:?}"));
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
                        return err("const index out of range");
                    }
                    code.extend_from_slice(&(i as u16).to_le_bytes());
                }
                K::J => {
                    let t = match label_byte.get(a.as_str()) {
                        Some(t) => *t as i64,
                        None => return err(format!("unknown label {a:?}")),
                    };
                    let rel = t - after;
                    if !(-32768..=32767).contains(&rel) {
                        return err("jump offset out of range");
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
pub fn canonical_bytes(p: &Program) -> Vec<u8> {
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
            Const::Str(s) => {
                o.push(1);
                o.extend_from_slice(&(s.len() as u32).to_le_bytes());
                o.extend_from_slice(s.as_bytes());
            }
        }
    }
    o.extend_from_slice(&(p.code.len() as u32).to_le_bytes());
    o.extend_from_slice(&p.code);
    o
}

pub fn content_hash(p: &Program) -> String {
    let d = Sha256::digest(canonical_bytes(p));
    d.iter().take(8).map(|b| format!("{b:02x}")).collect()
}
