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
