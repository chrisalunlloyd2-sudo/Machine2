"""MARKOV PLATEAU — generate until entropy levels out (no better reply exists).

Chris directive 2026-08-12:
"Markov training to output multiple concepts and expand on them until the
curve levels out of Shannon entropy and no better reply exists."

This is the entropy-stopping idea taken one level up. Instead of generating
ONE string and stopping at a spike, we generate MANY candidate replies (each
with a different deterministic seed), measure each candidate's word-level
Shannon entropy, and keep expanding candidates until the ENTROPY CURVE PLATEAUS
— i.e. successive candidates stop improving. At the plateau, the lowest-entropy
candidate is the "best reply": maximally coherent, maximally confident.

Plateau detection (deterministic, no LLM):
  - candidate_i has entropy H_i (mean per-step conditional entropy).
  - improvement_i = H_{i-1} - H_i  (positive = getting more coherent).
  - plateau when improvement < eps for `patience` consecutive candidates.

Pure stdlib. Deterministic (seeded). Zero LLM.
"""

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .markov_chat import MarkovChat, row_entropy, tokenize, _log2


def word_entropy(tokens: Sequence[str]) -> float:
    """Shannon entropy of the token distribution of a generated string.
    Lower = more repetitive/coherent = more confident. This is a proxy for
    'how surprising is the emitted text'."""
    if not tokens:
        return 0.0
    n = len(tokens)
    from collections import Counter
    counts = Counter(tokens)
    return -sum((c / n) * _log2(c / n) for c in counts.values())


class MarkovPlateau:
    """Generate multiple Markov candidates until the entropy curve plateaus."""

    def __init__(self, order: int = 2, base_seed: int = 7,
                 eps: float = 0.05, patience: int = 5,
                 max_candidates: int = 50):
        self.order = order
        self.base_seed = base_seed
        self.eps = eps            # min improvement to count as "still improving"
        self.patience = patience  # consecutive non-improving candidates to stop
        self.max_candidates = max_candidates

    def generate(self, corpus_texts: Sequence[str], seed: str,
                 max_words: int = 80, entropy_cap: float = 3.0,
                 spike_mult: float = 2.0, window: int = 8,
                 echo_seed: bool = False, min_words: int = 25) -> Dict[str, Any]:
        """Generate candidates until entropy plateaus. Returns best + curve.

        echo_seed=False => reply topically (don't echo the prompt).
        min_words => minimum tokens per candidate so replies are substantial.
        """
        curve: List[Dict[str, Any]] = []
        best: Optional[Dict[str, Any]] = None
        stagnant = 0

        for i in range(self.max_candidates):
            # deterministic per-candidate seed (base + i), so the run is
            # reproducible but candidates differ.
            mc = MarkovChat(order=self.order, seed=self.base_seed + i)
            mc.build(corpus_texts)
            gen = mc.generate(seed=seed, max_words=max_words,
                              entropy_cap=entropy_cap, spike_mult=spike_mult,
                              window=window, echo_seed=echo_seed,
                              min_words=min_words)
            text = gen.get("text", "")
            toks = tokenize(text)
            H = word_entropy(toks)
            series = gen.get("entropy_series", []) or []
            mean_step = (sum(series) / len(series)) if series else 0.0
            cand = {
                "index": i,
                "seed_val": self.base_seed + i,
                "text": text,
                "word_entropy": round(H, 4),
                "mean_step_entropy": round(mean_step, 4),
                "words": gen.get("words", 0),
                "reason": gen.get("reason", ""),
            }
            curve.append(cand)

            # track improvement vs previous best (lower entropy = better)
            if best is None:
                best = cand
                stagnant = 0
            else:
                improvement = best["word_entropy"] - H
                if improvement > self.eps:
                    best = cand
                    stagnant = 0
                else:
                    stagnant += 1

            if stagnant >= self.patience:
                break

        plateaued = stagnant >= self.patience
        return {
            "best": best,
            "curve": curve,
            "plateaued": plateaued,
            "candidates": len(curve),
            "plateau_entropy": best["word_entropy"] if best else 0.0,
        }

    def expand(self, corpus_texts: Sequence[str], seed: str, max_words: int = 80,
               **kw) -> Dict[str, Any]:
        """Alias for generate() — 'expand on them until the curve levels out'."""
        return self.generate(corpus_texts, seed, max_words=max_words, **kw)


def plateau_reply(corpus_texts: Sequence[str], seed: str, max_words: int = 80,
                  order: int = 2, base_seed: int = 7, **kw) -> Dict[str, Any]:
    """One-shot convenience: build plateau, return best reply dict."""
    mp = MarkovPlateau(order=order, base_seed=base_seed)
    return mp.generate(corpus_texts, seed, max_words=max_words, **kw)

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
