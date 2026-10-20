//! pq::vm -- py4qwhip block 04 (the bytecode-eating VM), Rust port. Reference: ../../blocks/04_vm.py
//! Contract (matches Python 2026-10-14): statuses RUNNING/HALTED/SYNTH_PENDING/FAULT; ints are i64 with
//! an OverflowError trap checked BEFORE the store; Python TypeError/ValueError/ArithmeticError/IndexError/
//! KeyError are trapped as fault "trap:<TypeName>"; VMError text is carried verbatim.
//! Not ported: resolve_and_run (the loop-closure driver stays with block 03, which is Python).
use crate::{validate, Const, Program};
use serde_json::Value;

pub const MAX_STEPS_DEFAULT: u64 = 100_000;
pub const MAX_STR: usize = 10_000;

#[derive(Debug, Clone, PartialEq)]
pub enum Val {
    None,
    Bool(bool),
    Int(i64),
    Str(String),
    Float(f64),
    /// raw bytes (b01 pool byte strings)
    Bytes(Vec<u8>),
    /// canonical decimal string (int beyond i64), e.g. "-123"
    Bigint(String),
}

impl Val {
    pub fn to_json(&self) -> Value {
        match self {
            Val::None => Value::Null,
            Val::Bool(b) => Value::Bool(*b),
            Val::Int(i) => Value::from(*i),
            // non-finite floats: no JSON number; export layer owns that surface
            Val::Float(f) => serde_json::Number::from_f64(*f).map(Value::Number).unwrap_or(Value::Null),
            // latin-1 byte strings on the JSON surface
            Val::Bytes(b) => Value::String(b.iter().map(|&c| c as char).collect()),
            // beyond-i64 ints ride as canonical decimal strings on the JSON surface
            Val::Bigint(s) => Value::String(s.clone()),
            Val::Str(s) => Value::String(s.clone()),
        }
    }
    /// int view (bool is an int subclass); only valid on Int/Bool lanes.
    fn val_i64(&self) -> i64 {
        match self {
            Val::Int(i) => *i,
            Val::Bool(b) => *b as i64,
            _ => 0,
        }
    }
    /// float view (numeric compare across int/float lanes; big ints parse).
    fn val_f64(&self) -> f64 {
        match self {
            Val::Float(f) => *f,
            Val::Int(i) => *i as f64,
            Val::Bool(b) => {
                if *b {
                    1.0
                } else {
                    0.0
                }
            }
            // magnitudes beyond f64 saturate in the float view
            Val::Bigint(s) => s.parse::<f64>().unwrap_or_else(|_| {
                if s.starts_with('-') {
                    f64::NEG_INFINITY
                } else {
                    f64::INFINITY
                }
            }),
            _ => 0.0,
        }
    }
    fn truthy(&self) -> bool {
        match self {
            Val::None => false,
            Val::Bool(b) => *b,
            Val::Int(i) => *i != 0,
            Val::Str(s) => !s.is_empty(),
            Val::Float(f) => *f != 0.0, // NaN is truthy in Python
            Val::Bytes(b) => !b.is_empty(),
            // canonical decimal: only zero is falsy
            Val::Bigint(s) => s != "0",
        }
    }
    /// the VM's _str(): None -> "", str as is, int/bool/float via str();
    /// bytes reach json.dumps -> TypeError (Python); clamped to MAX_STR chars.
    fn as_text(&self) -> Result<String, String> {
        let s = match self {
            Val::None => String::new(),
            Val::Bool(true) => "True".into(),
            Val::Bool(false) => "False".into(),
            Val::Int(i) => i.to_string(),
            Val::Str(s) => s.clone(),
            // Python str(float) = repr(float)
            Val::Float(f) => py_float_repr(*f),
            // json.dumps(b"..") raises TypeError in Python
            Val::Bytes(_) => return trap("TypeError"),
            Val::Bigint(s) => s.clone(),
        };
        Ok(s.chars().take(MAX_STR).collect())
    }
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum Status {
    Running,
    Halted,
    SynthPending,
    Fault,
}

impl Status {
    pub fn as_str(&self) -> &'static str {
        match self {
            Status::Running => "RUNNING",
            Status::Halted => "HALTED",
            Status::SynthPending => "SYNTH_PENDING",
            Status::Fault => "FAULT",
        }
    }
}

#[derive(Debug, Clone)]
pub struct RunState {
    pub status: Status,
    pub steps: u64,
    pub fault: Option<String>,
    pub pending_import: Option<String>,
    pub outs: Vec<Val>,
    pub regs: Vec<Val>,
}

pub struct Machine {
    prog: Program,
    regs: Vec<Val>,
    pc: i64,
    steps: u64,
    max_steps: u64,
    status: Status,
    fault: Option<String>,
    pending_import: Option<String>,
    outs: Vec<Val>,
}

type Step = Result<(), String>;
fn trap<T>(name: &str) -> Result<T, String> {
    Err(format!("trap:{name}"))
}

impl Machine {
    pub fn new(prog: &Program, max_steps: u64) -> Machine {
        let mut m = Machine {
            prog: prog.clone(),
            regs: vec![Val::None; prog.nlocals as usize],
            pc: 0,
            steps: 0,
            max_steps,
            status: Status::Running,
            fault: None,
            pending_import: None,
            outs: Vec::new(),
        };
        if let Err(e) = validate(prog) {
            m.regs = Vec::new();
            m.status = Status::Fault;
            m.fault = Some(format!("validate: {}", e.0));
        }
        m
    }

    fn byte(&self, o: i64) -> Result<u8, String> {
        if o < 0 {
            return trap("IndexError");
        }
        self.prog.code.get(o as usize).copied().map_or_else(|| trap("IndexError"), Ok)
    }
    fn u16(&self, o: i64) -> Result<u16, String> {
        Ok(u16::from_le_bytes([self.byte(o)?, self.byte(o + 1)?]))
    }
    fn s16(&self, o: i64) -> Result<i64, String> {
        Ok(i16::from_le_bytes([self.byte(o)?, self.byte(o + 1)?]) as i64)
    }
    fn rd(&self, r: u8) -> Result<Val, String> {
        self.regs.get(r as usize).cloned().map_or_else(|| trap("IndexError"), Ok)
    }
    fn wr(&mut self, r: u8, v: Val) -> Step {
        match self.regs.get_mut(r as usize) {
            Some(slot) => {
                *slot = v;
                Ok(())
            }
            None => trap("IndexError"),
        }
    }
    fn konst(&self, idx: u16) -> Result<Val, String> {
        match self.prog.pool.get(idx as usize) {
            Some(Const::Int(i)) => Ok(Val::Int(*i)),
            Some(Const::Bool(b)) => Ok(Val::Bool(*b)),
            Some(Const::Str(s)) => Ok(Val::Str(s.clone())),
            Some(Const::Bytes(b)) => Ok(Val::Bytes(b.clone())),
            Some(Const::Float(f)) => Ok(Val::Float(*f)),
            // beyond-i64 pool ints carried as canonical decimal
            Some(Const::Bigint(s)) => Ok(Val::Bigint(s.clone())),
            None => Err(format!("const idx {idx} out of pool")),
        }
    }

    fn step(&mut self) -> Step {
        if self.pc >= self.prog.code.len() as i64 {
            self.status = Status::Halted;
            return Ok(());
        }
        if self.pc < 0 {
            return trap("IndexError");
        }
        let pc = self.pc;
        let opc = self.prog.code[pc as usize];
        if opc > 0x11 {
            return trap("KeyError");
        }
        let mut off = pc + 1;
        match opc {
            0x00 => {}
            0x01 => {
                let v = self.konst(self.u16(off + 1)?)?;
                let d = self.byte(off)?;
                self.wr(d, v)?;
                off += 3;
            }
            0x02 => {
                let slot = self.byte(off)?;
                let dst = self.byte(off + 1)?;
                off += 2;
                let v = self.rd(slot)?;
                self.wr(dst, v)?;
            }
            0x03 => {
                let src = self.byte(off)?;
                let slot = self.byte(off + 1)?;
                off += 2;
                let v = self.rd(src)?;
                self.wr(slot, v)?;
            }
            0x04..=0x08 => {
                let d = self.byte(off)?;
                let a = self.byte(off + 1)?;
                let b = self.byte(off + 2)?;
                off += 3;
                let (va, vb) = (self.rd(a)?, self.rd(b)?);
                let v = arith(opc, &va, &vb)?;
                self.wr(d, v)?;
            }
            0x09 => {
                let rel = self.s16(off)?;
                self.pc = pc + 3 + rel;
                return Ok(());
            }
            0x0A => {
                let r = self.byte(off)?;
                let rel = self.s16(off + 1)?;
                off += 3;
                if self.rd(r)?.truthy() {
                    self.pc = pc + 4 + rel;
                    return Ok(());
                }
            }
            0x0B => return Err("CALL unimplemented in block 04 (function frames land in block 06)".into()),
            0x0C | 0x0E => {
                self.status = Status::Halted;
                return Ok(());
            }
            0x0D => {
                let dst = self.byte(off)?;
                let idx = self.u16(off + 1)?;
                let modname = self.konst(idx)?.as_text()?;
                self.pending_import = Some(modname);
                self.status = Status::SynthPending;
                self.wr(dst, Val::None)?;
                return Ok(());
            }
            0x0F => {
                let d = self.byte(off)?;
                let a = self.byte(off + 1)?;
                let b = self.byte(off + 2)?;
                off += 3;
                let sa = self.rd(a)?.as_text()?;
                let sb = self.rd(b)?.as_text()?;
                let v = Val::Str(sa + &sb);
                self.wr(d, v)?;
            }
            0x10 => {
                let d = self.byte(off)?;
                let a = self.byte(off + 1)?;
                off += 2;
                let n = match self.rd(a)? {
                    Val::None => 0i64,
                    // len(str) counts code points
                    Val::Str(s) => s.chars().count() as i64,
                    // bytes have __len__: raw byte count
                    Val::Bytes(b) => b.len() as i64,
                    // no __len__ -> len(str(v))
                    other => other.as_text()?.chars().count() as i64,
                };
                self.wr(d, Val::Int(n))?;
            }
            0x11 => {
                let v = self.rd(self.byte(off)?)?;
                self.outs.push(v);
                off += 1;
            }
            _ => unreachable!(),
        }
        self.pc = off;
        Ok(())
    }

    pub fn run(&mut self) -> RunState {
        while self.status == Status::Running {
            self.steps += 1;
            if self.steps > self.max_steps {
                self.status = Status::Fault;
                self.fault = Some("step_limit_exceeded".into());
                break;
            }
            if let Err(f) = self.step() {
                self.status = Status::Fault;
                self.fault = Some(f);
                break;
            }
        }
        RunState {
            status: self.status,
            steps: self.steps,
            fault: self.fault.clone(),
            pending_import: self.pending_import.clone(),
            outs: self.outs.clone(),
            regs: self.regs.clone(),
        }
    }
}

fn arith(opc: u8, va: &Val, vb: &Val) -> Result<Val, String> {
    match opc {
        0x07 => {
            // Python plain == (bool is an int subclass; str/bytes vs other
            // types is False; numbers compare numerically across lanes)
            let eq = match (va, vb) {
                (Val::None, Val::None) => true,
                (Val::Str(a), Val::Str(b)) => a == b,
                (Val::Bytes(a), Val::Bytes(b)) => a == b,
                (Val::Float(a), Val::Float(b)) => a == b,
                _ => {
                    if matches!(va, Val::Str(_) | Val::Bytes(_) | Val::None)
                        || matches!(vb, Val::Str(_) | Val::Bytes(_) | Val::None)
                    {
                        false
                    } else if matches!(va, Val::Float(_)) || matches!(vb, Val::Float(_)) {
                        // mixed float: f64 view is the only divergence here
                        va.val_f64() == vb.val_f64()
                    } else {
                        match (va, vb) {
                            (Val::Bigint(a), Val::Bigint(b)) => {
                                big_cmp_dec(a, b) == std::cmp::Ordering::Equal
                            }
                            (Val::Bigint(a), _) => {
                                dec_vs_i64(a, vb.val_i64()) == std::cmp::Ordering::Equal
                            }
                            (_, Val::Bigint(b)) => {
                                dec_vs_i64(b, va.val_i64()) == std::cmp::Ordering::Equal
                            }
                            _ => va.val_i64() == vb.val_i64(),
                        }
                    }
                }
            };
            Ok(Val::Bool(eq))
        }
        0x08 => {
            // Python: (va < vb) only when both are int/float; else None
            let lt: Option<bool> = if matches!(va, Val::None | Val::Str(_) | Val::Bytes(_))
                || matches!(vb, Val::None | Val::Str(_) | Val::Bytes(_))
            {
                None
            } else if matches!(va, Val::Float(_)) || matches!(vb, Val::Float(_)) {
                Some(va.val_f64() < vb.val_f64())
            } else {
                let ord = match (va, vb) {
                    (Val::Bigint(a), Val::Bigint(b)) => big_cmp_dec(a, b),
                    (Val::Bigint(a), _) => dec_vs_i64(a, vb.val_i64()),
                    (_, Val::Bigint(b)) => dec_vs_i64(b, va.val_i64()).reverse(),
                    _ => va.val_i64().cmp(&vb.val_i64()),
                };
                Some(ord == std::cmp::Ordering::Less)
            };
            Ok(match lt {
                Some(b) => Val::Bool(b),
                None => Val::None,
            })
        }
        _ => {
            // MUL traps on any str/bytes operand BEFORE the None guard (Python order)
            if opc == 0x06
                && (matches!(va, Val::Str(_) | Val::Bytes(_))
                    || matches!(vb, Val::Str(_) | Val::Bytes(_)))
            {
                return trap("TypeError");
            }
            if matches!(va, Val::None) || matches!(vb, Val::None) {
                return Ok(Val::None);
            }
            // concat lanes (str+str, bytes+bytes: byte strings DO concat on +)
            if opc == 0x04 {
                if let (Val::Str(a), Val::Str(b)) = (va, vb) {
                    return Ok(Val::Str(format!("{a}{b}")));
                }
                if let (Val::Bytes(a), Val::Bytes(b)) = (va, vb) {
                    let mut c = a.clone();
                    c.extend_from_slice(b);
                    return Ok(Val::Bytes(c));
                }
            }
            // float lane (no i64 check on the float path)
            if matches!(va, Val::Float(_)) || matches!(vb, Val::Float(_)) {
                let (a, b) = (va.val_f64(), vb.val_f64());
                let r = match opc {
                    0x04 => a + b,
                    0x05 => a - b,
                    _ => a * b,
                };
                return Ok(Val::Float(r));
            }
            // big-int lane: unbounded math, trap only on the i64 OUTPUT
            if matches!(va, Val::Bigint(_)) || matches!(vb, Val::Bigint(_)) {
                let sa = dec_of(va);
                let sb = dec_of(vb);
                let r = match opc {
                    0x04 => big_add_dec(&sa, &sb),
                    0x05 => big_add_dec(&sa, &big_negate(&sb)),
                    _ => big_mul_dec(&sa, &sb),
                };
                return dec_to_i64_val(&r);
            }
            // int lane: both operands must be Int/Bool here
            if !matches!(va, Val::Int(_) | Val::Bool(_)) || !matches!(vb, Val::Int(_) | Val::Bool(_))
            {
                return trap("TypeError");
            }
            let a = va.val_i64() as i128;
            let b = vb.val_i64() as i128;
            let r = match opc {
                0x04 => a + b,
                0x05 => a - b,
                _ => a * b,
            };
            if r < i64::MIN as i128 || r > i64::MAX as i128 {
                return trap("OverflowError");
            }
            Ok(Val::Int(r as i64))
        }
    }
}

/// Python str(float) parity: shortest round-trip digits, fixed when
/// -4 <= exp < 16, else 'd.ddd e+DD' CPython 'r' format.
fn py_float_repr(f: f64) -> String {
    if f.is_nan() {
        return "nan".into();
    }
    if f.is_infinite() {
        return if f < 0.0 { "-inf".into() } else { "inf".into() };
    }
    if f == 0.0 {
        return if f.is_sign_negative() { "-0.0".into() } else { "0.0".into() };
    }
    let neg = f < 0.0;
    let a = f.abs();
    let sci = format!("{:e}", a);
    let (mant, exp) = match sci.split_once('e') {
        Some(p) => p,
        None => (sci.as_str(), "0"),
    };
    let e: i32 = exp.parse().unwrap_or(0);
    let digits: String = mant.chars().filter(|c| *c != '.').collect();
    let mut out = String::new();
    if neg {
        out.push('-');
    }
    if e >= 0 && e < 16 {
        let pt = e as usize + 1;
        if pt >= digits.len() {
            out.push_str(&digits);
            out.push_str(&"0".repeat(pt - digits.len()));
            out.push_str(".0");
        } else {
            out.push_str(&digits[..pt]);
            out.push('.');
            out.push_str(&digits[pt..]);
        }
    } else if e >= -4 {
        out.push_str("0.");
        out.push_str(&"0".repeat((-e - 1) as usize));
        out.push_str(&digits);
    } else {
        out.push_str(&digits[..1]);
        if digits.len() > 1 {
            out.push('.');
            out.push_str(&digits[1..]);
        }
        out.push('e');
        if e < 0 {
            out.push('-');
        } else {
            out.push('+');
        }
        let m = e.abs();
        if m < 10 {
            out.push('0');
        }
        out.push_str(&m.to_string());
    }
    out
}

fn split_sign(s: &str) -> (bool, &str) {
    match s.strip_prefix('-') {
        Some(r) => (true, r),
        None => (false, s),
    }
}

fn mag_is_zero(s: &str) -> bool {
    s.chars().all(|c| c == '0')
}

fn mag_cmp(a: &str, b: &str) -> std::cmp::Ordering {
    match a.len().cmp(&b.len()) {
        std::cmp::Ordering::Equal => a.cmp(b),
        o => o,
    }
}

/// canonical-decimal compare (signs handled)
fn big_cmp_dec(a: &str, b: &str) -> std::cmp::Ordering {
    let (na, ma) = split_sign(a);
    let (nb, mb) = split_sign(b);
    let az = mag_is_zero(ma);
    let bz = mag_is_zero(mb);
    if az && bz {
        return std::cmp::Ordering::Equal;
    }
    if na && !nb {
        return std::cmp::Ordering::Less;
    }
    if !na && nb {
        return std::cmp::Ordering::Greater;
    }
    let o = mag_cmp(ma, mb);
    if na {
        o.reverse()
    } else {
        o
    }
}

/// decimal-string vs i64 compare
fn dec_vs_i64(dec: &str, i: i64) -> std::cmp::Ordering {
    big_cmp_dec(dec, &i.to_string())
}

fn add_mag(a: &str, b: &str) -> String {
    let ab = a.as_bytes();
    let bb = b.as_bytes();
    let mut i = ab.len();
    let mut j = bb.len();
    let mut carry = 0u8;
    let mut out: Vec<u8> = Vec::new();
    while i > 0 || j > 0 || carry != 0 {
        let da = if i > 0 { ab[i - 1] - b'0' } else { 0 };
        let db = if j > 0 { bb[j - 1] - b'0' } else { 0 };
        let s = da + db + carry;
        out.push(b'0' + (s % 10));
        carry = s / 10;
        if i > 0 {
            i -= 1;
        }
        if j > 0 {
            j -= 1;
        }
    }
    while out.len() > 1 && *out.last().unwrap() == b'0' {
        out.pop();
    }
    out.reverse();
    String::from_utf8(out).unwrap()
}

/// a >= b required
fn sub_mag(a: &str, b: &str) -> String {
    let ab = a.as_bytes();
    let bb = b.as_bytes();
    let mut i = ab.len();
    let mut j = bb.len();
    let mut borrow = 0i8;
    let mut out: Vec<u8> = Vec::new();
    while i > 0 {
        let mut d = (ab[i - 1] - b'0') as i8 - borrow;
        if j > 0 {
            d -= (bb[j - 1] - b'0') as i8;
            j -= 1;
        }
        if d < 0 {
            d += 10;
            borrow = 1;
        } else {
            borrow = 0;
        }
        out.push(b'0' + d as u8);
        i -= 1;
    }
    while out.len() > 1 && *out.last().unwrap() == b'0' {
        out.pop();
    }
    out.reverse();
    String::from_utf8(out).unwrap()
}

/// signed decimal add
fn big_add_dec(a: &str, b: &str) -> String {
    let (na, ma) = split_sign(a);
    let (nb, mb) = split_sign(b);
    if na == nb {
        let s = add_mag(ma, mb);
        if na && !mag_is_zero(&s) {
            format!("-{s}")
        } else {
            s
        }
    } else {
        match mag_cmp(ma, mb) {
            std::cmp::Ordering::Equal => "0".into(),
            std::cmp::Ordering::Greater => {
                let d = sub_mag(ma, mb);
                if na {
                    format!("-{d}")
                } else {
                    d
                }
            }
            std::cmp::Ordering::Less => {
                let d = sub_mag(mb, ma);
                if nb {
                    format!("-{d}")
                } else {
                    d
                }
            }
        }
    }
}

fn big_negate(s: &str) -> String {
    if mag_is_zero(s) {
        return "0".into();
    }
    match split_sign(s) {
        (true, m) => m.into(),
        (false, m) => format!("-{m}"),
    }
}

/// signed decimal multiply
fn big_mul_dec(a: &str, b: &str) -> String {
    let (na, ma) = split_sign(a);
    let (nb, mb) = split_sign(b);
    if mag_is_zero(ma) || mag_is_zero(mb) {
        return "0".into();
    }
    let ab = ma.as_bytes();
    let bb = mb.as_bytes();
    let mut acc = vec![0u32; ab.len() + bb.len()];
    for i in 0..ab.len() {
        for j in 0..bb.len() {
            acc[i + j + 1] += (ab[i] - b'0') as u32 * (bb[j] - b'0') as u32;
        }
    }
    let mut carry: u32 = 0;
    for k in (0..acc.len()).rev() {
        let v = acc[k] + carry;
        acc[k] = v % 10;
        carry = v / 10;
    }
    let s: String = acc.iter().map(|d| (b'0' + *d as u8) as char).collect();
    let t = s.trim_start_matches('0');
    let r = if t.is_empty() { "0" } else { t };
    if na != nb {
        format!("-{r}")
    } else {
        r.into()
    }
}

/// decimal string to Val lane; OverflowError trap iff out of i64
fn dec_to_i64_val(s: &str) -> Result<Val, String> {
    let (neg, mag) = split_sign(s);
    let m = mag.trim_start_matches('0');
    let m = if m.is_empty() { "0" } else { m };
    let limit = if neg {
        "9223372036854775808"
    } else {
        "9223372036854775807"
    };
    if !(m.len() < 19 || (m.len() == 19 && m.as_bytes() <= limit.as_bytes())) {
        return trap("OverflowError");
    }
    let v: i128 = m.parse().unwrap_or(0);
    Ok(Val::Int(if neg { -v } else { v } as i64))
}

/// decimal view of a numeric operand for the Bigint lanes
fn dec_of(v: &Val) -> String {
    match v {
        Val::Bigint(s) => s.clone(),
        Val::Int(i) => i.to_string(),
        Val::Bool(b) => {
            if *b {
                "1".into()
            } else {
                "0".into()
            }
        }
        _ => "0".into(),
    }
}
