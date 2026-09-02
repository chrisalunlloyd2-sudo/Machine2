"""EXHAUSTIVE TASK TREE ENGINE — per-task exhaustive decision trees + DAG.

Chris directive 2026-08-11: "the bdi portion should make a exhaustive decision
tree for every task ... each step compare result and then take next step and
make a new tree and dag and select the statistically most likely based on the
lexicon ask."

Doctrine (no LLM in the decision core — LLM stays for serendipity only):
  1. EVERY task gets an exhaustive tree of candidate actions, not one guess.
  2. Each step: pick the statistically most likely action (Bayesian posterior
     from the DAG, filtered by the lexicon ask's performative), execute it,
     COMPARE the result, record it, then build a NEW tree rooted at the new
     state — trees are born, live one step, and die into the DAG.
  3. The TaskDAG is the persistent statistical memory: state -> action ->
     win/fail counts. It IS the learned policy. Every executed step merges
     into it, so the next task starts smarter.
  4. FOW: candidate actions are filtered by what the agent can see (hex
     visibility, 1-hop) and what the lexicon ask allows (performative match).
  5. ADD-only, never-mistakes-twice (blocked actions never re-expand).

Selection: Bayesian posterior p = (wins+1)/(total+2) (Beta(1,1) prior) with a
UCB-style exploration bonus c*sqrt(ln(global_total)/n) so unseen actions get
a fair chance while proven ones dominate. Ties resolve deterministically.

Pure stdlib. Zero LLM. Every tree renders ASCII and persists to
decision_trees/task_tree_<ts>.txt + the DAG to decision_trees/task_dag.json.
"""

import hashlib
import json
import math
import os
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# state fingerprints
# ---------------------------------------------------------------------------

def state_fp(state_sig: str) -> str:
    """Canonical state fingerprint (sha256 prefix 12)."""
    return hashlib.sha256(state_sig.encode()).hexdigest()[:12]


def sig_of(task: str, step: int, context: str = "") -> str:
    """State signature: task kind + step + compact context."""
    return f"{task}|{step}|{context}"


# ---------------------------------------------------------------------------
# TaskDAG — persistent statistical decision memory
# ---------------------------------------------------------------------------

class TaskDAG:
    """Directed acyclic graph of states -> actions -> outcomes.

    Node:  state_fp -> {"sig": original signature, "actions": {action: stats}}
    stats: {"w": wins, "f": fails, "n": total, "last": outcome, "ts": epoch}

    merge(state_sig, action, outcome) updates counts.  best(state_sig, ask)
    returns the statistically most likely action filtered by the ask.
    """

    def __init__(self, path: Optional[str] = None):
        self.path = path
        self.nodes: Dict[str, Dict[str, Any]] = {}
        if path and os.path.exists(path):
            try:
                self.nodes = json.load(open(path))
            except Exception:
                self.nodes = {}

    # -- persistence --------------------------------------------------------
    def save(self) -> str:
        if self.path:
            tmp = self.path + ".tmp"
            json.dump(self.nodes, open(tmp, "w"), indent=1)
            os.replace(tmp, self.path)
        return self.path or ""

    # -- mutation -----------------------------------------------------------
    def merge(self, state_sig: str, action: str, outcome: str) -> None:
        fp = state_fp(state_sig)
        node = self.nodes.setdefault(fp, {"sig": state_sig[:80], "actions": {}})
        acts = node["actions"]
        st = acts.setdefault(action, {"w": 0, "f": 0, "n": 0, "last": "", "ts": 0.0})
        if outcome == "ok":
            st["w"] += 1
        else:
            st["f"] += 1
        st["n"] = st["w"] + st["f"]
        st["last"] = outcome
        st["ts"] = time.time()
        node["actions"] = acts
        self.nodes[fp] = node

    # -- selection ----------------------------------------------------------
    @staticmethod
    def _bayes(w: int, n: int, total_explored: int, c: float = 1.2) -> float:
        """Selection score.

        Tried actions: pure Bayesian posterior mean Beta(1,1) = (w+1)/(n+2).
        NO exploration bonus on tried actions — a failed action must rank
        BELOW untried ones (never-mistakes-twice: don't re-prefer failures).
        Untried actions: small exploration incentive so the tree actually
        tries new branches (variety is the spice of life doctrine).
        """
        if n == 0:
            return c * math.sqrt(math.log(total_explored + 2)) * 0.1
        return (w + 1.0) / (n + 2.0)

    def best(self, state_sig: str, ask: Optional[str] = None,
             allowed: Optional[List[str]] = None,
             blocked: Optional[List[str]] = None) -> Tuple[Optional[str], Dict]:
        """Most statistically likely action for a state, filtered by ask.

        ask:      performative from the lexicon (e.g. "save_code") — only
                  actions whose name contains the ask (or any ask) qualify.
        allowed:  explicit allowlist (FOW-visible actions).
        blocked:  never-mistakes-twice list (never re-expand).
        Returns (action, stats-of-action) or (None, {}) if no candidate.
        """
        fp = state_fp(state_sig)
        node = self.nodes.get(fp)
        if not node:
            return None, {}
        blocked = set(blocked or [])
        allowed = set(allowed) if allowed else None
        total = sum(a["n"] for a in node["actions"].values())
        best_a, best_s, best_score = None, None, -1.0
        for action, st in sorted(node["actions"].items()):
            if action in blocked:
                continue
            if allowed and action not in allowed:
                continue
            if ask and ask not in action:
                continue
            score = self._bayes(st["w"], st["n"], total)
            # deterministic tie-break: lexicographic on (score, action)
            if score > best_score or (score == best_score and action < (best_a or "")):
                best_a, best_s, best_score = action, st, score
        return best_a, best_s or {}

    def stats(self) -> Dict:
        nactions = sum(len(n["actions"]) for n in self.nodes.values())
        return {"states": len(self.nodes), "actions": nactions,
                "trials": sum(a["n"] for n in self.nodes.values() for a in n["actions"].values())}

    def to_ascii(self, limit: int = 40) -> str:
        lines = [f"TaskDAG — {self.stats()['states']} states, "
                 f"{self.stats()['actions']} action-edges, "
                 f"{self.stats()['trials']} trials"]
        for fp, node in sorted(self.nodes.items()):
            best_a, best_s = None, None
            for a, s in node["actions"].items():
                if best_s is None or s["w"] / max(1, s["n"]) > best_s["w"] / max(1, best_s["n"]):
                    best_a, best_s = a, s
            lines.append(f"  {fp} [{node['sig'][:44]}] -> "
                         f"{best_a} ({best_s['w']}w/{best_s['f']}f)" if best_a else
                         f"  {fp} [{node['sig'][:44]}] -> (no actions)")
            if len(lines) >= limit + 1:
                lines.append("  ...")
                break
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# TaskTree — one exhaustive tree per task step
# ---------------------------------------------------------------------------

class TaskNode:
    __slots__ = ("id", "state_sig", "action", "depth", "parent",
                 "children", "outcome", "stats", "explored")

    def __init__(self, state_sig: str, action: Optional[str], depth: int,
                 parent: Optional["TaskNode"] = None):
        self.id = state_fp(state_sig + "|" + (action or "root"))
        self.state_sig = state_sig
        self.action = action
        self.depth = depth
        self.parent = parent
        self.children: List["TaskNode"] = []
        self.outcome: Optional[str] = None
        self.stats: Dict = {"w": 0, "f": 0, "n": 0}
        self.explored = False

    def add_child(self, state_sig: str, action: str) -> "TaskNode":
        c = TaskNode(state_sig, action, self.depth + 1, self)
        self.children.append(c)
        return c

    def path(self) -> List[str]:
        p = []
        n = self
        while n:
            if n.action:
                p.append(n.action)
            n = n.parent
        return list(reversed(p))


class TaskTree:
    """Exhaustive candidate tree for ONE task step.

    expand() grows ALL candidate actions for the current state (filtered by
    ask/performative, FOW visibility, NMTD blocks, DAG priors). select()
    picks the statistically most likely leaf. After execution + comparison
    the caller records the outcome (merging into the DAG) and builds a NEW
    tree for the next step — born, live one step, die into the DAG.
    """

    def __init__(self, task: str, step: int, dag: TaskDAG,
                 candidates_fn: Callable[[str], List[str]],
                 ask: Optional[str] = None,
                 context: str = "",
                 max_branch: int = 12):
        self.task = task
        self.step = step
        self.dag = dag
        self.candidates_fn = candidates_fn
        self.ask = ask
        self.context = context
        self.max_branch = max_branch
        self.root = TaskNode(self._sig(), None, 0)
        self.nodes: List[TaskNode] = [self.root]
        self.leaves: List[TaskNode] = []
        self.rendered = ""

    def _sig(self) -> str:
        return sig_of(self.task, self.step, self.context)

    # -- exhaustive expansion ------------------------------------------------
    def expand(self, blocked: Optional[List[str]] = None,
               allowed: Optional[List[str]] = None) -> int:
        """Enumerate every candidate action for this state. Returns count."""
        candidates = self.candidates_fn(self._sig()) or []
        blocked = set(blocked or [])
        allowed = set(allowed) if allowed else None
        total_explored = self.dag.stats()["trials"] + 1

        # score each candidate with DAG priors + ask filter
        scored = []
        for a in candidates:
            if a in blocked:
                continue
            if allowed and a not in allowed:
                continue
            if self.ask and self.ask not in a:
                continue
            node = self.dag.nodes.get(state_fp(self._sig()))
            st = node["actions"].get(a, {"w": 0, "f": 0, "n": 0}) if node else {"w": 0, "f": 0, "n": 0}
            score = self.dag._bayes(st["w"], st["n"], total_explored)
            scored.append((score, a))
        # exhaustive: keep ALL candidates up to max_branch (hard cap for RAM)
        scored.sort(key=lambda t: (-t[0], t[1]))
        kept = scored[: self.max_branch]
        for score, a in kept:
            child = self.root.add_child(self._sig(), a)
            node = self.dag.nodes.get(state_fp(self._sig()))
            st = node["actions"].get(a, {"w": 0, "f": 0, "n": 0}) if node else {"w": 0, "f": 0, "n": 0}
            child.stats = dict(st)
            child.explored = True
            self.nodes.append(child)
        self.root.explored = True
        self.leaves = list(self.root.children)
        return len(kept)

    # -- selection -----------------------------------------------------------
    def select(self, prefer: Optional[str] = None) -> Optional[TaskNode]:
        """Best leaf: prefer-match first, then Bayesian score, then alpha."""
        if not self.leaves:
            return None
        if prefer:
            for c in self.leaves:
                if prefer in c.action:
                    return c
        # highest score; deterministic tie-break (alphabetically first)
        total = self.dag.stats()["trials"] + 1
        scored = sorted(self.leaves,
                        key=lambda c: (-self.dag._bayes(c.stats["w"], c.stats["n"], total),
                                       c.action))
        return scored[0] if scored else None

    # -- rendering -----------------------------------------------------------
    def render_ascii(self) -> str:
        """Tree with per-leaf score + path."""
        total = self.dag.stats()["trials"] + 1
        lines = [f"TaskTree — '{self.task}' step {self.step} "
                 f"(ask={self.ask or 'any'})"]
        lines.append(f"  state: {self._sig()}")
        for c in sorted(self.leaves, key=lambda n: -self.dag._bayes(n.stats['w'], n.stats['n'], total)):
            sc = self.dag._bayes(c.stats["w"], c.stats["n"], total)
            hist = f"{c.stats['w']}w/{c.stats['f']}f" if c.stats["n"] else "new"
            lines.append(f"  ├─ {c.action}  (score {sc:.3f}, {hist})")
        chosen = self.select()
        if chosen:
            lines.append(f"  → CHOSEN: {chosen.action}  "
                         f"path={chosen.path()}")
        self.rendered = "\n".join(lines)
        return self.rendered


# ---------------------------------------------------------------------------
# TaskTreeRunner — the per-task loop: expand -> select -> execute -> compare
# -> record -> NEW tree. Born, live one step, die into the DAG.
# ---------------------------------------------------------------------------

class TaskTreeRunner:
    """Drives one task through exhaustive trees.

    executor(action, state_sig) -> {"ok": bool, "result": str, "quality": float}
    Runs until: task completes (ok + quality gate) or max_steps reached.
    Every step merges its outcome into the DAG (statistical memory) and
    builds a brand-new tree for the next step from the updated DAG.
    """

    def __init__(self, task: str, dag: TaskDAG,
                 candidates_fn: Callable[[str], List[str]],
                 executor: Callable[[str, str], Dict],
                 ask: Optional[str] = None,
                 context: str = "",
                 max_steps: int = 5,
                 quality_gate: float = 0.5,
                 blocked: Optional[List[str]] = None,
                 tree_dir: Optional[str] = None):
        self.task = task
        self.dag = dag
        self.candidates_fn = candidates_fn
        self.executor = executor
        self.ask = ask
        self.context = context
        self.max_steps = max_steps
        self.quality_gate = quality_gate
        self.blocked = list(blocked or [])
        self.tree_dir = tree_dir
        self.steps: List[Dict] = []
        self.trees: List[TaskTree] = []

    def _persist(self, tree: TaskTree, idx: int) -> None:
        if not self.tree_dir:
            return
        os.makedirs(self.tree_dir, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        safe = "".join(c if c.isalnum() else "_" for c in self.task)[:40]
        p = os.path.join(self.tree_dir, f"task_tree_{ts}_{safe}_s{idx}.txt")
        with open(p, "w") as f:
            f.write(tree.rendered + "\n")
            f.write("\nDAG after step:\n" + self.dag.to_ascii(20) + "\n")
        # keep a rolling 'latest'
        latest = os.path.join(self.tree_dir, "task_tree_latest.txt")
        with open(latest, "w") as f:
            f.write(tree.rendered + "\n")

    def run(self, prefer: Optional[str] = None) -> Dict:
        """Full task loop. Returns summary with all trees + outcomes."""
        state = self.context
        fail_blocked = list(self.blocked)  # NMTD: failures never retried this task
        for step in range(1, self.max_steps + 1):
            tree = TaskTree(self.task, step, self.dag, self.candidates_fn,
                            ask=self.ask, context=state)
            n = tree.expand(blocked=fail_blocked)
            if n == 0:
                # exhausted: no candidates — record and stop
                rec = {"step": step, "status": "no-candidates", "state": state,
                       "tree": tree.render_ascii()}
                self.steps.append(rec)
                self.trees.append(tree)
                break
            chosen = tree.select(prefer=prefer)
            if chosen is None:
                rec = {"step": step, "status": "no-selection", "state": state}
                self.steps.append(rec)
                self.trees.append(tree)
                break
            # execute + compare
            res = self.executor(chosen.action, tree._sig()) or {}
            outcome = "ok" if res.get("ok") else "fail"
            self.dag.merge(tree._sig(), chosen.action, outcome)
            if outcome == "fail":
                fail_blocked.append(chosen.action)  # never-mistakes-twice
            rec = {
                "step": step, "state": state, "action": chosen.action,
                "path": chosen.path(), "outcome": outcome,
                "result": (res.get("result") or "")[:160],
                "quality": res.get("quality", 0.0),
            }
            self.steps.append(rec)
            self.trees.append(tree)
            self._persist(tree, step)
            # compare result -> decide next state (new tree rooted here)
            if outcome == "ok" and res.get("quality", 0.0) >= self.quality_gate:
                rec["status"] = "complete"
                break
            # move on: carry the result as new context (next tree, new state)
            carry = (res.get("result") or "")[:60].replace("\n", " ")
            state = f"{state}|{chosen.action}:{carry}" if state else f"{chosen.action}:{carry}"
        else:
            rec = {"step": self.max_steps, "status": "max-steps"}
            self.steps.append(rec)

        return {
            "task": self.task, "ask": self.ask, "steps": self.steps,
            "completed": any(s.get("status") == "complete" for s in self.steps),
            "dag": self.dag.stats(),
            "renders": [t.rendered for t in self.trees],
            "last_state": state,
        }
