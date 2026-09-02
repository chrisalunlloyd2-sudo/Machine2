"""MARKOV CHAT — entropy-stopped stochastic stitching (no LLM, ever).

The bet-winning idea, made rigorous with Shannon's math:

A non-LLM chatbot can generate LONG coherent text by stitching Markov
strings — IF it knows when to stop. Coherent text has LOW conditional
entropy: each next word is fairly predictable given context. When the
generator reaches a branch point with many equally-likely continuations,
the conditional entropy SPIKES — that is exactly where an LLM's confidence
collapses and where our string would go incoherent. So we stop there.

    generate:  seed -> while not stopped:
                   row = transitions[context]
                   H    = -sum p log2 p  (this step's entropy)
                   if H > entropy_cap or H > running_mean * spike_mult:
                       STOP (coherence break — the branch is unpredictable)
                   emit argmax(row) (deterministic, seeded tie-break)
                   advance context

Correlates with source theory: the generator is a stochastic source with
information rate r; entropy-stopping bounds r so the emitted string stays
in the coherent regime. The chat is the channel output; stopping at H-spikes
is the decoder refusing low-signal symbols.

Pure stdlib, deterministic (seeded), zero LLM.
"""

import math
import random
import re
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Sequence, Tuple

_TOKEN_RE = re.compile(r"[A-Za-z']+|[0-9]+|[.,!?;:()\"-]")


def tokenize(text: str) -> List[str]:
    return _TOKEN_RE.findall(text.lower())


def _log2(p: float) -> float:
    return math.log2(p) if p > 0 else 0.0


def row_entropy(row: Counter) -> float:
    """H = -sum p log2 p over one transition row — uncertainty of the
    next symbol given this context."""
    total = sum(row.values())
    if total <= 1:
        return 0.0
    return -sum((c / total) * _log2(c / total) for c in row.values())


MAX_CYCLE = 4        # longest loop we bother detecting
CYCLE_REPEATS = 3    # how many times it must repeat before we call it degenerate

# Function words carry no topic, so jumping on them lands anywhere at all -- which is the random
# jump this is meant to replace. Deliberately short: an aggressive stoplist would strip the
# subject out of half the sentences in the corpus.
STOPWORDS = frozenset("""
a an the of to in on at by for from with and or but if is are was were be been being
it its this that these those as not no do does did have has had will would can could
i you he she they we them us our your their my me him her
""".split())

JUMP_LOOKBACK = 8    # how far back to look for a word worth jumping on


def _cycling(emitted, max_period=MAX_CYCLE, repeats=CYCLE_REPEATS):
    """Has generation fallen into a repeating loop?

    True when the tail of `emitted` is the same k-token block repeated `repeats` times, for any
    k up to max_period. k=1 is the old "three identical tokens" test, so this strictly widens
    the guard rather than replacing its behaviour.

    Bounded on purpose: it inspects at most max_period * repeats trailing tokens per step, so
    the check costs the same whether the reply is 10 words or 10,000.
    """
    for k in range(1, max_period + 1):
        span = k * repeats
        if len(emitted) < span:
            break
        block = emitted[-k:]
        if all(emitted[-(i + 1) * k:len(emitted) - i * k] == block for i in range(1, repeats)):
            return True
    return False


class MarkovChat:
    """Order-k Markov chain over a corpus, with entropy-stopped generation."""

    def __init__(self, order: int = 2, seed: int = 7):
        self.order = order
        self.rng = random.Random(seed)
        self.seed = seed
        self.transitions: Dict[Tuple[str, ...], Counter] = defaultdict(Counter)
        self.starts: List[Tuple[str, ...]] = []
        # token -> contexts that END in that token (topical fallback index)
        self.token_ctx: Dict[str, List[Tuple[str, ...]]] = defaultdict(list)
        self.stop_tokens = {".", "!", "?", ";"}
        # Words used as a jump target, and contexts already LANDED on, this generation.
        # Both reset per call in generate(): carrying either between calls would make the
        # second reply to a seed quietly worse than the first.
        self._jumped = set()
        self._landed = set()

    # ---- build ----------------------------------------------------------
    def build(self, texts: Sequence[str]) -> Dict[str, Any]:
        """Learn transition tables from a corpus of texts (each its own stream)."""
        self.transitions.clear()
        self.starts.clear()
        self.token_ctx.clear()
        n_streams = 0
        for text in texts:
            toks = tokenize(text)
            if len(toks) < self.order + 1:
                continue
            n_streams += 1
            self.starts.append(tuple(toks[:self.order]))
            for i in range(self.order, len(toks)):
                ctx = tuple(toks[i - self.order:i])
                self.transitions[ctx][toks[i]] += 1
        # index every context by its final token for topical seeding
        for ctx in self.transitions:
            self.token_ctx[ctx[-1]].append(ctx)
        return {"streams": n_streams, "contexts": len(self.transitions),
                "tokens": sum(sum(r.values()) for r in self.transitions.values())}

    # ---- generation -----------------------------------------------------
    def _jump(self, emitted: Sequence[str]) -> Optional[Tuple[str, ...]]:
        """Leave the current tree on a word, land on another tree that shares it.

        Chris 2026-08-12: *"in my mind, I jump from word to word and tree to tree, trees inside
        trees -- words, sentences, concepts... that's how we string markov properly"*.

        Every restart in this generator used to be `rng.choice(self.starts)`: when a sentence
        ended or coherence broke, the chain teleported to a RANDOM document opening. That is why
        stitched replies read as unrelated fragments bolted together -- the sentences were
        genuinely unrelated, drawn independently from the corpus.

        The associative jump uses the index build() already maintains: token_ctx maps a token to
        every context ending in it. So we walk back over what was just said, take the first word
        that carries topic, and resume from somewhere that word actually occurs. The chain keeps
        moving, but it keeps moving ABOUT SOMETHING.

        Falls back to the random start when nothing topical is available, so this can only ever
        improve on the old behaviour -- there is no input for which it does worse.
        """
        for tok in reversed(list(emitted)[-JUMP_LOOKBACK:]):
            if tok in STOPWORDS or tok in self.stop_tokens or not tok.isalpha() or len(tok) < 3:
                continue
            # Never jump twice on the same word: the chain re-reads its own last sentence, finds
            # the word it just landed on, and returns to the same place -- a loop wearing a
            # topic's clothes.
            if tok in self._jumped:
                continue
            # SENTENCE OPENINGS ONLY, and never one already used this reply.
            #
            # The first version also accepted contexts from token_ctx, which holds contexts
            # ENDING in the token -- i.e. mid-sentence, often one token from a full stop. Landing
            # there emitted "." and restarted immediately, so associative restarts produced
            # SHORTER output than random ones (37 words against 42, measured on a 20-sentence
            # corpus) and replies read "the road. down the road. the road." That falsified this
            # method's own promise that it could never do worse than what it replaced.
            #
            # An opening is on-topic AND has a whole sentence of runway, so a jump can only help.
            # When no unused topical opening exists we fall through to the random start, which is
            # exactly the old behaviour -- the floor, never the ceiling.
            opens = [c for c in self.starts
                     if tok in c and self._has_runway(c) and tuple(c) not in self._landed]
            if opens:
                return self._land(tok, opens)
        if self.starts:
            return tuple(self.rng.choice(self.starts))
        return None

    def _land(self, tok, options):
        """Choose a landing and remember it, so a later jump cannot return to the same place.

        Tracking the WORD alone was not enough: two different words in one sentence lead back to
        the same context, and the reply became "the station. the station. past the station."
        Measured on a 20-sentence corpus, that made associative restarts produce SHORTER output
        than random ones -- 37 words against 42 -- which falsified this method's own promise that
        it could never do worse. Excluding spent landings restores the guarantee.
        """
        self._jumped.add(tok)
        ctx = tuple(self.rng.choice(options))
        self._landed.add(ctx)
        return ctx

    def _has_runway(self, ctx):
        """Would generation continue from here, or stop on the very next token?"""
        row = self.transitions.get(ctx)
        if not row:
            return False
        return any(t not in self.stop_tokens for t in row)

    def _pick(self, row: Counter) -> Tuple[str, float]:
        """Deterministic argmax with seeded tie-break. Returns (token, H)."""
        H = row_entropy(row)
        best = max(row.items(), key=lambda kv: (kv[1], self.rng.random()))
        return best[0], H

    def generate(self, seed: Optional[str] = None, max_words: int = 80,
                 entropy_cap: float = 3.0, spike_mult: float = 2.0,
                 window: int = 8, echo_seed: bool = False,
                 min_words: int = 1, max_restarts: int = 3) -> Dict[str, Any]:
        """Generate a coherent string. Stops when:
        - the current step's entropy > entropy_cap (absolute incoherence), or
        - entropy > running_mean * spike_mult (relative spike = coherence break),
        - a stop token is emitted (after min_words), a dead end is hit, or
          max_words reached.

        echo_seed: if True, continue the prompt verbatim when its trailing
        n-gram is in the corpus. If False (chat mode), reply topically instead
        of echoing the prompt back.

        min_words: keep stitching fresh sentences (restarting at each stop
        token) until at least this many tokens are emitted, or an entropy
        spike / dead end / max_words halts. Default 1 = stop at first period
        (legacy behaviour).
        """
        # Fresh per call: the no-repeat-jump set is about THIS reply. Carried between calls it
        # would make the second answer to a seed quietly worse than the first, which is the kind
        # of bug that only shows up as "it used to be better".
        self._jumped = set()
        self._landed = set()
        if not self.transitions:
            return {"text": "", "words": 0, "reason": "empty_model"}
        toks = tokenize(seed or "") if seed else []
        # Choose a starting context. Priority:
        #   1. exact trailing n-gram of the seed (only when echo_seed=True)
        #   2. topical fallback: any context ENDING in a seed token
        #   3. a random corpus start (guarantees novel text, never an echo)
        ctx = None
        if echo_seed and len(toks) >= self.order and tuple(toks[-self.order:]) in self.transitions:
            ctx = tuple(toks[-self.order:])
            emitted = list(toks)
        else:
            for tok in reversed(toks):
                cands = self.token_ctx.get(tok)
                if cands:
                    ctx = self.rng.choice(cands)
                    break
            if ctx is None and self.starts:
                # COLD start: nothing has been emitted yet, so there is no trail to be
                # associative about. This one stays random -- _jump() would have nothing to
                # read, and the seed ladder above has already had its chance.
                ctx = tuple(self.rng.choice(self.starts))
            if ctx is None:
                return {"text": "", "words": 0, "reason": "no_seed"}
            emitted = list(ctx)
        entropies: List[float] = []
        reasons = []
        restarts = 0
        frag_start = 0  # entropy index where the current sentence-fragment began
        for _ in range(max_words):
            if ctx not in self.transitions:
                # mid-stream dead end: restart a fresh sentence if we still
                # owe words (min_words not yet met).
                if len(emitted) < min_words and restarts < max_restarts and self.starts:
                    ctx = self._jump(emitted)
                    restarts += 1
                    frag_start = len(entropies)
                    continue
                reasons.append("dead_end")
                break
            row = self.transitions[ctx]
            nxt, H = self._pick(row)
            entropies.append(H)
            emitted.append(nxt)
            # degenerate-repetition guard. The old test was `nxt == emitted[-2] == emitted[-3]`,
            # which only catches a period-1 loop ("--- --- ---"). A Markov chain falls into a
            # CYCLE of any period as soon as it reaches a context whose successors are
            # effectively deterministic, and the corpus is full of them: Rust doc prose produced
            #     "... bitslice:: slice:: slice:: slice:: slice:: ..."
            # forever, which is period 2 and passed the old guard untouched. Entropy cannot stop
            # this either -- a deterministic successor has entropy 0, so the more degenerate the
            # loop the less the coherence test objects to it.
            if _cycling(emitted):
                reasons.append("repetition")
                break
            # entropy-stopping: the coherence test (per-fragment window)
            over_cap = H > entropy_cap
            frag = entropies[frag_start:]
            spiked = (not over_cap and len(frag) >= 4 and
                      H > (sum(frag[:-1]) / len(frag[:-1])) * spike_mult)
            if over_cap or spiked:
                # coherence break: stitch a fresh sentence if we still owe words
                if len(emitted) < min_words and restarts < max_restarts and self.starts:
                    reasons.append(f"restart(H={H:.2f})")
                    restarts += 1
                    ctx = self._jump(emitted)
                    frag_start = len(entropies)
                    continue
                reasons.append(f"entropy_cap({H:.2f}>{entropy_cap})" if over_cap
                               else f"entropy_spike(H={H:.2f} x{spike_mult})")
                break
            if nxt in self.stop_tokens:
                if len(emitted) >= min_words or restarts >= max_restarts:
                    reasons.append("stop_token")
                    break
                # sentence boundary before min_words: start a fresh sentence
                restarts += 1
                ctx = self._jump(emitted)
                frag_start = len(entropies)
                continue
            ctx = tuple((ctx + (nxt,))[-(self.order):])
        text = " ".join(emitted)
        # normalize spacing around punctuation for readability
        text = re.sub(r"\s+([.,!?;:])", r"\1", text)
        text = re.sub(r"([.!?;:])\s*([A-Za-z0-9])", r"\1 \2", text)
        return {
            "text": text,
            "words": len(emitted),
            "reason": reasons[0] if reasons else "max_words",
            "steps": len(entropies),
            "entropy_mean": (sum(entropies) / len(entropies)) if entropies else 0.0,
            "entropy_max": max(entropies) if entropies else 0.0,
            "entropy_series": entropies,
        }

    def stitch(self, seeds: Sequence[str], join_with: str = " ",
               max_words_per: int = 60, **kwargs) -> Dict[str, Any]:
        """Stitch multiple Markov streams into one longer chat message."""
        parts, all_e, total = [], [], 0
        for s in seeds:
            out = self.generate(seed=s, max_words=max_words_per, **kwargs)
            if out["text"]:
                parts.append(out["text"])
                all_e.extend(out["entropy_series"])
                total += out["words"]
        text = join_with.join(parts)
        return {"text": text, "words": total, "parts": len(parts),
                "entropy_mean": (sum(all_e) / len(all_e)) if all_e else 0.0,
                "entropy_max": max(all_e) if all_e else 0.0}

    def stats(self) -> Dict[str, Any]:
        n = len(self.transitions)
        if not n:
            return {"contexts": 0, "tokens": 0, "mean_row_entropy": 0.0}
        es = [row_entropy(r) for r in self.transitions.values()]
        return {"contexts": n,
                "tokens": sum(sum(r.values()) for r in self.transitions.values()),
                "mean_row_entropy": sum(es) / n,
                "max_row_entropy": max(es),
                "coherent_rows": sum(1 for e in es if e < 2.0)}


# ---- agent-facing convenience -------------------------------------------
def chat_longer(corpus_texts: Sequence[str], seed: str, max_words: int = 80,
                order: int = 2, seed_val: int = 7, **kwargs) -> Dict[str, Any]:
    """One-shot: build from corpus, generate from seed. Returns dict."""
    mc = MarkovChat(order=order, seed=seed_val)
    mc.build(corpus_texts)
    return mc.generate(seed=seed, max_words=max_words, **kwargs)

# LOCATIONS - this file lives in more than one place
#
#   live:  C:\Viper\projects\BDI_FSM_AGENT
#          -> C:\Users\viper\gan-otg-db\BDI_FSM_AGENT
#   mirror: J:\ViperVault\code\projects\BDI_FSM_AGENT
#   mirror: C:\Users\viper\gan-otg-db\BDI_FSM_AGENT
#
#   live detail (freshness, git coverage): docs\LOCATIONS.md
#   regenerate: python location_stamp.py apply
# end LOCATIONS
