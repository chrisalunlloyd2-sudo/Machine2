# BDI_FSM_AGENT

**The ultimate non-LLM tool-calling super agent** — a deterministic,
mathematically-verifiable agent rebuilt from 1990s foundational AI
(BDI · Subsumption · Blackboard · FSM) and armed with the *same* decision
machinery Alan Turing used to break Naval Enigma.

> **Zero LLM / SLM. Zero model inference. Every decision is a number you can
> read, every failure is mathematically incapable of repeating, every claim is
> a test.**

| | |
|---|---|
| **Paradigms** | BDI (PRS/AgentSpeak) · Subsumption (Brooks 1986) · Blackboard (BB1/Hearsay-II) · FSM behavior trees · PRODIGY/SOAR · Oz/Hap reactive plans · Atlantis deliberator |
| **Decision kernel** | Banburismus log-odds (decibans) · Nash threshold θ★ · Enigma crib · Shannon referee |
| **Formal kernel** | Gödel-coded Ω operator dictionary · canonical AST hashing (never code twice) · weakest-precondition guards (never mistake twice) · energy-manifold Q.E.D. (zero-repeat) |
| **Core promise** | Deterministic reliability · complete mathematical explainability · every claim is a test |
| **Self-training** | Webcrawl → lexicon (syntax) + Markov corpus (semantics), dream-pruned, hot-pushed to GitHub every heartbeat |
| **State** | v0.3.0 — **405 deterministic tests green**, zero model inference |

---

## 1. The bet

LLM tool-calling is nondeterministic, slow, unverifiable, and refuses when it
should act. This agent replaces the transformer core with **hash-maps,
pattern-matching, spectral/energy math, and Bayesian evidence accumulation**:

- every decision is inspectable (a deciban score, not a softmax),
- every failure becomes a *guard* — mathematically incapable of repeating,
- every chat continuation stops at the first Shannon-entropy rise,
- every "tool-use vs. chat" choice is a log-odds hypothesis test, not a vibe.

The 1990s stack — with a **proof as its memory**.

---

## 2. The mathematics

The agent is held together by a small set of exact identities. Everything else
is bookkeeping.

### 2.1 Banburismus — log-odds evidence accumulation (decibans)

Turing scored rotor hypotheses in log-odds and let evidence *accumulate* until
one survived. The agent does the same for tool calls.

```
odds(H)   = P(H) / P(¬H)
score     = 10 · log10( odds(H) )          # decibans (dBan)

+10 dBan  = 10:1 in favour       −10 dBan  = 10:1 against
 0 dBan  = 50/50 (neutral prior)
```

Evidence updates by **addition** (that's the whole point of logs):

```
score ← score + 10 · log10( LR ),    LR = P(evidence|H) / P(evidence|¬H)
```

| P(H) | odds | dBan |
|---|---|---|
| 0.5 | 1:1 | 0 |
| 0.9 | 9:1 | +9.5 |
| 0.1 | 1:9 | −9.5 |

`LR = 0` (a crib violated, a precondition failed) → **eliminate**: score → −∞.

### 2.2 The Nash decision boundary θ★

When a hypothesis's accumulated score clears the threshold, the gate fires. The
threshold is **not a magic constant** — it is the decision-theoretic optimum
where acting and not-acting have equal expected cost:

```
θ★ = log10( C_miss / C_false )            # bans  (1 ban = 10 dBan)
θ★ = 10 · log10( C_miss / C_false )       # decibans
```

- **C_miss** — cost of wrongly *not* acting (a needed tool call missed)
- **C_false** — cost of wrongly *acting* (a tool called when it shouldn't be)

The **default** cost ratio `C_miss / C_false = 100/1` gives θ★ = **20 dBan**
(100:1 odds). This number is *derived*, never hardcoded — pass any cost ratio
and the gate self-tunes:

```
θ★(100,1) = 20 dBan     θ★(10,1) = 10 dBan     θ★(1,1) = 0 dBan
```

Firing is the point where the two expected costs cross — the **Nash equilibrium**
of the decision. Evidence concentration *is* the game reaching Nash.

### 2.3 Shannon information — the referee

Every decision is scored for information content; a zero-information step is a
wasted step.

```
H(X)   = −Σ p(x) · log2 p(x)              # entropy
rate   = H(X) / n                         # entropy rate
Ĉ(X;Y) = H(X) + H(Y) − H(X,Y)             # mutual information (capacity)
R      = 1 − H / Hmax                     # redundancy
```

### 2.4 The Enigma crib — a permutation gate

The Enigma lock (`enigma_lock.py`) is the *crib*: a no-fixed-point involution
("no letter encrypts to itself") that eliminates impossible calls *before* the
ledger scores them.

```
keyspace = 1.59 × 10²⁰  (exact)
crib search convergence:  SEC → 7 survivors,  SECRETME → 1 survivor
```

### 2.5 Gödel-coded canonical hashing — never code twice

The foundry's Ω dictionary maps operations to distinct primes; a program graph
`G = (V,E)` is canonicalized (`normalize`) and hashed:

```
H = sha256( Normalize(G) )
```

An existing hash binds a **pre-verified** node — so the agent *cannot* write
the same code twice, and language (Python/pseudo/JSON) is just a *rendering
surface* over the canonical graph.

### 2.6 Energy manifold — Q.E.D. zero-repeat

A convex energy `E₀` with Gaussian obstacle bumps `φ_obs(x_f)` at failed states
makes repeat-failure *geometrically* expensive:

```
E(x) = E₀(x) + Σ φ_obs(x_f)               # bump every failure site
S    = ⟨V_k, −∇E⟩                         # geodesic winner
A*   = c₀ σ² √e / ε                       # numerically verified (+8.49 → −334.47)
```

A failed trajectory pushes the manifold *up*, so the same path is never
geodesic again. **Q.E.D. — zero-repeat, verified numerically.**

---

## 3. Architecture — end-to-end data flow

```
                          ┌────────────────────────────────────────┐
                          │        SELF-TRAINING (heartbeat)        │
                          │  webcrawl → prose → lexicon + corpus    │
                          └───────────────┬────────────────────────┘
                                          ▼
   HUMAN (English)          ┌──────────────────────────────┐
   "please build the X" ──► │ KQML ACL: classify → achieve  │
                          └───────────────┬────────────────┘
                                          ▼
        ┌──────────────────────────────────────────────────────────┐
        │                 BDI DELIBERATION LOOP                     │
        │                                                            │
        │  Beliefs B_t ──► Options(B_t, I) ──► Filter ──► Intention  │
        │     │                                  │                   │
        │     ▼                                  ▼                   │
        │  Aiception tree              Energy manifold              │
        │  (desirability ×             S = ⟨V_k, −∇E⟩              │
        │   feasibility)               geodesic winner              │
        └───────────────┬──────────────────────────────────────────┘
                        ▼
        ┌──────────────────────────────────────────────────────────┐
        │         DETERMINISTIC FORMAL KERNEL (foundry)             │
        │  G = (V,E) over Ω · normalize · H=sha256(Normalize(G))    │
        │  dedup: existing H binds pre-verified node                │
        │  transpile T(G, python|pseudo|json)  ← language is a      │
        │                                    rendering surface       │
        └───────────────┬──────────────────────────────────────────┘
                        ▼
              ┌───────────────────┐        FAILURE ──► obstacle bump φ_obs(x_f)
              │  EXECUTION ENGINE  │──────────────────► guard ∧ ¬(fail-state)
              │  (post-check)      │                    Q.E.D.: never again
              └───────────┬───────┘
                          ▼
        ┌──────────────────────────────────────────────────────────┐
        │   JOURNAL (hash-chained) → infotheory (H, Ĉ, R) → dream  │
        │   prune (source coding) → TRAINING_LOG.md → git push      │
        └──────────────────────────────────────────────────────────┘
```

### 3.1 The Banburismus decision loop

```
world state ──► preconditions (crib filter) ──► eliminate impossible actions
                                                    │
incoming evidence ──► likelihood ratio ──► score += 10·log10(LR)  [decibans]
                                                    │
                    ledger persists across ticks ──► accumulate
                                                    │
                    score ≥ θ★ ? ──YES──► execute action ──► FSM transition
                          │                          └─► reset ledger
                          NO ──► hold state, wait for more evidence
```

### 3.2 The FSM state machine — with PLATEAU (soft-stall)

```
IDLE ──new_slot──► EVALUATE ──recipe_hit──► COMMIT
                      │  needs_mining
                      ▼
                  SYNTHESIZE ──candidates_ready──► VERIFY
                      │  none_produced                │  pass ──► COMMIT
                      ▼                               │  fail
                   BLOCKED  ◄─────────────────────────┘
                      │
                 EVALUATE ──stalled──► PLATEAU  ◄── the soft-stall state
                                         │
                    ┌────────────────────┼────────────────────┐
                    ▼                    ▼                    ▼
              expand_horizon      decompose_subgoal     commit_min_regret
                    │                    │                    │
                    └──────► EVALUATE ◄──┘               COMMIT
```

**BLOCKED** (hard terminal: no candidates / all rejected / verify failed) has
*only* `give_up`. **PLATEAU** (soft: candidates exist but fail to
differentiate) has *only* mutation exits — **never a bare retry**. The old
`BLOCKED → retry → EVALUATE` edge re-entered with an *unchanged* blackboard, so
it looped by design. It is gone.

### 3.3 Architecture regimes — each paradigm is a state, BDI selects

```
              ┌─────────────────────────────────────────────┐
              │  RegimeDriver (meta-controller)              │
              │  blackboard facts ──► select active regime    │
              └───────────────┬─────────────────────────────┘
                              ▼
   reflex │ impasse │ learn │ sequence │ agenda │ activate
      │        │        │       │          │         │
      └────────┴────────┴───────┴──────────┴─────────┘
                       │  (fallback: full stack)
                       ▼
              decide within ONLY that regime's vectors
```

This is Atlantis's deliberator + BB1's control blackboard + PRS's metalevel KAs:
the *control problem* is itself a decision, not a hardwired subsumption stack.

### 3.4 English DAG → Nash gate (fluency as a decision)

```
webcrawl ──► DefinitionStore ──► EnglishDAG (tell/achieve/ask)
                                      │  stringify candidates
                                      ▼
                              FluencyGate.score(u)
                                      │  dban vs θ★
                        ┌─────────────┴─────────────┐
                        │ ≥ θ★                      │ < θ★ (all)
                        ▼                           ▼
                 emit fluent best            emit fallback (ε short-circuit)
                                             "a robot is perfect" — never loop
```

---

## 4. The FSM plateau decision tree

```
EVALUATE
  ├─ best log-odds ≥ θ★        → COMMIT (commit_min_regret)
  ├─ candidates tie / stall    → PLATEAU
  │     ├─ expand_horizon        (fact: horizon++)
  │     ├─ decompose_subgoal     (fact: subgoal posted)
  │     └─ commit_min_regret     (fact: best committed)
  └─ none activate             → fallback foundry (brute enumerate)

INVARIANT: a PLATEAU exit MUST mutate the blackboard.
           Detection without a changed recovery = the old loop.
```

Sample rendered decision tree (from `decision_trees/latest.txt`):

```
AICEPTION DECISION TREE — 2026-08-13 23:10:41
PROBLEM: agent-decision — no local LLM or human controller active
├─ STRATEGY: route through vector stack in priority order
│  ├─ FOCUS: [1] all candidates are executable weight=1.0 grain=coarse
│  ├─ TO-DO-SET (feasible): seek_controller
│  └─ CHOSEN-ACTION: seek_controller score=1.00
  INFO-THEORETIC SELF-MODEL: H=0.000 rate=0.000 I(X;Y)=0.000 R=1.00
```

The same tree renders as **plain English** (`latest.en.txt`): *"Considering
all candidates are executable. I decided to seek_controller."*

---

## 5. Module map (all deterministic, pure stdlib, zero LLM)

### Decision core — *how it chooses*
| Module | Role |
|---|---|
| `ban.py` | Ban/hartley information accounting (1 ban = log₁₀ 10) |
| `bayes_engine.py` | BDI FSM gated by a persistent BanLedger (Nash θ★) |
| `enigma_lock.py` | Enigma permutation crib + Nash threshold |
| `certainty.py` | Certainty gate (confidence band on every choice) |
| `tool_observer.py` | Log-odds intent gate: chat vs. tool-use |
| `fsm.py` / `btree.py` | Finite-state machine + behavior trees |
| `bdi.py` / `blackboard.py` | BDI beliefs/desires/intentions + shared blackboard |
| `arch_regimes.py` / `arch_vectors.py` | Architecture-as-state meta-controller |
| `plateau.py` | **Unified PlateauDetector** — `(is_stalled, reason)` |

### Formal kernel — *why it can't repeat itself*
| Module | Role |
|---|---|
| `foundry_kernel.py` | Ω (Gödel primes) · normalize · sha256 dedup · transpiler |
| `foundry.py` | Genetic candidate foundry (produce/breed/mutate) |
| `unify.py` | Subsumption-DAG unification caching (memoized) |
| `metaplan.py` | Backward-chaining macro abduction + anti-unification |
| `exhaustive_tree.py` | Exhaustive plan-tree search |
| `nmct.py` / `nmtd.py` | Never-code-twice audit · never-mistake-twice DB |
| `energy.py` | Convex E₀ + Gaussian obstacles → geodesic (Q.E.D.) |
| `infotheory.py` | H, rate, Ĉ, R — the Shannon referee |

### Code synthesis — *how it writes*
| Module | Role |
|---|---|
| `code_patcher.py` | AST-structured validated patching + BanLedger gate |
| `rotor_codec.py` | Enigma permutation as collision-free code search |
| `rotor_codec_java.py` / `rotor_codec_html.py` | Java + HTML crib (tag/structure match) |
| `compiler/` (lexer·parser·semantic·ir·optimize·codegen·vm) | Full Front/Middle/Back-End: source → tokens → AST → IR → optimized IR → registers → assembly → VM |
| `domain_node.py` / `android_domain.py` | Domain node synthesis + Android spatial graph |
| `code_templates.py` / `action_lib.py` | Template + action libraries |

### Language & chat — *how it talks*
| Module | Role |
|---|---|
| `markov_chat.py` / `markov_plateau.py` | Entropy-stopped Markov + plateau generation |
| `chatbot90.py` | 1990s chatterbot + command-hook revival |
| `boolean_chat.py` | Boolean Q&A over learned facts |
| `kqml.py` | English ↔ KQML ACL (ask-one/achieve/insert/deny) |
| `lexicon.py` / `phonotactics.py` | 45k+ token lexicon · sonority-sequencing DFA |
| `english_dag.py` / `english_render.py` | Performative DAG → fluency gate · decision-tree → sentences |
| `corpus_seed.py` / `github_corpus.py` / `verb_flags.py` | Corpus seeding (emails + repo mirrors) · verb flags |

### Self-model & memory — *how it learns*
| Module | Role |
|---|---|
| `identity.py` | Self-model (skills, mastery, feedback) |
| `memory.py` / `journal.py` | Recipe/memory store · sha256-chained journal |
| `feedback.py` / `learning.py` | Feedback loop · recursive lexical learning |
| `dream_prune.py` | Source-coding archival (ADD-only) |
| `learning_loop.py` | Multi-trace pattern mining → SOP promotion (≥0.7) + demotion (entry/exit points) |
| `skill_library.py` / `capabilities.py` / `maslow.py` | Skills · capabilities · needs hierarchy |
| `dual_logger.py` | Dual-stream logging + pacing |

### Infra & runtime
| Module | Role |
|---|---|
| `hardened.py` | Per-platform sandbox isolation (memory cap, kill-tree) |
| `telemetry.py` / `pacing.py` | Health/telemetry · cooldowns + sequential exec |
| `daemon.py` / `controllers.py` / `control.py` | Daemon · controller discovery · Aegis control |
| `task_pool.py` / `webcrawl.py` | Task pool · paced webcrawl self-training |
| `daily_feature.py` / `brute_adapter.py` | Daily feature · brute-foundry adapter |
| `triple_loop.py` / `horizon.py` / `hap.py` | Triple learning loop · horizon · Oz reactive plans |
| `comparative_matrix.py` / `aiception.py` / `fow.py` | Spectral engine · aiception tree · fog-of-war |

---

## 6. Self-training loop (every heartbeat)

```
heartbeat ──► scripts/train_step.py ──► crawl seeds (off cooldown)
              │                            │
              │                            ├─► lexicon.mirror(prose)  (syntax)
              │                            └─► corpus/chat_corpus.jsonl (semantics)
              │
              ├─► dream_prune (archive redundant journal — source coding)
              ├─► append docs/TRAINING_LOG.md (dated, human-readable)
              └─► commit + push → training IS the progression,
                  hot-updated to GitHub every heartbeat
```

---

## 7. Quickstart

```bash
git clone https://github.com/chrisalunlloyd2-sudo/BDI_FSM_AGENT
cd BDI_FSM_AGENT
python3 -m pytest -q                        # full suite (~405 tests)
python3 scripts/train_step.py --max-pages 3 # one training heartbeat
python3 webui/server.py                     # live web UI (default port 8600)
python3 -c "
from bdi_fsm.kqml import talk
print(talk('please build the bridge')['english'])   # I will attempt to: build the bridge
"
```

---

## 8. Verification doctrine

- **Every claim is a test.** No feature ships without a matching `test_*.py`.
- **Deterministic only.** Seeded RNG, no model inference, no network in tests.
- **Q.E.D. numeric checks** in `energy.py` and `ban.py` assert the math.
- **ADD-only doctrine.** Never delete — failures become guards, successes
  become skills, heartbeats grow memory.

---

## 9. Roadmap

- [x] Formal kernel (foundry Ω + hashing + guards + transpiler)
- [x] Energy manifold + Q.E.D. zero-repeat (numerically verified)
- [x] Markov chat + entropy stopping · dream pruning · spectral matrix
- [x] KQML ACL + lexicon · webcrawl self-training + TRAINING_LOG
- [x] Banburismus decision engine + Nash θ★ (no magic constant)
- [x] Enigma lock + rotor codecs (Python / Java / HTML cribs)
- [x] Architecture regimes — each paradigm a state, BDI selects
- [x] Unified PlateauDetector + PLATEAU FSM state (mutation-only exits)
- [x] Subsumption-DAG unification caching (memoized)
- [x] Metaplan abduction (backward-chaining macro synthesis)
- [x] Precondition generalization (anti-unification on success)
- [x] English-word decision-tree rendering (sentences, not codes)
- [x] Corpus seed from self-emails + repo mirrors
- [x] Multi-agent cellular mesh (hex-grid cells, quorum voting, intent asks, search fallback)
- [x] Code organised by programming language (LangDB language index)
- [x] Never-make-code-twice vault (timestamped + language-tagged NMCT)
- [x] Never-make-mistakes-twice step recorder (NMTD step gate)
- [x] Gmail->corpus bridge (SELF-SENT emails only, strict From==To==account filter)
- [x] Atomic clock (Cloudflare epoch) + time-aware scheduler (cron)
- [x] Nightly dream cycle (dream-prune + GC + email cross-correlation + self-train)
- [x] Entity world model (sense-of-other DAGs, temporal identity, prune-as-learn)
- [x] Entity DAG backup -> private BDI_FSM_DAGs repo (scrubbed renders)
- [x] Deterministic compiler (Front/Middle/Back-End: lexer → parser → semantic → IR → optimize → codegen → VM)
- [x] Learning loop: multi-trace SOP promotion (≥0.7) + demotion path (exit point, nothing-lives-forever)
- [ ] Sophia logic ↔ FSM reachability verifier (SAT: prove you can reach the exit)
- [ ] Symbolic planner liveness/deadlock + total-correctness proofs
- [ ] Workspace heuristics + auto-repair of broken AST/type nodes

See `docs/ROADMAP.md` for versioned detail and `docs/` for the full manual set.

---

*ADD-only doctrine. Never delete. Every failure becomes a guard, every
success becomes a skill, every heartbeat grows the memory.*
