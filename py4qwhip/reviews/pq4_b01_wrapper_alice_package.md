# ALICE REVIEW PACKAGE 2026-10-20 - py4qwhip pq4 b01 file-level wrapper (Hermes)
Ruling file for: this package. Nothing applied beyond blocks\01_bytespace.py @ commit ac0e626
(prior snapshot also recorded in code ledger row 9026; 8754-8757 untouched).
WHAT: 88-line WRAPPER_BLOCK spliced into blocks\01_bytespace.py before the assemble() body
(anchor 0-idx 161; pristine 385 lines / 14,608 B / sha 1a72a8f6fbefbd17 kept on scratch).
Assemble() delegates to pq.dll C-ABI (ctypes + serde_json wire) IFF text/name are str,
utf-8-encodable, nlocals a non-bool int, and every const_extra element is typed; rebuilds
the b01-exact const pool from the wire echo (z->bool, i->int, B->int(decimal), f->'>d'
bits - bytes.fromhex is big-endian, the battery caught '<d' transposition - b->bytes,
s->str), revalidates, returns. ANY dll refusal prints a stderr note and falls through to
the VERBATIM pure-Python body -> native exception fidelity by construction (proven:
bad-register ValueError raised on a dll-refused vector). Zero call-site edits.
WHY: step-6 FILE-LEVEL swap per plan (03 synthesize stays Python; Alice 10-16 Q2 CONFIRM
honored - this is Python-side FFI, not a synthesize port).
TESTS: differential battery pristine-vs-wrapped 27/27 GREEN (exception texts byte-exact;
pool caps 65536/65537; struct.error text 'error:argument out of range' - its __name__ is
literally 'error'); 03_synthesize consumer battery 8/8; b01 selftest rc=0; six consumers
import cleanly; content-hash agreement dll<->pristine<->wrapped.
KNOWN DIVERGENCE (1, design-proven): pool cap - dll accepts 65537 const_extra while b01
raises from its own trailing validate(prog); the routed path calls validate on the rebuilt
dict, so observed behavior matches b01.
ASKS: (1) accept/reject the delegation + fall-through pattern; (2) confirm the battery
scope is a sufficient fidelity bar for a file-level swap; (3) flag anything owed on row
9026 before any further Rust-side growth.
