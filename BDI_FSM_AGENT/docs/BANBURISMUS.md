# Banburismus — How the BDI Agent Decides (a "how it works" you won't forget)

> Alan Turing's method for breaking Naval Enigma was **not** brute force.
> He scored hypotheses in **log-odds** and let evidence **accumulate** until one
> survived. This doc is that method, rebuilt as the agent's decision loop.

---

## The one-paragraph version (memorise this)

**Start with every possibility at 50/50. Every new fact moves each possibility
up or down by a log-odds number. Contradicted possibilities drop to zero.
When one possibility's accumulated score clears a threshold, you act.**

That's it. Everything below is just naming the pieces.

---

## The three moves

### 1. The Prior — "the full realm"

Before evidence, list every hypothesis `H`. All possible rotor settings; all
possible tool calls. Assign each a prior. A neutral prior `P(H) = 0.5` encodes
as **0 decibans**.

```
score(dBan) = 10 × log10( P(H) / P(not-H) )
```

| P(H) | odds | dBan |
|---|---|---|
| 0.5 | 1:1 | 0 |
| 0.9 | 9:1 | +9.5 |
| 0.1 | 1:9 | −9.5 |

### 2. The Evidence — "the likelihood"

Each new fact asks: *"how likely is this evidence if H is true, versus if H is
false?"* That ratio is the **likelihood ratio**:

```
LR = P(evidence | H) / P(evidence | not-H)
```

`LR > 1` → H more likely. `LR < 1` → H less likely. `LR = 0` → H **impossible**
(a rule was violated — a crib failed — eliminate it: score → −∞).

### 3. Log-odds — "why bans"

Multiplying LRs over many observations gives astronomically small/large
numbers. Turing's trick: work in logarithms. `log10` of the odds is the **ban**;
a tenth of a ban is the **deciban** (dBan). Updating becomes **addition**:

```
+10 dBan = 10× more likely      −10 dBan = 10× less likely
```

This is the exact unit in `ban.py` (1 ban = 10 dBan = log₁₀(10) odds).

---

## The gate — "the Nash threshold"

When a hypothesis's **accumulated** score clears the threshold, the gate fires:

```
threshold θ* = 10 × log10( C_miss / C_false )
```

`C_miss` = cost of wrongly NOT acting, `C_false` = cost of wrongly acting.
A wrong tool call 100× worse than a missed one → fire at **+20 dBan** (100:1).
Firing is the point where acting and not-acting have equal expected cost — the
**Nash equilibrium** of the decision. More evidence concentrates the posterior
until one hypothesis dominates; that dominance *is* the game reaching Nash.

---

## Worked example (real numbers, from `bayes_engine.py`)

Two candidate actions out of IDLE: `exec_sql_query` and `call_rest_api`.

```
context: db_connected = True, api_key_valid = False
threshold = 20 dBan (100:1)
```

**Tick 1** — both registered at 0 dBan. Precondition check: `call_rest_api`
needs a valid API key → **eliminated** (−∞). Evidence for `exec_sql_query`:

```
P(evidence | H) = 0.8,  P(evidence | not-H) = 0.2  →  LR = 4  →  +6.02 dBan
```

**Tick 2** — evidence **accumulates** (the ledger persists):

```
LR = 19  →  +12.79 dBan   →   total = 6.02 + 12.79 = 18.81 dBan  (still < 20)
```

**Tick 3** — one more observation:

```
LR = 9  →  +9.54 dBan   →   total = 28.35 dBan  ≥ 20  →  FIRE
```

`exec_sql_query` executes, FSM moves `IDLE → EXECUTING_TOOL`, ledger resets.

> **Key subtlety:** without persistence, every tick starts from zero and the
> gate can *never* fire. The ledger must live across ticks — this was the bug
> fixed in the integration.

---

## The Enigma connection (why this is Banburismus)

Turing's Banburismus scored rotor-order hypotheses exactly like this:

- **Prior** = the rotor/key space (1.59 × 10²⁰ settings).
- **Evidence** = letter coincidences between intercepted messages.
- **Elimination** = the crib ("no letter encrypts to itself" — any setting that
  maps a crib letter to itself is instantly rejected).
- **Accumulation** = Banbury sheets, scored in bans.
- **Gate** = enough accumulated score → run the Bombe on the survivor.

The agent does the same, replacing "rotor setting" with "tool action". The
`ToolObserver` (log-odds intent gate) feeds this ledger. The Enigma lock
(`enigma_lock.py`) is the crib: a permutation gate that eliminates impossible
calls before the ledger even scores them.

---

## Two ledgers, one soul

| | `ban.BanLedger` | `bayes_engine.BanLedger` |
|---|---|---|
| Question | *Did this step add information?* | *Which action is most likely?* |
| Measures | entropy gain (before − after) | log-odds accumulation |
| Doctrine | zero-ban step = wasted step | threshold clear = act |
| Role | judge the **past** | choose the **future** |

Together they are the Banburismus soul: measure the information in every step,
and let evidence — not instinct — decide the next one.

---

## The data flow

```
world state ──► preconditions (crib filter) ──► eliminate impossible actions
                                                    │
incoming evidence ──► likelihood ratio ──► score += 10·log10(LR)  [decibans]
                                                    │
                    ledger persists across ticks ──► accumulate
                                                    │
                    score ≥ θ* ? ──YES──► execute action ──► FSM transition
                          │                          └─► reset ledger
                          NO ──► hold state, wait for more evidence
```
