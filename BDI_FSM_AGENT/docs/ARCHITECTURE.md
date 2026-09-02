# Architecture

## 1. The 4-layer stack (1990s foundational paradigms)

```
┌───────────────────────────────────────────────────────────┐
│  Layer 4: BDI Goal Planner                                │
│  (Generates High-Level Desires & Tool Plans)              │
├───────────────────────────────────────────────────────────┤
│  Layer 3: Subsumption Arbiter                             │
│  (Real-time Priority Inhibition & Override)               │
├───────────────────────────────────────────────────────────┤
│  Layer 2: Shared Blackboard Store                         │
│  (Global Event/State Bus & Inter-Module KV)               │
├───────────────────────────────────────────────────────────┤
│  Layer 1: Reactive Behaviors / FSM                        │
│  (Direct Tool Execution, Input/Output Handlers)           │
└───────────────────────────────────────────────────────────┘
```

### Layer 1 — Reactive behaviors / FSM (`fsm.py`)
Deterministic finite state machine. States: IDLE → EVALUATE → SYNTHESIZE →
VERIFY → COMMIT → WAIT_AEGIS → IDLE — with **BLOCKED** (hard terminal: no
candidates/all-rejected/verify-fail, `give_up` only) and **PLATEAU** (soft stall:
candidates exist but don't differentiate, mutation-only exits `expand_horizon` /
`decompose_subgoal` / `commit_min_regret`). Every
transition is a guarded, pure function of blackboard facts. No inference.

### Layer 2 — Shared blackboard (`blackboard.py`)
BB1/Hearsay-II style global bus: facts (beliefs), event register, plan
fitness scores. Domain handlers post tool outputs and read triggered events
without direct coupling. Bounded event log (default 500).

### Layer 3 — Subsumption arbiter (`bdi.py`)
Higher-priority plans inhibit lower-priority reactive plans. The plan
library is sorted by `priority` (lower number wins). Critical safety layers
(e.g. rule gate, sandbox verify) always take precedence over routine
reactive behaviors. This is Rodney Brooks' inhibition control made explicit.

### Layer 4 — BDI goal planner (`bdi.py`)
- **Beliefs** — blackboard facts (AST state, file trees, test exit codes)
- **Desires** — high-level goals (`resolve_slot`, `fix_syntax`, ...)
- **Intentions** — active plans: `precondition → tool action → postcondition`
  selected to achieve a desire. Plan library = the rules engine that
  replaces LLM reasoning.

## 2. The ToK memory harness (control layer)

```
[ Unresolved AST Hole ]
        │
        ▼
1. Memory Harness: Scope & Recipe Pre-Filter
   (learnings.md rules + NMCT Vault + Recipe Book)
        │
   ┌────┴─────┐
   ▼          ▼
[ Recipe ]  [ No Recipe ]
   │          │
   ▼          ▼
Hydrate    Brute Foundry
skeleton   mines candidates
   │          │
   └────┬─────┘
        ▼
2. Rule Gate — filter candidates against learnings.md
        ▼
3. Hardened sandbox race (CoW overlay, RLIMIT, timeout→124)
   ┌─────┴─────┐
   ▼           ▼
[ Exit 0 ]  [ All fail ]
   │           │
   ▼           ▼
Seal NMCT   NMTD incident +
vault +     auto-extract rule
tape        to learnings.md
```

## 3. Cellular single-agent execution (FastMem pattern)

Only ONE agent cell is in memory at any millisecond:

```
[ Central ToK State / FastMem Store ]
        │  (loads minimal context frame)
        ▼
[ Active Cell Engine ]
  SlotFinder → BruteMiner → HeartbeatRunner → (flush) → next cell
```

- Strict single-active constraint (global mutex / FOW claim)
- FastMem context swap: state serialized to KV frame on cell exit
- No process contention, no race conditions, O(1) memory overhead

## 4. Memory structures (long-term)

| Structure | Location | Role |
|---|---|---|
| Learnings System | `.bdi_state/tok_memory/learnings.md` | negative-constraint propagation |
| Recipe Book | `.bdi_state/tok_memory/recipe_book/` | type-erased AST skeletons |
| NMCT Vault | `.bdi_state/nmct_vault/` | canonical code + execution tape (SHA-256 sealed) |
| NMTD DB | `.bdi_state/nmtd_db/` | post-mortem incident records + guardrails |

## 5. Maslow needs hierarchy

Modular needs engine: physiological (resources) → safety (integrity) →
belonging (comms) → esteem (trust) → self-actualization (betterment).
Every heartbeat evaluates needs and writes `needs_status.json` — the
auto-tell signal the system (Aegis) reads to satisfy unmet needs.
See [MASLOW.md](MASLOW.md).

## 6. Aegis control channel

The agent never acts on the outside world directly. It writes proposals to
`control/proposals.jsonl`; Aegis approves/denies/defer in
`responses.jsonl`. The agent executes locally-verifiable internal steps
only. Full sovereign override.

## 7. Why this beats an LLM for pure tooling

- **Sub-millisecond latency** — hash-map lookups + pattern matching, not
  transformer passes
- **Deterministic security** — every tool call bounded by symbolic
  guardrails
- **Formal verification** — plan library verifiable for liveness,
  deadlocks, total correctness before deployment
- **Zero context bleed** — FastMem frames prevent cross-cell leakage

## Vectored Terminal Driver (v0.2.0 step)

**Source:** Patrick Doyle, *AI Qual Summary* (June 3, 1997) — the classic
survey of agent architectures. Every architecture contributes one decision
vector; the driver routes each decision through the vector stack in
priority order (subsumption-style suppression), journals every decision,
and yields the winning action. Zero LLM — every decision is a pure
function of context facts.

| Vector (priority) | Architecture → Pattern |
|---|---|
| `atlantis-controller` (90) | **Atlantis** (Gat 1991): reflex layer — immediate reactions to current facts (controller missing → seek, fail-rate → heal, disk → prune). Internal state *guides*, never *controls* directly. |
| `prodigy-control` (70) | **PRODIGY** (Carbonell): control rules = SELECT/REJECT/PREFER over candidates. NMTD guardrails become REJECT rules; skill-library hits become SELECT rules. Learned control beats raw search. |
| `atlantis-sequencer` (60) | **Atlantis/RAP** (Firby): task queue with method fallbacks, cognizant failure — detect, don't prevent. Picks next open pool task. |
| `soar-preferences` (55) | **SOAR** (Laird/Newell): accept/reject/better/worse/indifferent preferences; TIE impasse → defer or random among indifferent maxima; chunking caches winning decisions as compiled knowledge. |
| `bb1-agenda` (50) | **BB1** (Hayes-Roth): KSAR agenda — enumerate → rate (weight × executability) → choose → execute. To-Do-Set → Chosen-Action. |
| `prs-intentions` (45) | **PRS** (Georgeff/Lansky): intention structure with invocation conditions; suspended intentions re-activate when their condition holds. Metalevel KAs override by priority. |
| `maes-activation` (40) | **Maes** (1989): competence nodes + activation spreading (env/goal/successor), link reliability S/T learned from outcomes (operant conditioning), neutral prior 1/1. |

Subsumption semantics: highest-priority vector with a non-None action
wins and suppresses the rest (Brooks' suppression wires, realized as
priority ordering). Decisions + outcomes flow into the action journal —
recording behavior is first-class.

## Aiception — explicit control decisions as a decision tree

BB1's control problem, implemented as a decision tree (`bdi_fsm/aiception.py`):

  "Make explicit control decisions that solve the control problem. Decide
   what actions to perform by reconciling independent decisions about what
   actions are DESIRABLE and what actions are FEASIBLE. Adopt variable
   grain-size control heuristics that focus on whatever action attributes
   are useful in the current problem-solving domain."

Levels, in importance order (each a node in the tree):
- **PROBLEM** (root) — what problem are we solving?
- **STRATEGY** — general plan for the episode
- **FOCUS** — local objectives rating candidates by attribute-value pairs
  (variable grain: fine/medium/coarse)
- **POLICY** — global scheduling criteria (long-lived)
- **TO-DO-SET** — FEASIBLE actions (preconditions true) vs triggered
- **CHOSEN-ACTION** — the winner + rationale (which Foci/Policies led)

Desirability = Σ Focus/Policy weights matching a candidate; feasibility =
the To-Do-Set gate (blocked attrs + PRODIGY guardrail rejections). The
Chosen-Action is the feasible candidate with highest desirability.

Every auto-choice renders the full path as an ASCII tree, persisted to
`decision_trees/latest.txt` + timestamped snapshots and pushed to GitHub,
so each decision the agent makes is inspectable end-to-end. Tests:
149/149 deterministic, zero LLM.

## Hap — Oz/Tok goal-directed reactive engine

From the Doyle survey (Oz/Tok section): Hap is Tok's goal-directed,
reactive engine (`bdi_fsm/hap.py`). Complements Aiception (BB1: WHAT
to do) with HOW to do it.

- **Goals** — atomic name + params; do NOT characterize world states
  (no explicit planning, Hap doctrine)
- **Plan memory** — production rules: {goal, precondition} → plan with
  specificity; multiple plans per goal; failed plans never retried
  blindly (NMTD doctrine)
- **Active Plan Tree (APT)** — AND-OR tree: alternating goal/plan
  layers; plan node succeeds when ALL subgoals succeed (AND), goal via
  ANY applicable plan (OR); root = persistent top-level goals
- **Theory of Activity loop** — (1) revise APT (context conditions +
  success tests, prune satisfied/failed), (2) goal arbiter picks leaf:
  priority → continuation of current line → plan specificity, (3)
  execute: primitive action or expand subgoal
- **Renders** the APT as ASCII (`render_apt()`) — inspectable like the
  Aiception tree

Agent wiring: `agent.hap` seeded with canonical plans (skill-first →
mine-fallback for resolve_task; check → restart for heal);
`agent.run_hap_goal()` posts + runs one loop step, journals the result.
Tests: 163/163 deterministic, zero LLM.


## 3. The decision kernel (blueprint)

The control layer is gated by the **Banburismus decision kernel** — the same
log-odds machinery Turing used for Naval Enigma, wired to a Nash-optimal
stop condition.

### 3.1 Evidence accumulation (decibans)

```
score(dBan) = 10 · log10( P(H) / P(¬H) )         # prior at 50/50 = 0 dBan
score ← score + 10 · log10( P(evidence|H) / P(evidence|¬H) )   # update = ADD
LR = 0 (crib violated) → eliminate → score = −∞
```

The ledger **persists across FSM ticks** — without persistence every tick
starts from zero and the gate can never fire. This was the integration bug
fixed in v0.2.0.

### 3.2 The Nash stop — no magic constant

```
θ★ = 10 · log10( C_miss / C_false )     # decibans
default C_miss/C_false = 100/1  →  θ★ = 20 dBan  (derived, never hardcoded)
```

`code_patcher.py` and `bayes_engine.py` no longer default to a `20.0` literal:
the threshold is always `θ★` from costs. Pass any ratio and the gate self-tunes.

### 3.3 PLATEAU vs BLOCKED — detection without a changed recovery is a loop

```
EVALUATE ──stalled──► PLATEAU (soft)
                          ├─ expand_horizon     → EVALUATE (fact: horizon++)
                          ├─ decompose_subgoal  → EVALUATE (fact: subgoal posted)
                          └─ commit_min_regret  → COMMIT  (fact: best committed)

BLOCKED (hard) ──give_up──► IDLE    # no retry; nothing left to mutate
```

`PlateauDetector` (`plateau.py`) unifies three signals into one
`(is_stalled: bool, reason: PlateauType)`:

| Source | Signal | PlateauType |
|---|---|---|
| `rotor_codec` patience | no score improvement for N candidates | `SCORE_STAGNANT` |
| `markov_plateau` entropy | word-entropy curve leveled out | `ENTROPY_FLAT` |
| FSM verify | multiple winners, no discriminator | `CANDIDATE_TIE` |

Hard blocks (`NO_CANDIDATES`, `ALL_REJECTED`, `VERIFY_FAIL`) are **not**
stalls — there is no information left to mutate.
