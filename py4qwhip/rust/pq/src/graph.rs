//! graph — pq block 05: graph core (reachability + planner proofs), Rust port.
//!
//! Python reference (live source, re-read this session):
//!   C:\Viper\projects\BDI_FSM_AGENT\bdi_fsm\reachability.py
//!   C:\Viper\projects\BDI_FSM_AGENT\bdi_fsm\planner_proofs.py
//! Golden vectors: ../../rust_plan/graph_golden.json (pq05_golden_gen_v3.py,
//! run under PY311 against the live reference).
//! Conformance: every result object equals the Python reference as parsed
//! JSON (key order free); formula error strings match byte-for-byte
//! (tests/graph_golden.rs).
//!
//! Fidelity notes:
//! - Transition guards over JSON arrive only as `null` (no guard) or a
//!   boolean formula string; the RUNTIME/callable branch of the Python
//!   `guard_verdict` cannot occur and is therefore not representable here.
//! - Python falsy-chains are preserved exactly: an EMPTY explicit list means
//!   "empty" for deadlock/liveness `terminals` (nothing is exempt from the
//!   check) but falls through to auto-terminals for liveness/termination
//!   `goals` (truthiness), matching reference lines exactly.
//! - `path_to` default depth = max(#distinct source states + 1, 32).
//! - termination rank VALUES are deterministic (multi-source BFS minimal
//!   distance, all seeds enqueued before any expansion), so the Python
//!   reference's set-seeding order changes no values; JSON map keys compare
//!   order-free.
//! - Error fidelity: "mismatched parens", "unexpected char {c!r} at {i} in
//!   {f!r}", "malformed formula {f!r}: {e}" with CPython's exact IndexError
//!   texts ("pop from empty list", "list index out of range").

use serde_json::{json, Map, Value};
use std::collections::VecDeque;

/// Mirrors bdi_fsm ReachabilityError; carries the exact Python error string.
#[derive(Debug)]
pub struct ReachabilityError(pub String);

fn err<T>(m: impl Into<String>) -> Result<T, ReachabilityError> {
    Err(ReachabilityError(m.into()))
}

// ---- input data ------------------------------------------------------------

#[derive(Debug, Clone)]
pub struct Edge {
    pub from: String,
    pub event: String,
    pub to: String,
    /// None (no guard) or a boolean-formula string. Python's callable guards
    /// cannot arrive over JSON and are not representable.
    pub guard: Option<String>,
}

#[derive(Debug, Clone, Default)]
pub struct Graph {
    /// The FSM's current-state attribute (default start for path search).
    pub state: Option<String>,
    /// Flattened _transitions table in reference iteration order:
    /// states in first-appearance order, events in insertion order —
    /// which (for unique keys) equals the golden `edges` list order.
    pub edges: Vec<Edge>,
}

/// The reference renders every edge as {from, event, to, guard}.
pub fn edge_json(e: &Edge) -> Value {
    json!({"from": &e.from, "event": &e.event, "to": &e.to, "guard": &e.guard})
}

// ---- Python str repr (used in error strings) -------------------------------

/// Python `repr(str)`: quote choice (' unless the string contains a ' and
/// no "), backslash/control escapes. Covers the repr forms the reference
/// embeds in error text.
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

// ---- propositional guard formulas (reachability.py) ------------------------

#[derive(Debug, Clone, PartialEq)]
pub enum Tok {
    Atom(String),
    Not,
    And,
    Or,
    Imp,
    Iff,
    LP,
    RP,
}

fn starts_at(chars: &[char], i: usize, s: &str) -> bool {
    let mut n = 0usize;
    for want in s.chars() {
        if chars.get(i + n) != Some(&want) {
            return false;
        }
        n += 1;
    }
    true
}

// _ATOM = re.compile(r"[A-Za-z_][A-Za-z0-9_]*") — ASCII ranges only.
fn is_atom_start(c: char) -> bool {
    c.is_ascii_alphabetic() || c == '_'
}
fn is_atom_char(c: char) -> bool {
    c.is_ascii_alphanumeric() || c == '_'
}

/// reachability.tokenize_formula
pub fn tokenize_formula(formula: &str) -> Result<Vec<Tok>, ReachabilityError> {
    // Python indexes str by codepoint; iterate chars so `i` matches.
    let chars: Vec<char> = formula.chars().collect();
    let mut toks: Vec<Tok> = Vec::new();
    let mut i = 0usize;
    while i < chars.len() {
        let c = chars[i];
        if c.is_whitespace() {
            i += 1;
        } else if c == '(' {
            toks.push(Tok::LP);
            i += 1;
        } else if c == ')' {
            toks.push(Tok::RP);
            i += 1;
        } else if starts_at(&chars, i, "<->") {
            toks.push(Tok::Iff);
            i += 3;
        } else if starts_at(&chars, i, "->") {
            toks.push(Tok::Imp);
            i += 2;
        } else if c == '~' {
            toks.push(Tok::Not);
            i += 1;
        } else if c == '&' {
            toks.push(Tok::And);
            i += 1;
        } else if c == '|' {
            toks.push(Tok::Or);
            i += 1;
        } else if is_atom_start(c) {
            let mut j = i + 1;
            while j < chars.len() && is_atom_char(chars[j]) {
                j += 1;
            }
            toks.push(Tok::Atom(chars[i..j].iter().collect()));
            i = j;
        } else {
            return err(format!(
                "unexpected char {} at {} in {}",
                py_repr(&c.to_string()),
                i,
                py_repr(formula)
            ));
        }
    }
    Ok(toks)
}

// _OPS precedences; -> and <-> tie at 1 and never pop on ties
// (reference treats them plus ~ as right-associative).
fn prec(t: &Tok) -> i32 {
    match t {
        Tok::Not => 4,
        Tok::And => 3,
        Tok::Or => 2,
        Tok::Imp | Tok::Iff => 1,
        _ => 0,
    }
}

/// reachability.shunting_yard
pub fn shunting_yard(tokens: Vec<Tok>) -> Result<Vec<Tok>, ReachabilityError> {
    let mut out: Vec<Tok> = Vec::new();
    let mut stack: Vec<Tok> = Vec::new();
    for t in tokens {
        match t {
            Tok::Atom(_) => out.push(t),
            Tok::LP => stack.push(Tok::LP),
            Tok::RP => loop {
                match stack.pop() {
                    Some(Tok::LP) => break,
                    Some(top) => out.push(top),
                    None => return err("mismatched parens"),
                }
            },
            op => {
                // stack holds only LPs and ops; mirror the reference pop loop
                loop {
                    let pop = match stack.last() {
                        None => false,
                        Some(Tok::LP) => false,
                        Some(top) => {
                            let pt = prec(&op);
                            let ptop = prec(top);
                            ptop > pt
                                || (ptop == pt && !matches!(op, Tok::Imp | Tok::Iff | Tok::Not))
                        }
                    };
                    if pop {
                        out.push(stack.pop().unwrap());
                    } else {
                        break;
                    }
                }
                stack.push(op);
            }
        }
    }
    while let Some(top) = stack.pop() {
        if top == Tok::LP {
            return err("mismatched parens");
        }
        out.push(top);
    }
    Ok(out)
}

/// CPython IndexError texts the reference embeds in `malformed formula {f!r}`.
enum EvalFault {
    /// list.pop() on empty -> "pop from empty list"
    PopEmpty,
    /// st[0] on empty -> "list index out of range"
    OutOfRange,
}

fn eval_postfix<F>(postfix: &[Tok], env: &F) -> Result<bool, EvalFault>
where
    F: Fn(&str) -> bool,
{
    let mut st: Vec<bool> = Vec::new();
    for t in postfix {
        match t {
            Tok::Not => {
                let a = st.pop().ok_or(EvalFault::PopEmpty)?;
                st.push(!a);
            }
            Tok::And | Tok::Or | Tok::Imp | Tok::Iff => {
                let b = st.pop().ok_or(EvalFault::PopEmpty)?;
                let a = st.pop().ok_or(EvalFault::PopEmpty)?;
                let v = match t {
                    Tok::And => a && b,
                    Tok::Or => a || b,
                    Tok::Imp => !a || b,
                    _ => a == b,
                };
                st.push(v);
            }
            Tok::Atom(name) => st.push(env(name)),
            // parens never survive shunting_yard
            _ => unreachable!("paren token in postfix"),
        }
    }
    st.first().copied().ok_or(EvalFault::OutOfRange)
}

/// reachability.truth_table -> {atoms, rows, is_tautology, is_satisfiable, models}
pub fn truth_table(formula: &str) -> Result<Value, ReachabilityError> {
    let toks = tokenize_formula(formula)?;
    let mut atoms: Vec<String> = toks
        .iter()
        .filter_map(|t| match t {
            Tok::Atom(s) => Some(s.clone()),
            _ => None,
        })
        .collect();
    atoms.sort(); // Python sorted(set(...)) — same codepoint order
    atoms.dedup();
    let post = shunting_yard(toks)?;
    let n = atoms.len();
    let mut rows: Vec<Value> = Vec::new();
    let mut models: i64 = 0;
    // itertools.product([False, True], repeat=n): atoms[0] is the slowest bit.
    for idx in 0..(1usize << n) {
        let mut bits: Vec<bool> = Vec::with_capacity(n);
        for j in 0..n {
            bits.push(((idx >> (n - 1 - j)) & 1) == 1);
        }
        let env = |name: &str| -> bool {
            atoms
                .iter()
                .zip(bits.iter())
                .find(|(a, _)| a.as_str() == name)
                .map(|(_, b)| *b)
                .unwrap_or(false)
        };
        let val = match eval_postfix(&post, &env) {
            Ok(v) => v,
            Err(EvalFault::PopEmpty) => {
                return err(format!(
                    "malformed formula {}: pop from empty list",
                    py_repr(formula)
                ));
            }
            Err(EvalFault::OutOfRange) => {
                return err(format!(
                    "malformed formula {}: list index out of range",
                    py_repr(formula)
                ));
            }
        };
        rows.push(json!([&bits, val]));
        if val {
            models += 1;
        }
    }
    let row_count = rows.len() as i64;
    Ok(json!({
        "atoms": &atoms,
        "rows": rows,
        "is_tautology": models == row_count && row_count > 0,
        "is_satisfiable": models > 0,
        "models": models,
    }))
}

/// reachability.guard_verdict for string guards.
pub fn guard_verdict_str(guard: &str) -> Result<(String, Option<Value>), ReachabilityError> {
    let tt = truth_table(guard)?;
    let taut = tt["is_tautology"].as_bool().unwrap_or(false);
    let sat = tt["is_satisfiable"].as_bool().unwrap_or(false);
    let verdict = if taut {
        "TAUTOLOGY"
    } else if sat {
        "SATISFIABLE"
    } else {
        "UNSAT"
    };
    Ok((verdict.to_string(), Some(tt)))
}

/// reachability.guard_verdict over JSON-representable guards.
/// (The RUNTIME branch exists only for Python callables — unreachable here.)
pub fn guard_verdict_opt(
    guard: Option<&str>,
) -> Result<(String, Option<Value>), ReachabilityError> {
    match guard {
        None => Ok(("TAUTOLOGY".to_string(), None)),
        Some(f) => guard_verdict_str(f),
    }
}

// ---- graph machinery -------------------------------------------------------

/// Insertion-ordered state -> edge-index map (Python dict/setdefault order).
type Adj = Vec<(String, Vec<usize>)>;

fn slot<'a>(adj: &'a mut Adj, k: &str) -> &'a mut Vec<usize> {
    if let Some(i) = adj.iter().position(|(s, _)| s == k) {
        return &mut adj[i].1;
    }
    adj.push((k.to_string(), Vec::new()));
    let i = adj.len() - 1;
    &mut adj[i].1
}

fn adj_of<'a>(adj: &'a Adj, k: &str) -> &'a [usize] {
    match adj.iter().position(|(s, _)| s == k) {
        Some(i) => adj[i].1.as_slice(),
        None => &[],
    }
}

fn adj_get<'a>(adj: &'a Adj, k: &str) -> Option<&'a [usize]> {
    adj.iter().find(|(s, _)| s.as_str() == k).map(|(_, v)| v.as_slice())
}

fn adj_has(adj: &Adj, k: &str) -> bool {
    adj.iter().any(|(s, _)| s.as_str() == k)
}

#[allow(clippy::needless_clone)]
fn sorted_states(adj: &Adj) -> Vec<(String, Vec<usize>)> {
    let mut v = adj.clone();
    v.sort_by(|a, b| a.0.cmp(&b.0));
    v
}

/// planner_proofs._terminals: sorted states with no outgoing edges.
fn terminals_of(adj: &Adj) -> Vec<String> {
    let mut v: Vec<String> = adj
        .iter()
        .filter(|(_, es)| es.is_empty())
        .map(|(s, _)| s.clone())
        .collect();
    v.sort();
    v
}

/// `start or fsm.state or "IDLE"` with Python falsy semantics.
fn resolve_start(g: &Graph, start: Option<&str>) -> String {
    match start {
        Some(s) if !s.is_empty() => s.to_string(),
        _ => match g.state.as_deref() {
            Some(st) if !st.is_empty() => st.to_string(),
            _ => "IDLE".to_string(),
        },
    }
}

/// planner_proofs._edge_can_fire: verdict != "UNSAT".
fn edge_can_fire(guard: Option<&str>) -> Result<bool, ReachabilityError> {
    match guard {
        None => Ok(true), // TAUTOLOGY
        Some(f) => {
            let tt = truth_table(f)?;
            Ok(tt["is_satisfiable"].as_bool().unwrap_or(false))
        }
    }
}

// ---- reachability.py: path search ------------------------------------------

fn path_to_idx(
    g: &Graph,
    goal: &str,
    start: Option<&str>,
    max_depth: Option<i64>,
) -> Option<Vec<usize>> {
    let adj = adj_sources(g); // from-keys only (reference order)
    let s0 = resolve_start(g, start);
    if !adj_has(&adj, &s0) && s0 != goal {
        return None;
    }
    let depth = match max_depth {
        Some(d) => d,
        None => std::cmp::max(adj.len() as i64 + 1, 32),
    };
    let mut seen: Vec<String> = vec![s0.clone()];
    let mut q: VecDeque<(String, Vec<usize>)> = VecDeque::new();
    q.push_back((s0, Vec::new()));
    while let Some((cur, path)) = q.pop_front() {
        if cur == goal {
            return Some(path);
        }
        if path.len() as i64 >= depth {
            continue;
        }
        for &ei in adj_of(&adj, &cur) {
            let to = g.edges[ei].to.clone();
            if seen.contains(&to) {
                continue;
            }
            seen.push(to.clone());
            let mut next = path.clone();
            next.push(ei);
            q.push_back((to, next));
        }
    }
    None
}

/// reachability.path_to -> shortest edge path, or None when unreachable.
pub fn path_to(
    g: &Graph,
    goal: &str,
    start: Option<&str>,
    max_depth: Option<i64>,
) -> Option<Vec<Edge>> {
    path_to_idx(g, goal, start, max_depth)
        .map(|idxs| idxs.iter().map(|&i| g.edges[i].clone()).collect())
}

/// reachability.verify_path — per-edge guard verdicts on the BFS path.
pub fn verify_path(
    g: &Graph,
    goal: &str,
    start: Option<&str>,
    max_depth: Option<i64>,
) -> Result<Value, ReachabilityError> {
    let path = match path_to_idx(g, goal, start, max_depth) {
        Some(p) => p,
        None => {
            return Ok(json!({
                "reachable": false,
                "path": Value::Null,
                "proofs": Vec::<Value>::new(),
                "blocked": Value::Null,
                "reason": "no path in state graph",
            }));
        }
    };
    let path_json: Vec<Value> = path.iter().map(|&i| edge_json(&g.edges[i])).collect();
    let mut proofs: Vec<Value> = Vec::new();
    for &i in &path {
        let e = &g.edges[i];
        let (verdict, tt) = guard_verdict_opt(e.guard.as_deref())?;
        let is_unsat = verdict == "UNSAT";
        // Step guard rendering: str stays, None stays null ("<callable>"
        // branch unreachable over JSON). "models" only for string guards.
        let mut step = json!({
            "from": &e.from,
            "event": &e.event,
            "to": &e.to,
            "guard": &e.guard,
            "verdict": &verdict,
        });
        if let Some(tt) = &tt {
            step["models"] = tt["models"].clone();
        }
        proofs.push(step.clone());
        if is_unsat {
            let reason = format!(
                "edge {} -{}-> {} guard {} is UNSAT (no model)",
                e.from,
                e.event,
                e.to,
                py_repr(e.guard.as_deref().unwrap_or(""))
            );
            return Ok(json!({
                "reachable": false,
                "path": path_json,
                "proofs": proofs,
                "blocked": step,
                "reason": reason,
            }));
        }
    }
    Ok(json!({
        "reachable": true,
        "path": path_json,
        "proofs": proofs,
        "blocked": Value::Null,
        "reason": Value::Null,
    }))
}

/// reachability.prove_exit — prove every goal (default: auto terminals).
pub fn prove_exit(
    g: &Graph,
    goals: Option<&[String]>,
    start: Option<&str>,
) -> Result<Value, ReachabilityError> {
    let s0 = resolve_start(g, start);
    let goal_list: Vec<String> = match goals {
        Some(list) => list.to_vec(),
        None => {
            // sorted(states with no outgoing edge) over raw edges
            let mut v: Vec<String> = Vec::new();
            for e in &g.edges {
                if !v.contains(&e.from) {
                    v.push(e.from.clone());
                }
                if !v.contains(&e.to) {
                    v.push(e.to.clone());
                }
            }
            v.retain(|s| !g.edges.iter().any(|e| &e.from == s));
            v.sort();
            v
        }
    };
    if goal_list.is_empty() {
        return Ok(json!({
            "start": &s0,
            "goals": Vec::<Value>::new(),
            "results": Map::new(),
            "all_reachable": false,
            "summary": Map::new(),
            "reason": "no terminal states exist (cyclic control loop); call prove_exit(goals=[...]) with explicit success states",
        }));
    }
    let mut results = Map::new();
    let mut summary = Map::new();
    let mut all_ok = true;
    for gl in &goal_list {
        let r = verify_path(g, gl, Some(&s0), None)?;
        let ok = r["reachable"].as_bool().unwrap_or(false);
        results.insert(gl.clone(), r);
        summary.insert(gl.clone(), Value::Bool(ok));
        all_ok = all_ok && ok;
    }
    Ok(json!({
        "start": &s0,
        "goals": &goal_list,
        "results": results,
        "all_reachable": all_ok,
        "summary": summary,
    }))
}

// ---- planner_proofs.py -----------------------------------------------------

fn adj_sources(g: &Graph) -> Adj {
    let mut adj: Adj = Adj::new();
    for (i, e) in g.edges.iter().enumerate() {
        slot(&mut adj, &e.from).push(i);
    }
    adj
}

/// planner_proofs._graph: from-keys, then every to-key (reference order).
fn adj_full(g: &Graph) -> Adj {
    let mut adj = adj_sources(g);
    for e in &g.edges {
        slot(&mut adj, &e.to);
    }
    adj
}

/// planner_proofs.deadlock_report
pub fn deadlock_report(
    g: &Graph,
    terminals: Option<&[String]>,
) -> Result<Value, ReachabilityError> {
    let adj = adj_full(g);
    let terms: Vec<String> = match terminals {
        Some(t) => t.to_vec(),
        None => terminals_of(&adj),
    };
    let mut dead: Vec<Value> = Vec::new();
    for (s, es) in sorted_states(&adj) {
        if terms.contains(&s) {
            continue;
        }
        let mut live = false;
        // reference: live_edges = [e for e in es if _edge_can_fire(e["guard"])]
        // — a list comprehension: EVERY guard is evaluated in list order (no
        // short-circuit), so a malformed guard raises even when an earlier
        // edge already fired (fuzz fz00008: '' guard raises
        // "malformed formula '': list index out of range" out of audit).
        for &ei in &es {
            if edge_can_fire(g.edges[ei].guard.as_deref())? {
                live = true;
            }
        }
        if !live {
            let edges_json: Vec<Value> = es
                .iter()
                .map(|&ei| {
                    let e = &g.edges[ei];
                    json!({"event": &e.event, "to": &e.to, "guard": &e.guard})
                })
                .collect();
            dead.push(json!({
                "state": &s,
                "edges": edges_json,
                "cause": if es.is_empty() { "no_outgoing" } else { "all_guards_unsat" },
            }));
        }
    }
    let cex = if dead.is_empty() { Value::Null } else { dead[0].clone() };
    Ok(json!({
        "property": "deadlock-freedom",
        "holds": dead.is_empty(),
        "deadlock_states": dead,
        "counterexample": cex,
    }))
}

fn symbolic_reaches(
    start: &str,
    adj: &Adj,
    terms: &[String],
    g: &Graph,
) -> Result<bool, ReachabilityError> {
    let mut seen: Vec<String> = vec![start.to_string()];
    let mut q: VecDeque<String> = VecDeque::new();
    q.push_back(start.to_string());
    while let Some(cur) = q.pop_front() {
        if terms.contains(&cur) {
            return Ok(true);
        }
        for &ei in adj_of(adj, &cur) {
            let e = &g.edges[ei];
            if !seen.contains(&e.to) && edge_can_fire(e.guard.as_deref())? {
                seen.push(e.to.clone());
                q.push_back(e.to.clone());
            }
        }
    }
    Ok(false)
}

/// planner_proofs.liveness
pub fn liveness(
    g: &Graph,
    terminals: Option<&[String]>,
    goals: Option<&[String]>,
) -> Result<Value, ReachabilityError> {
    let adj = adj_full(g);
    // terms = set(goals) if goals else (set(terminals) if terminals is not
    // None else set(_terminals(adj))) — goal emptiness falls through,
    // terminal emptiness is respected.
    let mut terms: Vec<String> = match goals {
        Some(list) if !list.is_empty() => list.to_vec(),
        _ => match terminals {
            Some(t) => t.to_vec(),
            None => terminals_of(&adj),
        },
    };
    terms.sort();
    terms.dedup();
    if terms.is_empty() {
        let first = match adj.first() {
            Some((s, _)) => s.clone(),
            None => {
                // Python raises StopIteration here (uncaught by the golden
                // generator); no edgeless-FSM golden case exists.
                return err::<Value>(
                    "liveness on an edgeless fsm: reference raises StopIteration (no golden case)",
                );
            }
        };
        return Ok(json!({
            "property": "liveness",
            "holds": false,
            "counterexample": {"state": first, "reason": "no terminal states exist"},
        }));
    }
    let mut bad: Vec<Value> = Vec::new();
    for (s, _es) in sorted_states(&adj) {
        // structural BFS
        let mut seen: Vec<String> = vec![s.clone()];
        let mut q: VecDeque<String> = VecDeque::new();
        q.push_back(s.clone());
        let mut reached = false;
        while let Some(cur) = q.pop_front() {
            if terms.contains(&cur) {
                reached = true;
                break;
            }
            for &ei in adj_of(&adj, &cur) {
                let to = g.edges[ei].to.clone();
                if !seen.contains(&to) {
                    seen.push(to.clone());
                    q.push_back(to);
                }
            }
        }
        if !reached {
            bad.push(json!({"state": &s, "reason": "no structural path to any terminal"}));
            continue;
        }
        if !symbolic_reaches(&s, &adj, &terms, g)? {
            bad.push(json!({
                "state": &s,
                "reason": "all paths to a terminal pass an UNSAT guard",
            }));
        }
    }
    let cex = if bad.is_empty() { Value::Null } else { bad[0].clone() };
    Ok(json!({
        "property": "liveness",
        "holds": bad.is_empty(),
        "terminals": &terms,
        "counterexample": cex,
        "violations": bad,
    }))
}

fn rank_get(rank: &[(String, i64)], k: &str) -> Option<i64> {
    rank.iter().find(|(s, _)| s.as_str() == k).map(|(_, r)| *r)
}

fn rank_push(rank: &mut Vec<(String, i64)>, k: &str, v: i64) {
    if let Some(i) = rank.iter().position(|(s, _)| s.as_str() == k) {
        rank[i].1 = v;
    } else {
        rank.push((k.to_string(), v));
    }
}

fn color_get(color: &[(String, u8)], k: &str) -> Option<u8> {
    color.iter().find(|(s, _)| s.as_str() == k).map(|(_, c)| *c)
}

fn color_set(color: &mut [(String, u8)], k: &str, v: u8) {
    if let Some(i) = color.iter().position(|(s, _)| s.as_str() == k) {
        color[i].1 = v;
    }
}

const NOTE_TERMINATION: &str = "no-goal termination requires an acyclic graph; with goals, cycles that never pass a goal are livelocks (need runtime bounded counters), cycles that pass a goal are task-cycles where each loop completes a unit of work.";

fn dfs_cycle(
    g: &Graph,
    adj: &Adj,
    color: &mut Vec<(String, u8)>,
    path: &mut Vec<usize>,
    cycles: &mut Vec<Vec<usize>>,
    s: &str,
) {
    color_set(color, s, 1);
    let es: Vec<usize> = adj_get(adj, s).map(|v| v.to_vec()).unwrap_or_default();
    for ei in es {
        let to = g.edges[ei].to.clone();
        match color_get(color, &to) {
            Some(1) => {
                // extract the cycle from the DFS path (reference semantics:
                // first edge on _path whose `from` == e["to"], else the whole
                // path, then append e)
                let idx = path
                    .iter()
                    .position(|&p| g.edges[p].from == to)
                    .unwrap_or(path.len());
                let mut cyc: Vec<usize> = path[idx..].to_vec();
                cyc.push(ei);
                let first = &g.edges[cyc[0]];
                let fk = (first.from.as_str(), first.event.as_str(), first.to.as_str());
                let dup = cycles.iter().any(|c| {
                    let e0 = &g.edges[c[0]];
                    (e0.from.as_str(), e0.event.as_str(), e0.to.as_str()) == fk
                });
                if !dup {
                    cycles.push(cyc);
                }
            }
            Some(0) => {
                path.push(ei);
                dfs_cycle(g, adj, color, path, cycles, &to);
                path.pop();
            }
            _ => {}
        }
    }
    color_set(color, s, 2);
}

/// planner_proofs.termination
pub fn termination(g: &Graph, goals: Option<&[String]>) -> Result<Value, ReachabilityError> {
    let adj = adj_full(g);
    let terms = terminals_of(&adj); // structural; goals do NOT seed the rank
    let mut rank: Vec<(String, i64)> = Vec::new();
    if !terms.is_empty() {
        // reverse adjacency: child -> parents (may contain duplicates)
        let mut rev: Vec<(String, Vec<String>)> = Vec::new();
        for (s, es) in adj.iter() {
            for &ei in es {
                let to = g.edges[ei].to.clone();
                if let Some((_, v)) = rev.iter_mut().find(|(k, _)| k.as_str() == to) {
                    v.push(s.clone());
                } else {
                    rev.push((to, vec![s.clone()]));
                }
            }
        }
        // Multi-source BFS: every seed enters before any d+1 discovery, so
        // ranks are the minimal distance to the nearest terminal regardless
        // of seed order (the reference seeds in Python set order).
        let mut q: VecDeque<(String, i64)> = VecDeque::new();
        for t in &terms {
            rank_push(&mut rank, t, 0);
            q.push_back((t.clone(), 0));
        }
        while let Some((cur, d)) = q.pop_front() {
            let parents = match rev.iter().find(|(k, _)| k.as_str() == cur) {
                Some((_, v)) => v.clone(),
                None => Vec::new(),
            };
            for p in parents {
                if rank_get(&rank, &p).is_none() {
                    rank_push(&mut rank, &p, d + 1);
                    q.push_back((p, d + 1));
                }
            }
        }
    }
    let n = adj.len() as i64;
    for (s, _es) in adj.iter() {
        if rank_get(&rank, s).is_none() {
            rank_push(&mut rank, s, n + 1);
        }
    }

    // DFS cycle detection over adj
    let mut color: Vec<(String, u8)> = adj.iter().map(|(s, _)| (s.clone(), 0u8)).collect();
    let mut cycles: Vec<Vec<usize>> = Vec::new();
    let mut path: Vec<usize> = Vec::new();
    for (s, _es) in sorted_states(&adj) {
        if color_get(&color, &s) == Some(0) {
            dfs_cycle(g, &adj, &mut color, &mut path, &mut cycles, &s);
        }
    }

    // goals = set(goals) if goals else set()
    let goal_set: Option<&[String]> = match goals {
        Some(list) if !list.is_empty() => Some(list),
        _ => None,
    };
    let mut livelock: Vec<Vec<usize>> = Vec::new();
    for c in &cycles {
        let hits = goal_set
            .map(|gs| c.iter().any(|&ei| gs.contains(&g.edges[ei].to)))
            .unwrap_or(false);
        if !hits {
            livelock.push(c.clone());
        }
    }
    let mut task: Vec<Vec<usize>> = Vec::new();
    for c in &cycles {
        if !livelock.contains(c) {
            task.push(c.clone());
        }
    }
    let holds = if goal_set.is_none() {
        cycles.is_empty()
    } else {
        livelock.is_empty()
    };
    // watch: non-rank-decreasing edges (rank defaults to 0 in the filter,
    // values serialize to null when absent)
    let mut watch: Vec<Value> = Vec::new();
    for e in &g.edges {
        let rf = rank_get(&rank, &e.from);
        let rt = rank_get(&rank, &e.to);
        if rt.unwrap_or(0) >= rf.unwrap_or(0) {
            watch.push(json!({
                "from": &e.from,
                "event": &e.event,
                "to": &e.to,
                "rank_from": rf,
                "rank_to": rt,
            }));
        }
    }
    let cex = if !livelock.is_empty() {
        edge_json(&g.edges[livelock[0][0]])
    } else if !cycles.is_empty() {
        edge_json(&g.edges[cycles[0][0]])
    } else {
        Value::Null
    };
    let cycles_json: Vec<Vec<Value>> = cycles
        .iter()
        .map(|c| c.iter().map(|&ei| edge_json(&g.edges[ei])).collect::<Vec<Value>>())
        .collect();
    let livelock_json: Vec<Vec<Value>> = livelock
        .iter()
        .map(|c| c.iter().map(|&ei| edge_json(&g.edges[ei])).collect::<Vec<Value>>())
        .collect();
    let task_json: Vec<Vec<Value>> = task
        .iter()
        .map(|c| c.iter().map(|&ei| edge_json(&g.edges[ei])).collect::<Vec<Value>>())
        .collect();
    let mut ranks = Map::new();
    for (s, r) in &rank {
        ranks.insert(s.clone(), json!(r));
    }
    Ok(json!({
        "property": "termination",
        "holds": holds,
        "ranks": ranks,
        "counterexample": cex,
        "cycles": cycles_json,
        "livelock_cycles": livelock_json,
        "task_cycles": task_json,
        "watch": watch,
        "note": NOTE_TERMINATION,
    }))
}

/// planner_proofs.total_correctness (accepting param unused in the reference).
pub fn total_correctness(g: &Graph, goals: Option<&[String]>) -> Result<Value, ReachabilityError> {
    let live = liveness(g, None, goals)?;
    let term = termination(g, goals)?;
    let dead = deadlock_report(g, None)?;
    let dh = dead["holds"].as_bool().unwrap_or(false);
    let lh = live["holds"].as_bool().unwrap_or(false);
    let th = term["holds"].as_bool().unwrap_or(false);
    let holds = dh && lh && th;
    // Python or-chain over the three counterexamples (first non-null here;
    // no counterexample can be an empty collection in the reference).
    let cex = if !live["counterexample"].is_null() {
        live["counterexample"].clone()
    } else if !term["counterexample"].is_null() {
        term["counterexample"].clone()
    } else {
        dead["counterexample"].clone()
    };
    let goals_json = match goals {
        Some(list) if !list.is_empty() => json!(list),
        _ => json!(Vec::<Value>::new()),
    };
    Ok(json!({
        "property": "total-correctness",
        "holds": holds,
        "deadlock": dh,
        "liveness": lh,
        "termination": th,
        "goals": goals_json,
        "counterexample": cex,
    }))
}

/// planner_proofs.planner_audit (accepting param unused in the reference).
pub fn planner_audit(
    g: &Graph,
    terminals: Option<&[String]>,
    goals: Option<&[String]>,
) -> Result<Value, ReachabilityError> {
    Ok(json!({
        "deadlock": deadlock_report(g, terminals)?,
        "liveness": liveness(g, terminals, goals)?,
        "termination": termination(g, goals)?,
        "total_correctness": total_correctness(g, goals)?,
    }))
}