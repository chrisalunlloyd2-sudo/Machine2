# Phonotactics — the Token-Stream Guardrail (a "how it works" you won't forget)

> Speech is continuous; thought is discrete. The bridge is the *token stream*:
> a sequence of phonemes. The set of valid sequences is a **regular language**
> `L_valid`, and a **deterministic finite automaton** decides membership. That
> DFA is not a new idea in this project — it is the *same crib filter* as
> Enigma's "no fixed point" and the AST patcher's "syntax check", applied to
> sequences instead of rotors or code.

---

## The one-paragraph version (memorise this)

**Any token stream is a string in a language. A DFA `M = (Q, Σ, δ, q₀, F)`
walks it state by state. An undefined transition `δ(q, a)` is the crib: the
string leaves the language and the hypothesis dies at −∞ dBan. Valid tokens
accumulate evidence transition-by-transition until the gate fires.**

That's it. The DFA *is* an FSM; the undefined transition *is* a contradiction.

---

## The mapping (your three-way split, made literal)

```
[ BDI ]  -> desires / intentions   (what to say)
    |
    v
[ FSM ]  -> phonotactic DFA M      (which sequences are legal — the guardrail)
    |
    v
[ tokens ] -> discrete symbols     (the Turing tape, driven cycle by cycle)
```

The continuous physics (formants, `f₀`, prosody) is the *substrate* the tokens
abstract over; the DFA is the *structure* they must obey; the BDI agent is the
*reasoner* that chooses tokens within those boundaries.

---

## The three moves

### 1. The alphabet Σ — discrete symbols

A phoneme is a token with a **sonority class** (vowel > glide > liquid >
nasal > fricative > stop). Sonority is why the grammar has its shape: the
nucleus (vowel) is the peak, and consonants arrange around it.

### 2. The transition function δ — the crib

English syllables follow the **Sonority Sequencing Principle** (SSP):

- **Onset**: sonority must **not fall** toward the nucleus — with ONE
  exception, the "extra-syllabic /s/" (`/st/ /sp/ /sk/ /str/ /spl/ /skr/`).
- **Coda**: sonority must **not rise** away from the nucleus.

So `/str/` is valid (s-cluster + rising `t→r`), but `/ftr/` is **not** — the
`f→t` step is a sonority fall with no s-exception. That fall is the crib:

```
δ(ONSET, /f/) = ONSET     (fine)
δ(ONSET, /t/) = undefined  (f→t is a fall, no /s/ → CONTRADICTION)
```

Exactly like `E(x) = x` in Enigma: the string hits an impossible state and is
eliminated, with the **exact failing (state, symbol)** reported.

### 3. The gate — evidence in decibans

Every legal transition is positive evidence; an illegal one is −∞. Wire the
stream through the BanLedger:

```
/strin/  -> 5 legal transitions -> +23.86 dBan -> gate fires ("valid")
/ftrin/  -> fails at (ONSET, /t/)  -> −∞ dBan   -> eliminated
```

---

## The extra moves (the "way better" additions)

### Bark-scale formants — perceptual distance = ban distance

Vowel `V = (F1, F2, F3)` in **Bark space**, not Hz. The Bark scale is
log-frequency, so a Bark Δ ≈ a ban Δ (both base-10 logs). Discriminating
`/i/` from `/a/` is then literally a likelihood-ratio in the same units as the
decision ledger. The continuum becomes Bayes.

### Isochrony — rhythm as evidence

Stress-timed speech keeps inter-stress intervals ~constant. Deviation is the
coefficient of variation; `0` = perfectly isochronous. That deviation is
evidence — a rhythm that's regular is *consistent with* the stress-timed
hypothesis, and feeds the ledger just like any other observation.

---

## Where it lives

```
bdi_fsm/phonotactics.py   SequenceDFA (generic) + EnglishSyllableDFA (SSP crib)
                          + Bark formants + isochrony + score_with_ledger
tests/test_phonotactics.py  16 tests (accept/reject/crib/gate/formant/isochrony)
```

---

## The lesson, in one line

> *A token stream is a string in a language; a DFA is the guardrail that
> keeps it in the language; and an undefined transition is a contradiction —
> the same −∞ dBan crib that kills bad rotors and bad code.*
