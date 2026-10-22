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

## PROGRESS 10-19 (spans F-H: CB-1 fix, full C-ABI parity, git/backup v2)

- ROUNDTRIP BREAK found: pq_program_json -> pq_content_hash_json FAILED for
  PADDED base64 payloads ("AQAAAA4=" rebuilt as "AQAAAAA="): b64_decode consumed
  the trailing 4-char tail with the low-bit packing only correct for UNPADDED
  input. NEW decode = min(4, body_end - i) take-loop (take<2 -> None); encode
  side untouched. Patched by b64fix_apply.py (latin-1 splice, CRLF anchors in
  lib.rs, assert count==1); rebuild EXIT 0; 8/8 content_hash parity (CB-1
  CLOSED); 17/17 GREEN (run #10). Commit eb0a696 -> 15837c0 (only lib.rs
  staged; dll is NOT git-tracked - build artifact, carried by backup zips).
- FULL C-ABI PARITY PROVEN on pq_probe4.dll (fresh scratch copy): validate 6/6
  byte-exact + None-on-success; content_hash 8/8; assemble errors 13/13;
  const-kinds 9/9; wire roundtrip identity. Live exports (8): pq_version,
  pq_abi_version, pq_ops_json, pq_assemble_json, pq_validate_json,
  pq_content_hash_json, pq_free, pq_program_json. NO disassemble /
  canonical_bytes exports (wrapper keeps those pure Python).
- Backup v2 = pq_port_backup_20261019_190650.zip (49 entries, testzip OK).

## PROGRESS 10-19..20 (spans I-K: b01 recon + wire map, all landed)

- 09 re-hydration RESOLVED: 09 -> b07.program_from_text (07_qgrant.py L59,
  Latin-1) re-encodes `code` to text; 09's only b01 use = validate(prog).
- b01 385/385 lines mapped via latin-1 numbered disk-log reads (escape-rich
  text defeats read_file clipping). census open(p,"rb"): b01 PURE LF; lib.rs
  PURE CRLF; vm/graph/envelope/karaka/golden.rs PURE LF; vm_conformance CRLF.
- struct.error origin = L124 struct.pack("<q", val) in canonical_bytes -> the
  huge-int lane keeps content_hash/validate PURE PYTHON; assemble rebuilds
  b01-exact pool values from the wire echo (bool->z lane, f->"0x%016x" bits).
- WIRE MAP COMPLETE (no remaining holes): pos+neg huge ints echo as
  {"t":"B","v":"<decimal>"} both accepted; dedupe (type+value) matches both
  directions (bool <> int 1 separate); dll STRICTER on name/text/nlocals types
  (b01 natural AttributeError/TypeError -> route gate); pool-cap: dll accepts
  65537 const_extra, b01's own trailing validate(prog) raises
  "const pool too large" (L237) - dll lane must call validate(prog) on the
  rebuilt dict explicitly; 300-ch name error pin VOID (both accept long names).

## PROGRESS 10-20 (span L: wrapper APPLIED + PROVEN, milestone 4)

- Wrapper write: pristine b01 copy -> scratch pq_b01_pristine.py
  (14,608 B / 385 LF / sha256 1a72...; exact sha in backup meta). Applier
  (latin-1 splice, anchor "    labels: Dict[str, int] = {}" 4-indent,
  count==1 assert, CR asserts 3x, py_compile doraise) -> 88-line WRAPPER_BLOCK
  spliced before L162; live b01 now 473+ lines. Payload composition:
  route gate (text str + name str + utf-8 encodable + nlocals non-bool int +
  const_extra elements typed) -> ctypes pq_assemble_json -> rebuild pool
  echo (z->bool, i->int, B->int(dec-str), f->>d bits, b->bytes, s->str) ->
  validate(prog) on rebuilt dict -> return; ANY dll refusal prints stderr
  note + falls through to the VERBATIM pure-Python body -> native
  AttributeError/TypeError/ValueError/BytespaceError fidelity by
  construction (bad-reg ValueError proven on a dll-refused case).
- FIXES during battery authoring: (1) wrapper referenced undeclared
  module-level base64 -> lane-local imports (base64/ctypes/sys). (2) float
  rebuild used struct.unpack("<d", bytes.fromhex(hx)) - fromhex is
  big-endian; correct unpack is ">d" (battery caught 3.5 -> 1.55e-320).
- DIFFERENTIAL BATTERY 27/27 (pq4_battery.py, PY311 -I): all fallback rows
  exception-identical pristine vs wrapped; routed rows pool/hash identical;
  dl<->py hash agreement; pool caps 65536 ("const pool overflow") / 65537
  ("const pool too large"); struct.error text EXACT "error:argument out of
  range" (struct.error.__name__ == "error" - grep gotcha); jumps corpus,
  surrogate/None rows, selftest rc=0. 03_synthesize consumer battery: 8/8
  GREEN, all blocks true; six b01 consumers import cleanly; b01
  selftest rc=0.
- MILESTONE 4 runbook: commit ac0e626 pushed (parent 15837c0; 95 insertions,
  b01 only). Backup v3 =
  pq_port_backup_20261020_final.zip (61 entries, testzip OK, no dups, v2
  members carried byte-exact; interim zips removed; meta carries commit +
  pristine sha). GIT-3 CLOSED: dll never git-tracked (all 3 commits).
- RESIDUAL: DOC-1 this update; scratch probe dlls pq_probe*.dll (delete when
  kernel session ends); Alice step-2/step-5 rulings still external.

## PROGRESS 10-21 (spans M-P: 04_vm Machine file-level wrapper, milestone 5)

- RUST LANE (vm.rs 731 -> 945 LF, sha b959a10a): 214-line lane at EOF —
  Machine::from_snapshot(prog: Program, snap) with error strings
  "snapshot missing 'pc'/'steps'/'max_steps'"; lane_* fns collision-free
  (D218); TAGGED codec both directions incl. Val::None -> {"t":"n","v":null}
  (D230, b01 lane has no n arm); run() semantics mirror Python (steps
  POST-increment, step_limit_exceeded, trap:"TypeName", i64 gate, pool
  natives pool-form). lib.rs +28 (D228, 848 lines): program_from_json
  (name/nlocals 0..=255/const_pool TAGGED/code_b64 -> Program, D217) +
  28-line pq_vm_run_json export at L814-841. build2 GREEN; full suite
  17/17 + vm_conformance GREEN; dll 413,184 B. Census proven: 2 files,
  +214/+28 (pq_vm_splice_gitdiff.txt).
- PYTHON WRAPPER (blocks\04_vm.py 16,281 -> 24,493 B, PURE CRLF, 519
  lines, sha256 1d3a9d0df4ba9fe6): Machine.run() route gate (program dict:
  name str + utf-8-probeable ALL request strings D234 + nlocals + code
  bytes + pool/regs/outs typed) -> ctypes pq_vm_run_json 9-field TAGGED
  request (pool from live self.pool, constructor-backed) -> 6-key snapshot
  synced INTO self.* (pc/steps/status/fault/pending_import/outs->self._outs/
  regs; synth_retries NOT synced, D229) -> return snapshot; missing-dll/
  null-ptr/dll-refusal -> D168 stderr note + VERBATIM pure-Python
  fall-through; _lib cached on Machine.run (D233); pc = returned final pc,
  resume loop applies +4 Python-side.
- DRY-RUN GATE: temp-copy splice BEFORE real write (pristine sha assert ->
  CRLF anchor count==1 -> block LF assert -> LF->CRLF convert 158 pairs ->
  py_compile + dll smoke in mirror trees — smoke caught the tree-depth dll
  hunt: both lanes walk dirname(dirname(__file__)), converge on
  py4qwhip\rust\pq\target\release\pq.dll in the real tree). write_file
  strips trailing newline -> block final line join is explicit \r\n.
- DIFFERENTIAL BATTERY 22/22 (pq4_vm_battery2.py, PY311 -I): 19 run cases
  (arith, label-loop, branches, float, bool, bytes, strcat, bignum,
  import-pending, traps, step-limit, fall-through routes, nlocals 255)
  identical 6-key dict AND identical machine attrs; ctor exceptions
  identical; selftest parity (resolve_and_run composes with wrapped run).
  b01 jump operands are LABELS (name: lines); None routes via load_local
  (not a legal const).
- CONSUMERS on wrapped 04_vm: extended 7/7; fuzz 2,000-case 0-bad;
  gen_vm_edge_corpus 414 regenerated byte-identical (determinism);
  vm_graph_proof 6/6 @ 501 runs; b01 battery 27/27; 03 unreferenced.
- MILESTONE 5 runbook: commit d70b80f pushed (parent 0a8b57f; 3 files:
  04_vm +159, vm.rs +214, lib.rs +28). Backup v4 =
  pq_port_backup_20261021_v4.zip (95 entries = v3 floor 61 carried + 34
  tree members; pq.dll member = current 413,184 B build; testzip OK;
  v1/v2/v3 untouched).
- NEXT: 02_karaka file-level wrapper (port-order #2; karaka.rs goldens
  already in the Rust suite); Alice open rulings external (step-2/step-5 +
  Alice package pq4_b01_wrapper_alice_package.md, emit staged
  20261020-181628, unsent).
