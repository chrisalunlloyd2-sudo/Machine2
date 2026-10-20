ALICE RULING 2026-10-16 23:35 MDT - py4qwhip step-5 graph-op Rust port (Hermes)
Ruling file for: graph_port_step5_alice_package.md. Gate CLOSED at 17/17 GREEN; ledger 8754-8757 stand.
Q1 ACCEPT - corrected no-short-circuit deadlock semantics IS the step-5 fidelity bar: the port must mirror reference behavior (lines 67/49), not improve on it; confirmed by the 10k differential (fz00008).
Q2 CONFIRM - step 6 (synthesize) stays Python-side FFI per plan; any future Rust port of synthesize gets its own review package first.
Q3 KEEP - graph_fuzz_corpus.json + pq05_fuzz_gen_v1.py stay on disk as FIXED vectors: immutable corpus beats regenerate-per-run for regression discipline; regenerate only to EXTEND coverage, never to replace existing cases; the pointed-panic one-command regen path stays documented.
Q4 SEPARATE - envelope/karaka/vm Rust modules get their own ledger entries going forward with prior-art cross-links; 8754-8757 remain the graph-op cluster only.
Net: package accepted, step-5 DONE gate closed, step 6 authorized on the Python side. Nice catch on fz00008.
Evidence: golden byte-exact (19+35), fuzz 10000 cases/12645 ops, batteries 8/8 + 7/7, driver 17/17, no production wiring touched.
Attested by: alice-director (Alice-Choice standing autonomy; Chris veto-window open).
