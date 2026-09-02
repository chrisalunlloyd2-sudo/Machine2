"""INFO THEORY — the decision tree as an information source (Shannon 1948).

Correlates the agent's decision stream with source theory:

* SOURCE:       the decision process — every chosen action is a message symbol
* ENTROPY H(X)      — uncertainty of the next decision, -sum p log2 p
* ENTROPY RATE r    — conditional entropy of a symbol given its history,
                      r = lim H(Xn | Xn-1, Xn-2, ...); here via Markov order-k
                      transition tables over the journaled decision stream
* CHANNEL p(y|x)    — decision -> outcome mapping; fleet reality is the noise
* CHANNEL CAPACITY  — C = max I(X;Y): how much decision information actually
                      predicts outcomes (how good the channel is)
* DIRECTED INFO     — feedback case P(yi | xi, y^{i-1}): how much past
                      decisions + outcomes shape the next outcome; this is
                      the learning loop made measurable
* REDUNDANCY R      — 1 - H/Hmax: how compressible the decision stream is;
                      high R = habitual = dream-prunable (source coding)

Pure stdlib, deterministic, zero LLM. Feeds the Aiception tree footer and
the agent's self-model: an agent that knows its own entropy rate knows when
it is stuck (r -> 0, habitual), chaotic (H -> Hmax, no structure), or
learning (directed info rising).
"""

import math
import os
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Sequence, Tuple


def _log2(p: float) -> float:
    return math.log2(p) if p > 0 else 0.0


def entropy(seq: Sequence[str]) -> float:
    """H(X) = -sum p(x) log2 p(x) — uncertainty of the next symbol."""
    n = len(seq)
    if n < 2:
        return 0.0
    c = Counter(seq)
    return -sum((k / n) * _log2(k / n) for k in c.values())


def max_entropy(alphabet_size: int) -> float:
    return _log2(alphabet_size) if alphabet_size > 1 else 0.0


# ── collapsing a candidate field ─────────────────────────────────────────────
#
# Chris 2026-09-01, on coalescing rows returned by a regex recall: treat the
# candidates as states and collapse only when the field is actually peaked,
# instead of taking whichever row came back first.
#
# entropy() above measures a STREAM of decisions already made. This measures a
# SINGLE decision not yet made: given N scored candidates, is there a winner, or
# is the agent about to pick one of thirty near-identical options and call it a
# choice? The BDI package has seventeen argmax sites and not one of them can
# currently tell the difference.
#
# Measured on the NMCT vault, 120 probes:
#
#     top two candidates within 0.05 of each other   72% of the time
#     mean candidates per recall                     30.9
#
#     BETA=10   real duplicate present  med H 0.39, p90 0.64
#               flat field              med H 0.97, p10 0.87
#
# Two cheaper forms were tried and rejected on measurement. The participation
# ratio (sum s)^2/sum s^2 removes BETA but does not separate at all (22.4 vs
# 29.4): the linear tail swamps the head. The plain ratio test s1/s2 scores
# F1 0.22, because a runner-up is very often an older VERSION of the same
# artifact. So the exponential stays, BETA is pinned rather than fitted, and
# the cut is the only free parameter.
#
# ABSTAINING IS AN ANSWER. A flat field returns no winner and the whole
# cluster, which is also the never-delete axiom arriving from the maths rather
# than being bolted on: nothing gets merged away because it lost a coin toss.
BETA = 10.0


def field_entropy(scores: Sequence[float], beta: float = BETA) -> float:
    """Normalised entropy of a Boltzmann weighting over candidate scores.

    0.0 = one candidate dominates.  1.0 = every candidate equally plausible.
    Shifted by the max before exponentiating, so a large beta cannot overflow.
    """
    vals = [float(s) for s in scores]
    if len(vals) < 2:
        return 0.0
    m = max(vals)
    ex = [math.exp(beta * (v - m)) for v in vals]
    z = sum(ex)
    if z <= 0:
        return 1.0
    ps = [e / z for e in ex]
    return -sum(p * _log2(p) for p in ps) / max_entropy(len(ps))


def collapse(candidates: Sequence, score, hcut: Optional[float] = None,
             beta: float = BETA) -> Dict:
    """Pick a winner from a scored field, or refuse to.

    `score` maps a candidate to a float. Returns:

        winner    the best candidate, or None when the field is too flat
        H         normalised entropy, 0 peaked .. 1 flat
        cluster   every candidate, best first -- always populated
        abstained whether H put the decision beyond reach

    With `hcut` None this never abstains: it reports H and returns the argmax,
    so a call site can be instrumented before it is changed. That is deliberate.
    A threshold fitted to the seven real duplicates in the sample above would be
    a guess wearing a decimal; measure first on the real stream, set the cut
    afterwards.
    """
    ranked = sorted(candidates, key=score, reverse=True)
    if not ranked:
        return {"winner": None, "H": 0.0, "cluster": [], "abstained": False,
                "n": 0}
    H = field_entropy([score(c) for c in ranked], beta=beta)
    flat = hcut is not None and len(ranked) > 1 and H >= float(hcut)
    return {"winner": None if flat else ranked[0], "H": H, "cluster": ranked,
            "abstained": flat, "n": len(ranked)}


def redundancy(seq: Sequence[str]) -> float:
    """R = 1 - H/Hmax — 1.0 means fully predictable/compressible.

    A degenerate alphabet (one symbol) is maximally redundant: H = 0 and
    Hmax = 0, so the ratio is defined as 1.0 (fully compressible).
    """
    H = entropy(seq)
    Hmax = max_entropy(len(set(seq)))
    if Hmax == 0:
        return 1.0 if H == 0 else 0.0
    return 1.0 - H / Hmax


def entropy_rate(seq: Sequence[str], order: int = 1) -> float:
    """r = H(Xn | Xn-1..Xn-k) via Markov transition tables.

    r -> 0  : decisions are fully determined by history (habitual/scripted)
    r ~ H(X): decisions carry independent information (exploratory)
    """
    n = len(seq)
    if n <= order:
        return 0.0
    ctx_counts: Dict[Tuple[str, ...], Counter] = defaultdict(Counter)
    for i in range(order, n):
        ctx = tuple(seq[i - order:i])
        ctx_counts[ctx][seq[i]] += 1
    total = n - order
    rate = 0.0
    for ctx, row in ctx_counts.items():
        row_total = sum(row.values())
        for sym, cnt in row.items():
            p_ab = cnt / total          # p(ctx, sym)
            p_b_given = cnt / row_total  # p(sym | ctx)
            rate -= p_ab * _log2(p_b_given)
    return rate


def mutual_information(x: Sequence[str], y: Sequence[str]) -> float:
    """I(X;Y) = H(X) + H(Y) - H(X,Y) — shared info between decisions and outcomes."""
    n = min(len(x), len(y))
    if n < 2:
        return 0.0
    x, y = x[:n], y[:n]
    px = Counter(x)
    py = Counter(y)
    pxy = Counter(zip(x, y))
    mi = 0.0
    for (xi, yi), cxy in pxy.items():
        p_xy = cxy / n
        mi += p_xy * _log2(p_xy / ((px[xi] / n) * (py[yi] / n)))
    return mi


def channel_capacity_estimate(x: Sequence[str], y: Sequence[str]) -> float:
    """C = max I(X;Y) — how much decision info can predict outcomes.

    Practical estimate: compute I(X;Y) under the empirical input
    distribution and under the max-entropy (uniform) input distribution,
    report the larger as the capacity ceiling.
    """
    n = min(len(x), len(y))
    if n < 2:
        return 0.0
    x, y = x[:n], y[:n]
    py = Counter(y)
    symbols = sorted(set(x))
    # uniform-input channel matrix: p(y|x) estimated from empirical pairs
    given: Dict[str, Counter] = defaultdict(Counter)
    for xi, yi in zip(x, y):
        given[xi][yi] += 1
    # capacity via uniform input over the SEEN alphabet
    k = len(symbols)
    mi = 0.0
    for xi in symbols:
        row = given[xi]
        row_total = sum(row.values())
        for yi, cnt in row.items():
            p_y_given_x = cnt / row_total
            p_y = py[yi] / n
            mi += (1.0 / k) * p_y_given_x * _log2(p_y_given_x / p_y)
    # ensure non-negative (numeric noise floor)
    return max(0.0, mi)


def directed_information_rate(x: Sequence[str], y: Sequence[str],
                              order: int = 1) -> float:
    """I(X^n -> Y^n) ~ (1/n) sum_i I(Xi; Yi | Y^{i-1}) — feedback-aware.

    Measures how much the current decision + past outcomes explain the next
    outcome. Rising directed info = the agent's decisions are increasingly
    causally relevant (it is LEARNING). For order-1 it conditions on the
    previous outcome: I(Xi; Yi | Yi-1) = H(Yi|Yi-1) - H(Yi|Yi-1,Xi).
    """
    n = min(len(x), len(y))
    if n <= order + 1:
        return 0.0
    x, y = x[:n], y[:n]
    # p(y_i | y_{i-1})
    h_y_given_prev = 0.0
    pairs = Counter(zip(y[order:], y[order - 1:-1]))
    tot = n - order
    for (yi, yp), c in pairs.items():
        py_yp = c / tot
        h_y_given_prev -= py_yp * _log2(c / sum(1 for (a, b), cc in pairs.items()
                                                if b == yp for _ in range(cc)))
    # p(y_i | y_{i-1}, x_i)
    triples = Counter(zip(y[order:], y[order - 1:-1], x[order:]))
    h_y_given_prev_x = 0.0
    ctx_tot: Dict[Tuple[str, str], int] = defaultdict(int)
    for (yi, yp, xi), c in triples.items():
        ctx_tot[(yp, xi)] += c
    for (yi, yp, xi), c in triples.items():
        py_ypx = c / tot
        h_y_given_prev_x -= py_ypx * _log2(c / ctx_tot[(yp, xi)])
    return max(0.0, h_y_given_prev - h_y_given_prev_x)


class DecisionEntropy:
    """Full source-theory model of a journaled decision stream."""

    def __init__(self, journal_path: Optional[str] = None):
        self.journal_path = journal_path
        self.decisions: List[str] = []     # X^n
        self.outcomes: List[str] = []      # Y^n
        if journal_path and os.path.exists(journal_path):
            self._load_journal(journal_path)

    def _load_journal(self, path: str) -> None:
        """Read DeterministicActionJournal records: action=X, outcome=Y."""
        import json
        try:
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        e = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    action = e.get("action") or e.get("intent")
                    outcome = e.get("outcome")
                    if action:
                        self.decisions.append(str(action))
                        self.outcomes.append(str(outcome or "ok"))
        except OSError:
            pass

    def add(self, decision: str, outcome: str = "ok") -> None:
        self.decisions.append(decision)
        self.outcomes.append(outcome)

    def clear(self) -> None:
        self.decisions.clear()
        self.outcomes.clear()

    # ---- the five measures ----------------------------------------- #
    def H(self) -> float:
        return entropy(self.decisions)

    def rate(self, order: int = 1) -> float:
        return entropy_rate(self.decisions, order=order)

    def I(self) -> float:
        return mutual_information(self.decisions, self.outcomes)

    def capacity(self) -> float:
        return channel_capacity_estimate(self.decisions, self.outcomes)

    def directed(self, order: int = 1) -> float:
        return directed_information_rate(self.decisions, self.outcomes, order=order)

    def R(self) -> float:
        return redundancy(self.decisions)

    # ---- interpretation -------------------------------------------- #
    def report(self) -> Dict[str, float]:
        H = self.H()
        r = self.rate()
        I = self.I()
        C = self.capacity()
        D = self.directed()
        R = self.R()
        alphabet = len(set(self.decisions))
        n = len(self.decisions)
        return {
            "samples": float(n),
            "alphabet": float(alphabet),
            "H": round(H, 4),
            "Hmax": round(max_entropy(alphabet), 4),
            "rate": round(r, 4),
            "I_XY": round(I, 4),
            "capacity": round(C, 4),
            "directed": round(D, 4),
            "redundancy": round(R, 4),
        }

    def interpret(self) -> List[str]:
        rep = self.report()
        out = []
        if rep["samples"] < 8:
            out.append("not enough decisions yet (need >= 8)")
            return out
        H, r, I, R = rep["H"], rep["rate"], rep["I_XY"], rep["redundancy"]
        if H < 0.15:
            out.append("HABITUAL: decisions nearly deterministic — scripted loop")
        elif H > 0.8 * rep["Hmax"]:
            out.append("CHAOTIC: near max entropy — no structure, explore or constrain")
        else:
            out.append("BALANCED: decision entropy in the explorable range")
        if r < 0.3 * H and H > 0.3:
            out.append("SEQUENTIAL: strong history dependence (r << H) — decisions chain")
        if I > 0.4:
            out.append("HIGH SIGNAL: decisions carry outcome-relevant info — channel is good")
        elif I < 0.05 and rep["samples"] > 16:
            out.append("LOW SIGNAL: decisions barely predict outcomes — revisit guardrails/tools")
        if R > 0.7:
            out.append("COMPRESSIBLE: high redundancy — dream-prune duplicate decision paths")
        return out

    def to_ascii(self) -> str:
        rep = self.report()
        lines = [
            "  INFO-THEORETIC SELF-MODEL (source theory)",
            f"  H={rep['H']:.3f}/{rep['Hmax']:.3f}  rate={rep['rate']:.3f}  "
            f"I(X;Y)={rep['I_XY']:.3f}  C={rep['capacity']:.3f}  "
            f"directed={rep['directed']:.3f}  R={rep['redundancy']:.2f}",
        ]
        for s in self.interpret():
            lines.append(f"    - {s}")
        return "\n".join(lines)

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
