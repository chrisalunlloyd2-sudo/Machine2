"""realm.py — logical realms: hierarchical sub-databases + choice trees.

Chris 2026-08-15: logical realms are (1) SUB-DATABASES — "a person, place, or
thing of concept goes in the child concept like a sub-folder you navigate to" —
and (2) nested CHOICE TREES — "choice tree A is in choice tree B" (A->B), where
the -> transition is "a combination of the markov but SEPARATE": weighted,
probability-driven, with a hook+direction the batch terminal shell reads:

    read direction -> do computation -> next choice from a list of computations

These choice trees are MAPS OF CONVERSATIONS: where the conversation should go
based on probability + multi-step long-horizon task feedback, applied
incrementally. Pure stdlib, deterministic, zero-LLM.
"""

from __future__ import annotations

import random
from typing import Any, Callable, Dict, List, Optional


class Realm:
    """A logical realm: hierarchical sub-folders holding entities.

    Entities (person/place/thing/concept) always land in their child concept —
    a nested namespace you navigate like folders. Nothing is ever deleted.
    """

    def __init__(self, name: str = "root"):
        self.name = name
        self.subrealms: Dict[str, "Realm"] = {}
        self.entities: List[str] = []

    def navigate(self, *concepts: str) -> "Realm":
        """Walk (creating as needed) down to a sub-folder. Deterministic."""
        r = self
        for c in concepts:
            r = r.subrealms.setdefault(c, Realm(c))
        return r

    def place(self, entity: str, *concepts: str) -> "Realm":
        """Place an entity under its child concept path (sub-folder)."""
        self.navigate(*concepts).entities.append(entity)
        return self

    def lookup(self, *concepts: str) -> List[str]:
        """List entities in a sub-folder (or [] if absent)."""
        r = self
        for c in concepts:
            if c not in r.subrealms:
                return []
            r = r.subrealms[c]
        return list(r.entities)

    def render(self, depth: int = 0) -> List[str]:
        lines = [f"{'  ' * depth}{self.name}/"]
        for e in self.entities:
            lines.append(f"{'  ' * (depth + 1)}* {e}")
        for sub in sorted(self.subrealms):
            lines.extend(self.subrealms[sub].render(depth + 1))
        return lines


class ChoiceTree:
    """Nested choice tree: Markov-weighted transitions + incremental feedback.

    "choice tree A is in choice tree B" = add_node(A, parent=B); the B->A edge
    carries a weight. Traversal reads a hook (direction), runs the computation
    via an injected terminal, and picks the next child by probability.
    reward()/propagate() apply long-horizon feedback incrementally.
    """

    def __init__(self, seed: int = 0):
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.rng = random.Random(seed)

    def add_node(self, node_id: str, hook: Optional[str] = None,
                 parent: Optional[str] = None) -> str:
        """Add a node; if parent given, wire the B->A edge (A is in B)."""
        if node_id not in self.nodes:
            self.nodes[node_id] = {"hook": hook, "parent": parent,
                                   "children": [], "weights": {}}
        if parent is not None:
            self.add_node(parent)
            p = self.nodes[parent]
            if node_id not in p["children"]:
                p["children"].append(node_id)
                p["weights"][node_id] = 1.0  # uniform prior (separate Markov)
            self.nodes[node_id]["parent"] = parent
        return node_id

    def children(self, node_id: str) -> List[str]:
        return sorted(self.nodes[node_id]["children"])

    def choose(self, node_id: str) -> Optional[str]:
        """Probability-weighted next choice (the separate Markov transition)."""
        node = self.nodes[node_id]
        if not node["children"]:
            return None
        total = sum(node["weights"].get(c, 1.0) for c in node["children"])
        r = self.rng.random() * total
        acc = 0.0
        for c in sorted(node["children"]):
            acc += node["weights"].get(c, 1.0)
            if r <= acc:
                return c
        return node["children"][-1]

    def best(self, node_id: str) -> Optional[str]:
        """Deterministic argmax (ties -> lexicographically smallest)."""
        node = self.nodes[node_id]
        if not node["children"]:
            return None
        # highest weight first, tie -> lexicographically smallest
        return sorted(node["children"],
                      key=lambda c: (-node["weights"].get(c, 1.0), c))[0]

    def reward_edge(self, parent_id: str, child_id: str, value: float) -> None:
        """Incremental feedback: reinforce one B->A transition weight."""
        if parent_id in self.nodes and child_id in self.nodes[parent_id]["children"]:
            w = self.nodes[parent_id]["weights"]
            w[child_id] = w.get(child_id, 1.0) + max(0.0, value)

    def propagate(self, trace: List[str], reward: float, discount: float = 0.9) -> None:
        """Long-horizon feedback: reinforce every edge in the trace, discounted."""
        for i in range(len(trace) - 1):
            self.reward_edge(trace[i], trace[i + 1], reward * (discount ** i))

    def seed_from_relations(self, relations: List[Tuple[str, str, float]],
                            gain: float = 1.0) -> int:
        """Boost edge weights from directional relations (e.g. pos_db verb->noun).

        For each (src, dst, weight) relation, boost every edge whose parent
        name contains src and child name contains dst. Returns boosted count.
        This is how learned directional patterns tune the separate Markov.
        """
        boosted = 0
        for src, dst, w in relations:
            s, d = src.lower(), dst.lower()
            for pid, node in self.nodes.items():
                if s not in pid.lower():
                    continue
                for cid in node["children"]:
                    if d in cid.lower():
                        self.reward_edge(pid, cid, w * gain)
                        boosted += 1
        return boosted

    def traverse(self, start_id: str, run: Callable[[str], Any],
                 max_steps: int = 10) -> List[str]:
        """read direction -> do computation -> next choice. Returns the trace."""
        trace: List[str] = [start_id]
        node_id = start_id
        for _ in range(max_steps):
            hook = self.nodes[node_id]["hook"]
            if hook is not None:
                run(hook)
            nxt = self.choose(node_id)
            if nxt is None:
                break
            trace.append(nxt)
            node_id = nxt
        return trace
