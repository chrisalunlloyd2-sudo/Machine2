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
}

impl Val {
    pub fn to_json(&self) -> Value {
        match self {
            Val::None => Value::Null,
            Val::Bool(b) => Value::Bool(*b),
            Val::Int(i) => Value::from(*i),
            Val::Str(s) => Value::String(s.clone()),
        }
    }
    /// Python numeric view (bool is an int subclass).
    fn num(&self) -> Option<i64> {
        match self {
            Val::Int(i) => Some(*i),
            Val::Bool(b) => Some(*b as i64),
            _ => None,
        }
    }
    fn truthy(&self) -> bool {
        match self {
            Val::None => false,
            Val::Bool(b) => *b,
            Val::Int(i) => *i != 0,
            Val::Str(s) => !s.is_empty(),
        }
    }
    /// the VM's _str(): None -> "", str as is, int/bool via str(); clamped to MAX_STR chars.
    fn as_text(&self) -> String {
        let s = match self {
            Val::None => String::new(),
            Val::Bool(true) => "True".into(),
            Val::Bool(false) => "False".into(),
            Val::Int(i) => i.to_string(),
            Val::Str(s) => s.clone(),
        };
        s.chars().take(MAX_STR).collect()
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
            Some(Const::Str(s)) => Ok(Val::Str(s.clone())),
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
                let modname = self.konst(idx)?.as_text();
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
                let v = Val::Str(self.rd(a)?.as_text() + &self.rd(b)?.as_text());
                self.wr(d, v)?;
            }
            0x10 => {
                let d = self.byte(off)?;
                let a = self.byte(off + 1)?;
                off += 2;
                let n = match self.rd(a)? {
                    Val::None => 0,
                    Val::Str(s) => s.chars().count(),
                    other => other.as_text().chars().count(), // len(str(v)); not clamped for ints (max 20 chars)
                };
                self.wr(d, Val::Int(n as i64))?;
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
    use Val::*;
    match opc {
        0x07 => {
            let eq = match (va, vb) {
                (None, None) => true,
                (Str(a), Str(b)) => a == b,
                _ => match (va.num(), vb.num()) {
                    (Some(a), Some(b)) => a == b,
                    _ => false,
                },
            };
            Ok(Bool(eq))
        }
        0x08 => Ok(match (va.num(), vb.num()) {
            (Some(a), Some(b)) => Bool(a < b),
            _ => None,
        }),
        _ => {
            // MUL on a sequence traps before the None check (Python order)
            if opc == 0x06 && (matches!(va, Str(_)) || matches!(vb, Str(_))) {
                return trap("TypeError");
            }
            if matches!(va, None) || matches!(vb, None) {
                return Ok(None);
            }
            if opc == 0x04 {
                if let (Str(a), Str(b)) = (va, vb) {
                    return Ok(Str(format!("{a}{b}")));
                }
            }
            let (a, b) = match (va.num(), vb.num()) {
                (Some(a), Some(b)) => (a as i128, b as i128),
                _ => return trap("TypeError"),
            };
            let r = match opc {
                0x04 => a + b,
                0x05 => a - b,
                _ => a * b,
            };
            if r < i64::MIN as i128 || r > i64::MAX as i128 {
                return trap("OverflowError");
            }
            Ok(Int(r as i64))
        }
    }
}
