"""SUBSUMPTION DAG UNIFICATION CACHING (memoized).

Chris roadmap item: "Subsumption DAG unification caching (memoized)".

Given the formal kernel's canonical GraphNodes, two graphs are UNIFIABLE
when one structurally subsumes the other (same operator skeleton, variables
free to bind). We cache unification results keyed by graph hashes so a
recurring shape is resolved in O(1) after the first call.

Doctrine (ADD-only, never-mistakes-twice, never-code-twice):
  - unify(new, known) -> (True, subst) means the new graph is a MORE SPECIFIC
    instance of a known shape -> we can REUSE the known plan (memoized).
  - unify(known, new) direction also checked -> new shape generalizes known.
  - Every unify result is memoized in unify_cache.json so future calls are
    O(1) — the DAG is the cache.

Pure stdlib. Zero LLM.
"""

import hashlib
import json
import os
from typing import Any, Dict, List, Optional, Tuple


def unify(a: Dict[str, Any], b: Dict[str, Any],
          subst: Optional[Dict[str, str]] = None) -> Optional[Dict[str, str]]:
    """First-order structural unification of two normalized GraphNodes.

    Returns a substitution dict (var -> binding) if they unify, else None.
    Variables are nodes with op == 'VAR' (or name starting with 'v' in
    LOAD_VAR position). Constants must match exactly.
    """
    subst = dict(subst or {})

    def _var(n: Dict[str, Any]) -> Optional[str]:
        if n.get("op") == "VAR":
            return str(n.get("name") or n.get("value") or "")
        if n.get("op") == "LOAD_VAR":
            nm = str(n.get("name") or "")
            if nm.startswith("v") and nm[1:].isdigit():
                return nm
        return None

    def _walk(x: Dict[str, Any], y: Dict[str, Any]) -> bool:
        vx, vy = _var(x), _var(y)
        if vx is not None:
            key = "$" + vx
            if key in subst:
                return subst[key] == json.dumps(y, sort_keys=True)
            subst[key] = json.dumps(y, sort_keys=True)
            return True
        if vy is not None:
            key = "$" + vy
            if key in subst:
                return subst[key] == json.dumps(x, sort_keys=True)
            subst[key] = json.dumps(x, sort_keys=True)
            return True
        if x.get("op") != y.get("op"):
            return False
        if x.get("value") is not None or y.get("value") is not None:
            if x.get("value") != y.get("value"):
                return False
        if (x.get("name") or None) != (y.get("name") or None):
            # allow variable-position names to differ if either side is a VAR
            if not (_var(x) or _var(y)):
                return False
        cx, cy = x.get("children", []), y.get("children", [])
        if len(cx) != len(cy):
            return False
        return all(_walk(xx, yy) for xx, yy in zip(cx, cy))

    if not _walk(a, b):
        return None
    return subst


class UnifyCache:
    """Memoized subsumption cache.

    Cache keys: (hashA, hashB). Value: (unifies, subst-json or None).
    Also keeps a per-shape index: shape_hash -> [instance hashes], so we
    can answer "does anything known subsume this new graph?" in O(shapes).
    Persisted to unify_cache.json (ADD-only append + index).
    """

    def __init__(self, path: Optional[str] = None):
        self.path = path
        self.cache: Dict[str, Any] = {"pairs": {}, "shape_index": {}}
        if path and os.path.exists(path):
            try:
                self.cache = json.load(open(path))
            except Exception:
                self.cache = {"pairs": {}, "shape_index": {}}

    def save(self) -> None:
        if self.path:
            tmp = self.path + ".tmp"
            json.dump(self.cache, open(tmp, "w"))
            os.replace(tmp, self.path)

    # -- memoized lookup ------------------------------------------------
    def lookup(self, ha: str, hb: str) -> Optional[Tuple[bool, Optional[Dict]]]:
        """Return cached (unifies, subst) for a hash pair, or None if new."""
        v = self.cache["pairs"].get(f"{ha}|{hb}")
        if v is None:
            return None
        return v[0], (v[1] if v[1] is not None else None)

    def store(self, ha: str, hb: str, unifies: bool,
              subst: Optional[Dict[str, str]]) -> None:
        self.cache["pairs"][f"{ha}|{hb}"] = [unifies,
                                             json.dumps(subst) if subst else None]

    # -- shape index -----------------------------------------------------
    def index_shape(self, shape_hash: str, instance_hash: str) -> None:
        idx = self.cache["shape_index"].setdefault(shape_hash, [])
        if instance_hash not in idx:
            idx.append(instance_hash)

    def shape_members(self, shape_hash: str) -> List[str]:
        return self.cache["shape_index"].get(shape_hash, [])

    def stats(self) -> Dict[str, int]:
        return {"pairs": len(self.cache["pairs"]),
                "shapes": len(self.cache["shape_index"])}


class SubsumptionDAG:
    """DAG of shapes with memoized unification.

    add(graph) -> 'new' | 'subsumed' | 'generalizer'
      - 'new':        no known shape unifies -> registered as its own shape
      - 'subsumed':   a known shape subsumes it -> memoized, never re-added
      - 'generalizer':it subsumes a known shape -> replaces/augments index
    Every check is memoized by hash pair — O(1) on repeat.
    """

    def __init__(self, cache: UnifyCache):
        self.cache = cache
        self.shapes: Dict[str, Dict[str, Any]] = {}  # shape_hash -> canonical

    def add(self, graph: Dict[str, Any]) -> str:
        from bdi_fsm.foundry_kernel import normalize, graph_hash
        canon = normalize(graph)
        h = graph_hash(graph)
        # exact match first
        if h in self.shapes:
            return "new"  # already registered (dedup)
        # subsumption sweep over known shapes (memoized per pair)
        for shape_hash, shape in self.shapes.items():
            memo = self.cache.lookup(shape_hash, h)
            if memo is None:
                subst = unify(shape, canon)
                memo = (subst is not None, subst)
                self.cache.store(shape_hash, h, memo[0], memo[1])
            if memo[0]:
                self.cache.index_shape(shape_hash, h)
                return "subsumed"
        # reverse: does the new graph subsume any known shape? (generalizer)
        for shape_hash, shape in list(self.shapes.items()):
            memo = self.cache.lookup(h, shape_hash)
            if memo is None:
                subst = unify(canon, shape)
                memo = (subst is not None, subst)
                self.cache.store(h, shape_hash, memo[0], memo[1])
            if memo[0]:
                # new graph is more general — it becomes the shape
                self.shapes[h] = canon
                self.cache.index_shape(h, shape_hash)
                del self.shapes[shape_hash]
                return "generalizer"
        self.shapes[h] = canon
        return "new"

    def stats(self) -> Dict[str, Any]:
        return {"shapes": len(self.shapes), "cache": self.cache.stats()}

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
