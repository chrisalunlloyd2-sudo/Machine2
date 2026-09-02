"""ENGLISH FLUENCY DAG — performatives as a programmed syntax library that
feeds the Nash gate.

Chris directive: English syntax/order should become PROGRAMMED LIBRARIES
feeding the "game Nash endpoint" (theta* = log10(C_miss/C_false)). Here the DAG
is the syntax library: nodes are KQML performatives (tell / achieve / ask) with
variable slots; edges are grammatical ordering. Stringing variables through the
DAG produces English, and the output is scored by the BanLedger — fluency is a
higher log-odds, gated by the SAME Nash threshold that decides tool-use. That
shared gate is the coupling: "smarter = better across all domains" (language
and code converge on one decision-theoretic stop).

The canonical pipeline is webcrawl -> DefinitionStore -> EnglishDAG -> Nash
gate: a scraped variable (name=value) is strung into a grammatical sentence and
emitted only if its fluency clears theta*.

Deterministic, templated, zero LLM. "Not expecting Shakespeare — a robot is
perfect" (cat feathers acceptable; the grammar is a library, not a model).
"""
import re
from typing import Any, Dict, List, Optional, Tuple

from .bayes_engine import BanLedger, nash_threshold_dban

_VOWELS = "aeiouAEIOU"


def article(word: str) -> str:
    """a/an selection from the leading letter (phonetic-simple)."""
    if not word:
        return ""
    return "an" if word[0] in _VOWELS else "a"


def pluralize(word: str, count: int = 2) -> str:
    """Naive plural: singular for count 1, else +s (es for sibilants)."""
    if count == 1:
        return word
    if word.endswith(("s", "x", "z", "ch", "sh")):
        return word + "es"
    if word.endswith("y") and len(word) > 1 and word[-2] not in _VOWELS:
        return word[:-1] + "ies"
    return word + "s"


def agree_verb(subject: str, verb: str) -> str:
    """Third-person-singular agreement (he/she/it + verb)."""
    sing = subject.lower() in ("it", "he", "she", "this", "that") \
        or subject.lower() not in ("i", "you", "we", "they")
    if not sing:
        return verb
    if verb == "be":
        return "is"
    if verb == "have":
        return "has"
    if verb.endswith("s") or verb.endswith("x") or verb.endswith("ch") \
            or verb.endswith("sh") or verb.endswith("o"):
        return verb + "es"
    if verb.endswith("y") and len(verb) > 1 and verb[-2] not in _VOWELS:
        return verb[:-1] + "ies"
    return verb + "s"


class DAGNode:
    """One performative act (tell / achieve / ask) with variable slots."""

    def __init__(self, performative: str, name: str,
                 slots: Optional[Dict[str, str]] = None,
                 children: Optional[List["DAGNode"]] = None):
        self.performative = performative
        self.name = name
        self.slots = slots or {}
        self.children = children or []

    def add(self, node: "DAGNode") -> "DAGNode":
        self.children.append(node)
        return self

    def render(self, v: Optional[Dict[str, Any]] = None) -> str:
        """String this node's bound variables into a grammatical clause.

        Each node carries its OWN slots (its local variable scope); `v` (if
        given) overrides individual bindings for that call. This is what makes
        a DAG of performatives composable without cross-node slot collisions.
        """
        data = {**self.slots, **(v or {})}
        if self.performative == "tell":
            subj = str(data.get("subject", "it"))
            pred = str(data.get("predicate", "be"))
            obj = str(data.get("object", "ready"))
            pred = agree_verb(subj, pred)
            return f"{subj} {pred} {obj}."
        if self.performative == "achieve":
            verb = str(data.get("verb", "run"))
            obj = str(data.get("object", "the task"))
            return f"I will {verb} {obj}."
        if self.performative == "ask":
            wh = str(data.get("wh", "what"))
            obj = str(data.get("object", "this"))
            return f"{wh} is {obj}?"
        return str(data.get("object", ""))


def string_variable(name: str, value: str, kind: str = "assignment") -> str:
    """String a DefinitionStore record (name=value) into grammatical English.

    assignment -> "name is set to value."
    keyvalue   -> "name is value."
    function   -> "name is defined as a function."
    """
    if kind == "function":
        return f"{name} is defined as a function."
    if kind == "keyvalue":
        return f"{name} is {value}."
    return f"{name} is set to {value}."


class FluencyGate:
    """Scores an utterance through the BanLedger and gates it on theta*.

    The utterance is a hypothesis; grammatical features (terminal punctuation,
    subject-verb agreement, article presence) are the evidence. A fluent
    sentence concentrates the posterior and clears the Nash threshold — the
    same stop the tool-observer uses, which is the cross-domain coupling.
    """

    def __init__(self, c_miss: float = 10.0, c_false: float = 1.0):
        self.theta_dban = nash_threshold_dban(c_miss, c_false)
        self.c_miss = c_miss
        self.c_false = c_false

    def _features(self, sentence: str) -> List[Tuple[str, float, float]]:
        """(name, p_h, p_not_h) evidence pairs for the ledger."""
        ev: List[Tuple[str, float, float]] = []
        s = sentence.strip()
        if s.endswith((".", "?", "!")):
            ev.append(("terminal", 0.9, 0.5))
        else:
            ev.append(("no-terminal", 0.3, 0.7))
        if re.search(r"\b(is|are|was|were|has|have|will)\b", s):
            ev.append(("has-copula", 0.85, 0.5))
        if re.search(r"\b(a|an|the)\b", s):
            ev.append(("has-article", 0.8, 0.5))
        if re.search(r"\b(?:an [aeiou]|a [^aeiou])\b", s, re.I):
            ev.append(("correct-article", 0.9, 0.6))
        return ev

    def score(self, sentence: str) -> Tuple[float, bool]:
        """Return (dban, fired) for an utterance against theta*."""
        ledger = BanLedger(threshold_dban=self.theta_dban)
        ledger.register("utterance", prior_prob=0.5)
        for name, p_h, p_not_h in self._features(sentence):
            ledger.observe("utterance", p_h, p_not_h)
        gate = ledger.evaluate_gate()
        if gate is None:
            return ledger.scores.get("utterance", 0.0), False
        return gate[1], True

    def emit_best(self, utterances, fallback):
        """Epsilon short-circuit: score candidates, emit the best if it clears
        theta*, else emit the deterministic fallback. Never loop on fluency —
        when every rendered utterance falls below the Nash threshold, we emit
        the simplest grammatical candidate ("a robot is perfect") and move on.

        Returns (text, dban, used_fallback).
        """
        best, best_dban = None, float("-inf")
        for u in utterances:
            dban, _ = self.score(u)
            if dban > best_dban:
                best, best_dban = u, dban
        if best is not None and best_dban >= self.theta_dban:
            return best, best_dban, False
        return fallback, self.score(fallback)[0], True


def render_dag(root: DAGNode, v: Optional[Dict[str, Any]] = None) -> str:
    """Walk the DAG (pre-order) and join clauses into one sentence block.

    Each node strings its own bound slots; `v` is an optional shared override.
    """
    parts = [root.render(v)]
    for c in root.children:
        parts.append(render_dag(c, v))
    return " ".join(p for p in parts if p)


if __name__ == "__main__":
    g = FluencyGate()
    for s in ["max_retries is set to 5.",
              "an apple is a fruit.",
              "a apple is bad grammar"]:
        dban, fired = g.score(s)
        print(f"{dban:7.2f} dBan fired={fired}  {s!r}  (theta*={g.theta_dban:.2f})")
