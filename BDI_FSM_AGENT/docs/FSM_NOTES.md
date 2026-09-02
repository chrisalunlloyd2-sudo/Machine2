# FSM NOTES — The Ban Soul

*Saved from Chris 2026-08-11: "work on using the ban step by step as the soul —
save definitions and save to fsm notes."*

## Definitions (Wikipedia — "Hartley (unit)")

The **hartley** (symbol **Hart**), also called a **ban**, or a **dit** (short for
"decimal digit"), is a logarithmic unit that measures information or entropy,
based on **base-10 logarithms and powers of 10**.

- **One hartley** = the information content of an event if the probability of
  that event occurring is **1/10**.
- It is equal to the information contained in **one decimal digit (dit)**,
  assuming a priori equiprobability of each possible value.
- Named after **Ralph Hartley** (1928).

Related units:

| Unit    | Base | Event p | Notes                        |
|---------|------|---------|------------------------------|
| hartley | 10   | 1/10    | = ban = dit (one decimal digit) |
| shannon | 2    | 1/2     | = bit                        |
| nat     | e    | 1/e     | natural logarithms           |

**Conversions:**

    1 ban = ln(10)  nat  ≈ 2.303 nat
    1 ban = log2(10) Sh  ≈ 3.322 Sh (3.322 bit)
    1 bit = 1 / log2(10) ban ≈ 0.301 ban

## The Soul — step by step

Every step of the agent is measured in **bans**.

    H         = -SUM p * log10(p)          uncertainty (entropy), in bans
    gain      = H_before - H_after         information a step actually carries
    certainty = 10^(-H_remaining)          100% certainty  <=>  0 bans remain

**Step-by-step doctrine:**

1. Measure uncertainty BEFORE the step (bans).
2. Act.
3. Measure uncertainty AFTER the step (bans).
4. gain = before - after.
5. Remaining entropy = 0 bans → task **100% complete** (ties to SOP-010
   Certitude Doctrine: "until 100%" = until zero bans of uncertainty remain).
6. gain ≈ 0 bans → the step carried **NO information** → **step back, assess,
   redo** (a zero-ban step is a wasted step).

**Canonical example:** choosing 1 of 10 equiprobable digits carries exactly
**1.000 ban** of information — `hartley(10) = log10(10) = 1`. Resolving a
10-way choice step by step (e.g. 0.699 + 0.301 bans) sums to exactly 1.0 ban,
certainty 0.5 → 1.0.

## Implementation

- `bdi_fsm/ban.py` — `Ban` (self_info, hartley, entropy, kl, to_bits/to_nats,
  certainty) + `BanLedger` (step-by-step accounting, is_done, wasted_steps,
  verdict gate).
- `BDIFSMAgent.ban_step()`, `ban_verdict()`, `ban_state()` — the soul exposed
  to the agent.
- `CertaintyGate` verifier `ban_gain` — horizon blocks can gate on information
  content (a step must carry >= min bans, else STEP_BACK).
