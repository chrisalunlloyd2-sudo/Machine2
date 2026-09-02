# Programmatic Meaning

**Reducing programming to its fundamental physics: Data Transformation and
Control Flow.** Every language — Python, Rust, Go, SQL, or a server config file —
uses the same core operations. Syntax changes; the underlying topology is
identical. This document defines that topology and the algebraic substrate for
reasoning over it, wired into `BDI_FSM_AGENT` as deterministic, zero-LLM code.

> Implementation: `bdi_fsm/topology.py` (8-vector mapper), `bdi_fsm/hdc.py`
> (vector symbolic algebra), `bdi_fsm/enigma_lock.py` (Nash threshold).

---

## 1. The 8-Vector Universal Code Topology

Every human concept (sensory or conversational) maps cleanly to one of eight
Universal Programmatic Actions. A line of code is *classified into a set* of
these vectors (a line can do several things at once).

```
                        [0] ALLOCATE (Creation / Birth)
                                  ▲
                                  │
     [7] LISTEN (Input) ◄─────────┼──────────► [1] EMIT (Output / Talk)
                                  │
                                  ▼
                         [4] PURGE (Destruction)
```

| Vector | Programmatic Meaning | Human / Sensory Analog | Syntax Manifestations |
|--------|----------------------|------------------------|------------------------|
| 0 ALLOCATE | Instantiation, reservation | birth, create, spawn, imagine | `let`, `var`, `malloc`, `NEW`, `CREATE TABLE` |
| 1 EMIT | Output, broadcasting | speak, show, shine, write | `print()`, `console.log`, `return`, `RESP.WRITE` |
| 2 TRANSITION | Mutation, state shift | move, walk, change, paint | `=`, `+=`, `UPDATE`, `set()` |
| 3 EVALUATE | Conditional, comparison | decide, feel, check, taste | `if`, `switch`, `WHERE`, `match`, `filter()` |
| 4 PURGE | Garbage collection, destruction | delete, die, forget, eat | `del`, `free()`, `DROP`, `exit()` |
| 5 BIND | Coupling, linking, import | connect, touch, marry, grab | `import`, `require`, `JOIN`, `include` |
| 6 LOOP | Iteration, continuous execution | pulse, breathe, repeat, walk | `for`, `while`, `LOOP`, `setInterval` |
| 7 LISTEN | Ingestion, listening, reading | hear, see, smell, receive | `input()`, `READ`, `FETCH`, `ON_EVENT` |

### Precedence correctness (a bug fixed from the original sketch)

A naive regex scan classifies `if x == y` as **TRANSITION** because bare `=`
matches inside `==`. The fixed mapper uses a lookbehind/lookahead so bare
assignment `(?<![=!<>+\-*/%&|^])=(?!=)` excludes `==`, `!=`, `<=`, `>=` and
compound assignments, while `==`, `!=`, `<=`, `>=` map to **EVALUATE**.

```python
from bdi_fsm.topology import map_code_line
map_code_line("if x == y:")   # -> (3,)  EVALUATE, never TRANSITION
map_code_line("x = 5")        # -> (2,)  TRANSITION
map_code_line("x = input()")  # -> (2, 7) TRANSITION + LISTEN
```

### Deterministic identity

`line_hash` uses **sha256**, not Python's `hash()` (which is salted per-process
via `PYTHONHASHSEED`). Identical code yields an identical signature — the
precondition for "never make code twice".

### Sensory stripping

Human metaphors are intercepted and stripped of emotional bloat, leaving only
the raw operation vector:

```python
from bdi_fsm.topology import map_concept_word
map_concept_word("eat")    # -> 4  PURGE   ("eating the memory")
map_concept_word("touch")  # -> 5  BIND    ("touching the database")
map_concept_word("hear")   # -> 7  LISTEN  ("listening to the socket")
map_concept_word("speak")  # -> 1  EMIT    ("the server speaks")
```

---

## 2. Hyperdimensional Computing (HDC) — Vector Symbolic Architecture

Instead of treating code as a string or AST, HDC maps symbols into fixed-dimension
bipolar hypervectors `x ∈ {-1,+1}^D` (D = 10,000). Information is distributed
across all coordinates — resilient to noise, and real-time genetic operations
(crossover, structural audit) become matrix addition on one core, bypassing
tokenization.

### The three primitive operators (Multiply-Add-Permute)

**Bind (⊗) — Hadamard product** — associates a role with a filler:
`x_bound = x_role ⊗ x_filler`. Invertible: `x_filler ≈ x_bound ⊗ x_role`
(since `x ⊗ x = 1`).

**Bundle (⊕) — majority vote** — superposes constituents into one signature
representing a module or directory: `X_module = ⊕ᵢ xᵢ`. Stays similar to all
constituents.

**Permute (Π) — cyclic shift** — encodes sequence/order; a single shift renders
`Π(x)` orthogonal to `x`, capturing execution order without graph nodes.

```python
from bdi_fsm.hdc import Hypervector, code_signature
x = Hypervector.from_string("role", 256)
y = Hypervector.from_string("filler", 256)
(x.bind(y).bind(y)).cosine(x)   # 1.0  (bind is self-inverse)
code_signature(code)            # n-gram + positional permute + bundle -> signature
```

---

## 3. Computational Coding Bans — the Nash Gate (no magic 0.50)

The naive approach thresholds inner-product similarity at a fixed `0.50`. That
is a magic constant. The agent already carries the correct adaptive decision
rule: **theta\* = log₁₀(C_miss / C_false) bans** (`enigma_lock.nash_threshold`),
the decision-theoretic point where acting and not-acting have equal expected
cost.

Cosine similarity `s ∈ [-1, 1]` is mapped monotonically to log-odds (bans) via a
logit, then gated on theta\*:

```
similarity_ban(s) = 10 · log10( (1 + s) / (1 − s) )
same_code  ⟺  similarity_ban(s) ≥ nash_threshold(C_miss, C_false)
```

The old `0.50` cutoff corresponds to ≈ **4.77 bans**. By replacing it with the
cost-parameterized threshold, the *same* act-law that decides "act vs. don't
act" decides "same code vs. different code".

```python
from bdi_fsm.hdc import CodeSignatureStore
store = CodeSignatureStore(D=2048, c_miss=1000.0, c_false=1.0)
store.add("mod_1", code)
store.lookup(code)  # {"duplicate": True, "best_similarity": 1.0, "ban": 63.01}
```

---

## 4. One Algebra, Four Subsystems (the unification)

The HDC operators and the deciban gate are the same objects the agent already
uses, expressed in a new basis:

| HDC operator | Existing subsystem |
|--------------|---------------------|
| **Permute** (cyclic shift) | the **Enigma rotor step** (`rotor_codec`) |
| **Bundle** (majority vote) | **memory consolidation** (`dream_prune`, `asymptotic` knee-prune) |
| **Bind** (Hadamard) | **code/filler association** (NMCT slot → code, `pos_db` verb→noun) |
| **cosine + Nash threshold** | the **deciban act-law** (`BanLedger`, `nash_threshold`) |

"Never make code twice" (NMCT) and "never make mistakes twice" (NMTD) become a
single vector-similarity lookup gated by theta\*. Input DAGs (entity graphs,
task DAGs) project into the same hyperspace, so *code meaning* and *conversation
meaning* share one substrate — the coupling Chris's "smarter = better across all
domains" hypothesis requires.

### The 30-step matrix (summary)

Phase 1 (1–10) **ingestion**: allocate D=10,000 bipolar space, map paths/n-grams
to hypervectors, bundle to module signatures, normalize to bipolar, log to the
ledger. Phase 2 (11–20) **comparison**: load target vectors, cosine-project
candidates, flag hallucinated (low-similarity) prose, rank, cross over the top
two parents, unbind to source. Phase 3 (21–30) **deploy**: render TUI, commit the
unbound code via buffered write, compile, evict cache. (See the vector-algebra
Rust reference in the architecture notes.)
