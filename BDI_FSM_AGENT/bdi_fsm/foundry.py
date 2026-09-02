"""Brute Genetic Foundry — genetic actor-critic over symbolic plans.

* Genetic Actor: mutates / permutes / crosses over BDI plan templates
  and AST skeletons.
* Symbolic Critic: deterministic non-LLM evaluator — AST validity,
  test exit codes, memory footprint, latency (via sandbox runner).
* Pruning: drops low-fitness plans and duplicate recipes continuously
  (Non-TLStop doctrine — never halts during prune/learn).

Deterministic when seeded; pure stdlib. The actor's randomness is the
only source of variety (quorum-for-fun doctrine), everything else is
verifiable.
"""

import ast
import random
import time
from typing import Callable, Dict, List, Optional


def _now_iso():
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _gene_id(prefix, code):
    """Content-addressed plan id. A gene IS its code.

    Ids were f"GEN_{rng.randint(10000, 99999)}" -- 90,000 possible names for a
    population already at 739. Measured 2026-08-31: TWO ids already collided,
    each shared by two genuinely different bodies, and the birthday bound puts
    that at ~22 collisions by 2,000 plans. A genealogy keyed on a colliding id
    silently merges unrelated ancestries, so identity has to be fixed before
    lineage can mean anything.

    sha256 of the code also makes the desirable collision happen on purpose:
    two mutations that arrive at identical code ARE the same gene and now share
    one id, which is dedup rather than corruption.
    """
    import hashlib
    return "%s_%s" % (prefix, hashlib.sha256(
        (code or "").encode("utf-8", "replace")).hexdigest()[:10])


class SymbolicPlan:
    def __init__(self, plan_id: str, precondition: str,
                 code_template: str, fitness: float = 1.0,
                 kind: str = "plan"):
        self.plan_id = plan_id
        self.precondition = precondition
        self.code_template = code_template
        self.fitness = fitness
        self.kind = kind
        self.attempts = 0
        self.wins = 0
        # LINEAGE. produce_candidates knew the parents and dropped them on the
        # next line, so the pool had genetics with no genealogy: nothing could
        # trace an ancestry, credit a parent for a winning child, or measure
        # whether a line of descent was improving. Chris 2026-08-31: "start
        # catalogueing the lineages of code".
        self.parents = []          # plan_ids this was bred from
        self.op = "seed"           # seed | mutate | crossover | harvest
        self.born = None           # ISO timestamp of first synthesis

    def to_dict(self) -> dict:
        return {
            "plan_id": self.plan_id, "precondition": self.precondition,
            "code_template": self.code_template, "fitness": self.fitness,
            "kind": self.kind, "attempts": self.attempts, "wins": self.wins,
            "parents": list(getattr(self, "parents", []) or []),
            "op": getattr(self, "op", "seed"),
            "born": getattr(self, "born", None),
        }


class GeneticFoundry:
    """Actor-Critic loop over a population of symbolic plans."""

    def __init__(self, blackboard, seed: int = 42,
                 population: Optional[List[SymbolicPlan]] = None,
                 max_population: int = 64):
        self.bb = blackboard
        self.rng = random.Random(seed)
        self.population: List[SymbolicPlan] = population or []
        self.max_population = max_population
        self.critic: Optional[Callable[[SymbolicPlan], float]] = None

    def seed_plan(self, plan: SymbolicPlan) -> None:
        if len(self.population) < self.max_population:
            self.population.append(plan)

    def set_critic(self, critic: Callable[[SymbolicPlan], float]) -> None:
        self.critic = critic

    # -- GENETIC ACTOR ----------------------------------------------------
    def mutate(self, parent: SymbolicPlan) -> SymbolicPlan:
        """Mutation 1: swap a math operator; Mutation 2: swap return
        expression. Pure textual transformation of the template."""
        code = parent.code_template
        if "+" in code:
            code = code.replace("+", "*", 1)
        elif "*" in code:
            code = code.replace("*", "+", 1)
        if "return sum(" in code:
            code = code.replace("return sum(", "return max(", 1)
        elif "return max(" in code:
            code = code.replace("return max(", "return sum(", 1)
        child = SymbolicPlan(
            _gene_id("GEN", code),
            parent.precondition, code, fitness=0.5, kind=parent.kind)
        child.parents = [parent.plan_id]
        child.op = "mutate"
        child.born = _now_iso()
        return child

    def crossover(self, a: SymbolicPlan, b: SymbolicPlan) -> Optional[SymbolicPlan]:
        """Splice the body of a onto the signature of b (or vice versa)."""
        try:
            body_a = a.code_template.split("\n", 1)[1] if "\n" in a.code_template else a.code_template
            head_b = b.code_template.split("\n", 1)[0] if "\n" in b.code_template else b.code_template
            if "def " not in head_b or body_a.startswith("def "):
                return None
            child = f"{head_b}\n{body_a}"
            plan = SymbolicPlan(_gene_id("XO", child),
                                a.precondition, child, fitness=0.4, kind=a.kind)
            plan.parents = [a.plan_id, b.plan_id]
            plan.op = "crossover"
            plan.born = _now_iso()
            return plan
        except Exception:
            return None

    def produce_candidates(self, n: int = 3) -> List[SymbolicPlan]:
        """Actor phase: mutate + crossover the current population."""
        out: List[SymbolicPlan] = []
        if not self.population:
            return out
        for _ in range(n):
            parent = self.rng.choice(self.population)
            if self.rng.random() < 0.7:
                out.append(self.mutate(parent))
            else:
                other = self.rng.choice(self.population)
                child = self.crossover(parent, other)
                if child:
                    out.append(child)
        return out

    # -- SYMBOLIC CRITIC ---------------------------------------------------
    @staticmethod
    def ast_valid(code: str) -> bool:
        try:
            ast.parse(code)
            return True
        except SyntaxError:
            return False

    def evaluate(self, plan: SymbolicPlan, test_fn: Optional[Callable[[str], float]] = None) -> float:
        """Critic phase: deterministic score 0..1.
        If a test_fn is provided it overrides (e.g. sandbox exit code)."""
        plan.attempts += 1
        if test_fn is not None:
            score = float(test_fn(plan.code_template))
        else:
            score = 1.0 if self.ast_valid(plan.code_template) else 0.0
        plan.fitness = score
        if score > 0.5:
            plan.wins += 1
        self.bb.set_fitness(plan.plan_id, score)
        return score

    # -- NON-TLSTOP PRUNING -------------------------------------------------
    def prune(self, min_fitness: float = 0.3, max_attempts: int = 10) -> int:
        """Drop low-fitness / stale plans without halting. Returns count."""
        before = len(self.population)
        keep = [p for p in self.population
                if p.fitness >= min_fitness and p.attempts <= max_attempts]
        self.population = keep[:self.max_population]
        return before - len(self.population)

    def generation(self, n: int = 3, test_fn: Optional[Callable[[str], float]] = None) -> Dict[str, int]:
        """One full actor-critic generation. Returns stats."""
        produced = 0
        for cand in self.produce_candidates(n):
            self.evaluate(cand, test_fn)
            self.population.append(cand)
            produced += 1
        pruned = self.prune()
        return {"produced": produced, "pruned": pruned,
                "population": len(self.population)}

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
