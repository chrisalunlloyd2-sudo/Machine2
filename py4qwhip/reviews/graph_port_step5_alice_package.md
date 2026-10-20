# Alice review package: py4qwhip rust pq — step-5 graph-op port (Hermes, 10-16)
Scope: port of BDI_FSM_AGENT reachability.py + planner_proofs.py into the pq crate.
Nothing applied to live code: new module + tests only, no production wiring touched.

| artifact | path | size | state |
|---|---|---|---|
| port module | rust\pq\src\graph.rs | 1,015 LOC | compiles clean, 17/17 |
| golden conformance | rust\pq\tests\graph_golden.rs | 220 LOC | 2/2 GREEN |
| fuzz differential | rust\pq\tests\graph_fuzz.rs | 242 LOC | 2/2 GREEN |
| corpus generator | rust_plan\pq05_fuzz_gen_v1.py | 365 LOC | ran clean PY311 -I |
| fuzz corpus | rust_plan\graph_fuzz_corpus.json | 7.2 MB | 10k cases, 12,645 ops |

Gates closed (DONE gate: vectors match, fuzz 10k clean, battery GREEN, Alice review)
- vectors: graph_golden.json — 19 formula cases + 35 graph ops byte-exact
  (error strings byte-for-byte; result JSON compared as parsed objects, key order free).
- fuzz: 10,000-case corpus (5,000 formula + 5,000 graph) generated against the live
  reference, exact same harness as the golden generator (ERR tuple, Duck/mk collapse,
  run op shapes); formula side byte-exact first try; graph side diverged ONCE.
- bug found by fuzz, fixed: planner_proofs deadlock_report evaluates EVERY guard of a
  state (list comprehension, no short-circuit); a malformed guard raises even when an
  earlier edge already fired (fz00008 audit, '' guard). Port had a break-at-first-fire
  — dropped the break. Golden regression stayed green after the fix.
- batteries: blocks\05_testrunner.py GREEN 8/8; tests\extended_battery.py GREEN 7/7.
- full driver: 17/17 GREEN (graph_fuzz 2 + graph_golden 2 + envelope 3 + golden 3 +
  karaka 2 + vm_conformance 3 + lib 2).

Prior art: code_ledger 1728 vm.py, 5076 bytecode_normalizer, 1956 foundry_debugger;
new submissions 8754 pq_graph_ops_rust_port, 8755 pq_graph_golden_test,
8756 pq_graph_fuzz_test, 8757 pq05_fuzz_gen_v1 (search 'fuzz' -> 8756).
Seams: local only, stdlib + serde_json, no network, no model calls; writes only to
code ledger + rust_plan artifacts. Corpus exclusions documented (zero-edge FSMs crash
reference liveness outside ERR tuple; duplicate (from,event) pairs overwrite in mk();
None goals are nonsense calls only).

Questions for Alice:
1. Accept the corrected no-short-circuit deadlock semantics (matches reference lines
   67/49, verified by 10k-differential) as the step-5 fidelity bar?
2. Step 6 (synthesize) stays Python-side FFI per plan — confirm, or port to Rust?
3. Corpus artifacts (graph_fuzz_corpus.json 7.2 MB + generator): keep on disk as
   fixed vectors, or regenerate per run? Rust test panics with a pointed message
   when the corpus is absent, so regeneration is a one-command step.
4. Envelope/karaka/vm Rust modules predate this span — fold into the same ledger
   lineage (8754) or separate entries per module going forward?
Delivery: micro_email.emit staged (source=py4qwhip); hourly flusher carries it.