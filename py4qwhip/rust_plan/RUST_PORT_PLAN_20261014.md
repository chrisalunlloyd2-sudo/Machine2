# py4qwhip -> Rust port plan (TBD, planning only) 2026-10-14
Vision (Chris): Rust owns the metal, Python rides as the guest world; modules exportable.
State: NO rustc/cargo on this box (checked 10-14). Existing prior art: ViperCli-v2\rust_wrapper
(PyO3, lib.rs 121 LOC + resources.rs 98; PHASE_24_RUST_WRAPPER.md). Reuse that convention.
Installing the toolchain (rustup) is a download -> needs Chris's go. Not done.

## Port order (pure, deterministic, stdlib-only first; I/O-bound last)
| # | module | why | boundary |
| 1 | 01_bytespace (382 LOC) | data layer: assemble/disassemble/validate/content_hash | pure fn, no I/O |
| 2 | 02_karaka (167) | role table, JSON round trip | pure |
| 3 | 04_vm (306) Machine | hot loop; step limit + fault trapping map well to Rust | pure; IMPORT op = callback |
| 4 | envelope (alt\envelope_claude.py) | MAGIC/VER/KIND/ENDCAP/LEN/SHA256; sha2 crate | pure |
| 5 | reachability + planner_proofs graph core | BFS/SCC, no deps | pure |
| 6 | 03_synthesize | NOT first: needs code_ledger (sqlite) -> stays Python, calls Rust for hash/assemble | FFI |
Hive cells, supervisor, gateway: stay Python (guest world). Rust = libraries + later a runtime host.

## Interface
- Crate `pq` (cdylib + rlib). PyO3 module `py4qwhip_rs` exposes the same names as the Python blocks
  (assemble, content_hash, Machine.run, encode/decode) so callers swap by import, no API change.
- Also a plain C ABI + WASM target for "modular export" (phone, Redox). Decide after step 3.
- Redox: no_std core for 1-2-4-5; VM needs alloc only.

## Conformance (the gate for every port)
- golden_vectors.json (this folder): 45 skeleton content_hashes + 2 VM programs generated from the
  Python reference today. Rust must reproduce every hash byte-for-byte and every VM outs.
- Python battery (05_testrunner + extended_battery) runs against BOTH backends; watch cell reports both.
- Differential fuzz: random programs through both, compare status/outs/hash.
- A port is DONE only when: vectors match, fuzz 10k clean, battery GREEN on rust backend, Alice reviewed.

## Risks / questions for Alice
1. Hash definition: content_hash is Python-defined (canonical sha256 over what exactly?) -> freeze a
   written spec before porting, or Rust will drift.
2. marshal-based KIND_CODE in envelope is CPython-version-bound -> not portable; drop for Rust export?
3. Skeleton: marker vs fault (docstring corrected 10-14).
4. QW-7 end-cap tag fields (design note) affect the envelope layout -> decide before step 4.
Next: Chris go on rustup -> `cargo new` crate pq, port 01 against golden vectors.

## PROGRESS 10-14 (late)
- Toolchain installed: rustc/cargo 1.99.0 (rustup-init sha256 verified vs static.rust-lang.org). Build in PowerShell
  (Git Bash resolves coreutils `link` before MSVC link.exe).
- STEP 1 DONE: crate rust\pq (src\lib.rs): assemble + validate + canonical_bytes + content_hash.
  cargo test: 3/3 -- 45 skeleton hashes + 2 VM programs + 200 fuzz-corpus programs byte-identical to Python.
- Fuzz-driven spec fixes made in Python FIRST (the Rust port mirrors these): validate jump base = next instruction,
  target may equal len(code); disassemble same base + end label; VM ints are i64 with overflow trap; MUL on
  str/bytes traps; operand-type errors trap as fault "trap:<TypeName>"; LOAD_LOCAL/STORE_LOCAL fixed (rd() was undefined).
- NEXT: port 02_karaka, then 04_vm Machine (status/outs/fault strings vs fuzz_corpus.json), then envelope.

## PROGRESS 10-16
- STEP 4 (envelope) DONE pending Alice review: src\envelope.rs (MAGIC/VER/KIND/ENDCAP/LEN/SHA256, 50B header,
  endcap OUTSIDE the digest -- QW-7 slot preserved) wired into lib.rs; tests\envelope_golden.rs consumes
  rust_plan\envelope_golden.json (blobs byte-for-byte + exact Python error strings, errors mirror b06 text).
  Fresh full-link build: 13/13 GREEN (envelope golden 3, golden 3, karaka 2, vm_conformance 3, lib 2).
- LINKER (extends the 10-14 PowerShell note): PowerShell spawned FROM Git Bash also fails (inherits Git PATH;
  with Git stripped, all MSVC paths vanish). Only working env = VS 2026 Insiders dev shell:
  "C:\Program Files\Microsoft Visual Studio\18\Insiders\Common7\Tools\Launch-VsDevShell.ps1"
  -VsInstallationPath "C:\Program Files\Microsoft Visual Studio\18\Insiders" -Arch amd64 -HostArch amd64
  with Git\usr\bin + Git\mingw64\bin stripped from PATH first (coreutils link.exe shadow). LIB resolves to
  NETFXSDK + SDK\ScopeCppSDK\vc15\{SDK\lib, VC\lib} -- the scope SDK is this box's only ucrt/msvcrt store
  (there is NO Windows Kits\10; vswhere registers no instance). Driver: rust_plan\cargo_test_vsdevshell.ps1.
- NEXT: step 5 (reachability + graph core) if Chris says go; Q1-Q4 + port review stay with Alice.

## PROGRESS 10-16 (step 5)
- STEP 5 core DONE pending Alice review: src\graph.rs — tokenize_formula / shunting_yard / truth_table /
  guard_verdict + path_to / verify_path / prove_exit (reachability.py) + deadlock_report / liveness /
  termination / total_correctness / planner_audit (planner_proofs.py), wired as pub mod graph in lib.rs.
  tests\graph_golden.rs consumes rust_plan\graph_golden.json: 19 formula cases + 35 graph ops (vm_status 8, guarded_loop 7,
 unsat_blocked 4, no_terminals 5, paths 6, unsat_only 5) — result objects compare as
  parsed JSON (serde Value equality, key order free), error strings byte-for-byte ("mismatched parens",
  "unexpected char {c!r} at {i} in {f!r}", "malformed formula {f!r}: pop from empty list" /
  "list index out of range"). Fresh driver run: 15/15 GREEN (was 13/13).
- Fidelity pins (from the vectors): canonical edge order is GROUPED BY FROM-STATE (mk's
  trans.setdefault(state,{})[event] collapsed then re-flattened by _fsm_edges) — raw list order diverges
  for interleaved from-states (caught by guarded_loop 'watch'); liveness goals-truthiness vs
  terminals-emptiness distinction (liveness(f, goals=[]) falls through to auto-terminals);
  path_to default depth = max(#source-states+1, 32); termination rank = multi-source BFS to nearest
  structural terminal (goals never seed the rank); Python-callable guards unrepresentable over JSON
  (RUNTIME branch absent by construction, documented in graph.rs header).
- NEXT: differential fuzz extension for the graph ops (the plan's fuzz gate) + batteries, then steps:
  Alice review; step 6 stays Python-side FFI.
- STEP 5 FUZZ GATE RUNNING (10-16): pq05_fuzz_gen_v1.py (rust_plan, mirrors the golden generator exactly:
  ERR tuple = (rc.ReachabilityError, IndexError, KeyError, ValueError), Duck/mk collapse, run_op shape,
  G1-G6 verbatim anchors + falsy-chain stress, rest seeded-random SEED 20261016) -> graph_fuzz_corpus.json
  (5,000 formula + 5,000 graph cases, 12,645 ops, 2,759 exercising error paths). tests\graph_fuzz.rs replays
  it against src\graph.rs with the same differential rule. FIRST DRIVER RUN: formulas 5,000/5,000 byte-exact;
  graphs diverged ONCE — fz00008 audit.
- FUZZ BUG #1 (found+fixed 10-16): planner_proofs deadlock loop `live_edges = [e for e in es if
  _edge_can_fire(...)]` is a list comprehension — it evaluates EVERY guard in list order (no short-circuit),
  so a malformed guard RAISES even when an earlier edge already fired (fz00008: '' guard raised
  "malformed formula '': list index out of range" out of audit; Rust broke at the first fireable edge and
  swallowed it). Fix: graph.rs deadlock_report drops the break (liveness/symbolic_reaches short-circuit
  faithfully via `and`/`or` short-circuiting; they were already correct). Re-run after fix: FULL DRIVER GREEN,
  17/17 (graph_fuzz 2 + graph_golden 2 + envelope 3 + golden 3 + karaka 2 + vm_conformance 3 + lib 2 + doc 0)
  — fuzz corpus GREEN against the port; step-5 core re-verified by regression.
- DONE GATE FULLY CLOSED (10-16, same span): batteries GREEN — blocks\05_testrunner.py 8/8
  (01-04, 06-09) + tests\extended_battery.py 7/7 (side-effect-free battery, all checks true).
  Alice package: projects\py4qwhip\reviews\graph_port_step5_alice_package.md (4 questions:
  deadlock-bar accept; step-6 FFI confirm; corpus keep-vs-regenerate; ledger lineage).
  Delivered: micro_email.emit staged id 20261016-222814 (spool line verified, vault .md
  written, source=py4qwhip); hourly flusher sends (~23:19 next eligible; not force-flushed).
  Ledger: 8754 port, 8755 golden test, 8756 fuzz test, 8757 corpus generator.
  Step 5 PENDING ONLY: Alice ruling. Step 6 (synthesize) Python-side FFI per plan.
- STEP 6 DECISION (10-18): FFI mechanism = C-ABI + serde_json + ctypes (NOT pyo3).
  No new crates; no Python-ABI build coupling; JSON I/O byte-goldenable by the same
  differential method as step 5. Swap shape: FILE-LEVEL — 01_bytespace.py becomes the
  wrapper, because blocks bind it via importlib file-path loading (_load_local,
  03_synthesize.py L50: "01_bytespace.py" as "pq4_b01"), not import statements; the
  loader keeps picking the same filename and every consumer call site stays
  byte-identical with ZERO edits. Surface consumers touch: assemble, content_hash,
  validate, OPS (03/04/07/08/09 + tests/vm_graph_proof.py).
  Boundary pins (full source re-read 10-18, 01_bytespace.py 385 lines):
  - a3 "'5' vs 5 -> [5]" = PARSE-TIME coercion (L225 `int(a) if a.lstrip("-").isdigit()`
    after quote-strip), NOT a dedupe-side transform; pool dedupe is type-gated
    (type(existing) is type(v), L204); bool dedupes separately from int (a4) but
    canonicalizes to "i" int at canonical_pool_value (bool-listed first, L95).
  - Canonical layout: MAGIC + <B version + <H utf8-name-len + name + <B nlocals +
    <H pool-len + per-value (<B tag, <I payload-len, payload) + <I code-len + code
    (tags i=0,s=1,b=2,f=3). content_hash = sha256(canonical_bytes).hexdigest()[:16]
    — lib.rs content_hash currently returns 8 chars: DIVERGENCE to fix in the seam.
  - validate() (pre-walk, canonical): magic/version-mismatch/nlocals out of range
    (0..=255)/const pool too large (>MAX_POOL+1=65536)/pool type check/bad opcode/truncated
    instruction/reg>=nlocals/const idx out of pool/jump target out of program
    (base = NEXT instruction; == len(code) allowed). canonical_bytes validates magic ONLY.
  - struct.error pack overflows fire ONLY inside canonical_bytes (assemble admits then):
    pool 65536 -> 'ushort format requires 0 <= number <= 65535' at <H; big int ->
    'argument out of range' at <q; nlocals int() TypeError carries Python's exact message.
  - Uncaught-error seam: invalid reg token -> plain int() ValueError/TypeError
    (L220 `int(a)`, reg_or L200 `int(tok[1:])`), NOT BytespaceError — shim must
    reproduce the exact Python exception TYPE + message per error kind.
  - Probe battery authoritative blob: session 20261009_161334_603e96, call_9b0dek4r
    (default= serializer; supersedes te53tz3t/h35hhhn1/tkle0kbl).
