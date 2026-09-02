"""WORLD MODEL — sense of other: entity DAGs with temporal identity.

Chris directive (2026-08-13): the agent must model OTHER entities it
interacts with — "distinguish the symbolic reals in different days", keep a
DAG per entity, prune exactly as much as it learns, and render to a private
repo (scrubbed). Scope: SELF + INFRASTRUCTURE (servers/nodes/websites/repos),
NOT other people (privacy).

Each entity has a STABLE identity (deterministic hash of type + canonical
key), so the same server today is the same server yesterday — observations
MERGE into its DAG rather than spawning a new one. A node is an observed
attribute (with a small value-history, so "changed since yesterday" is
answerable); an edge is a relation. The DAG grows to an optimum size, then
prunes exactly as much as it learns (lowest utility first) — steady-state.

render() returns a scrubbed projection (PII redacted) — not live state.

Pure stdlib. Deterministic. Zero LLM.
"""
import hashlib
import json
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

# ---- PII / secret scrub patterns (deterministic redaction) ----------------
SCRUB_PATTERNS: List[Tuple["re.Pattern", str]] = [
    (re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"), "<email>"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]+\b"), "<github_token>"),
    (re.compile(r"\bsk-[A-Za-z0-9]+\b"), "<api_key>"),
    (re.compile(r"\b(?:4[0-9]{3}[ -]?){3}[0-9]{4}\b"), "<card>"),
    (re.compile(r"\b(?:\+?\d{1,2}[ -]?)?\(?\d{3}\)?[ -]?\d{3}[ -]?\d{4}\b"), "<phone>"),
]

# ---- identity --------------------------------------------------------------
def entity_id(entity_type: str, key: str) -> str:
    """Stable identity: hash of type + canonical key. Same entity across days."""
    k = f"{entity_type.strip().lower()}:{key.strip().lower()}"
    return hashlib.sha256(k.encode()).hexdigest()[:16]


def scrub(text: str) -> str:
    for pat, repl in SCRUB_PATTERNS:
        text = pat.sub(repl, text)
    return text


# ---- entity DAG ------------------------------------------------------------
class EntityDAG:
    """A DAG of observed attributes + relations for one entity."""

    def __init__(self, entity_id: str, max_nodes: int = 64):
        self.entity_id = entity_id
        self.max_nodes = max_nodes
        self.nodes: Dict[str, Dict[str, Any]] = {}   # node_id -> {label, value, ts, utility, history}
        self.archived: Dict[str, Dict[str, Any]] = {}  # archived (never deleted)
        self.edges: List[Tuple[str, str, str]] = []  # (parent, child, relation)

    def observe(self, facts: Dict[str, Any],
                relations: Optional[List[Tuple[str, str, str]]] = None,
                ts: Optional[float] = None) -> Dict[str, int]:
        """Merge an observation into the DAG. Returns {added, updated, evicted}."""
        ts = ts or time.time()
        added = 0
        updated = 0
        for key, value in facts.items():
            node_id = key
            if node_id in self.nodes:
                n = self.nodes[node_id]
                if n["value"] != value:
                    n.setdefault("history", []).insert(0, (n["value"], n["ts"]))
                    n["history"] = n["history"][:3]
                n["value"] = value
                n["ts"] = ts
                n["utility"] = n.get("utility", 0.0) + 1.0
                updated += 1
            else:
                self.nodes[node_id] = {"label": key, "value": value, "ts": ts,
                                       "utility": 1.0, "history": []}
                added += 1
        for parent, child, rel in (relations or []):
            if parent in self.nodes and child in self.nodes:
                self.edges.append((parent, child, rel))
        evicted = self.prune()
        return {"added": added, "updated": updated, "evicted": evicted}

    def _util(self, node_id: str) -> Tuple[float, float]:
        n = self.nodes[node_id]
        conn = sum(1 for p, c, _ in self.edges if p == node_id or c == node_id)
        # lower = prune first: low observation count + low connectivity, then oldest
        return (n["utility"] + conn, n["ts"])

    def prune(self) -> int:
        """Evict lowest-utility nodes until at max_nodes. Returns count evicted."""
        if len(self.nodes) <= self.max_nodes:
            return 0
        order = sorted(self.nodes, key=self._util)
        excess = len(self.nodes) - self.max_nodes
        for node_id in order[:excess]:
            del self.nodes[node_id]
        self.edges = [(p, c, r) for p, c, r in self.edges
                      if p in self.nodes and c in self.nodes]
        return excess

    def prune_to_optimum(self, dry_run: bool = False,
                         min_gain: float = 0.05) -> Dict[str, Any]:
        """Asymptotic dream-prune: archive nodes past the effectiveness knee.

        Ranks live nodes by utility, finds the knee of the cumulative
        effectiveness curve, and ARCHIVES (never deletes) the tail. This is
        Chris's "prune to the optimal size" — cut where effectiveness stops
        paying off, lose nothing good."""
        from .asymptotic import find_knee, effectiveness_curve
        if not self.nodes:
            return {"reason": "empty", "kept": 0, "archived": 0}
        ids = sorted(self.nodes, key=lambda nid: self._util(nid), reverse=True)
        utils = [self._util(nid)[0] for nid in ids]
        k = find_knee(utils, min_gain)
        curve = effectiveness_curve(utils)
        archive_ids = ids[k:]
        if not dry_run:
            for nid in archive_ids:
                self.archived[nid] = self.nodes.pop(nid)
            self.edges = [(p, c, r) for p, c, r in self.edges
                          if p in self.nodes and c in self.nodes]
        return {"entity": self.entity_id, "count": len(ids), "kept": k,
                "archived": len(archive_ids),
                "retained_value": curve["retained_value"]}

    def changed_since(self, since_ts: float) -> Dict[str, Any]:
        """Attributes that changed after since_ts (the 'different days' answer)."""
        out = {}
        for nid, n in self.nodes.items():
            if n["ts"] >= since_ts:
                out[nid] = {"value": n["value"], "history": n.get("history", [])}
        return out

    def render(self, scrub_pii: bool = True) -> Dict[str, Any]:
        nodes = {}
        for nid, n in sorted(self.nodes.items()):
            v = n["value"]
            if scrub_pii and isinstance(v, str):
                v = scrub(v)
            hist = n.get("history", [])
            if scrub_pii:
                hist = [(scrub(hv) if isinstance(hv, str) else hv, hts)
                        for hv, hts in hist]
            nodes[nid] = {"value": v, "ts": round(n["ts"], 2),
                          "utility": round(n["utility"], 2),
                          "history": hist}
        return {"entity_id": self.entity_id, "nodes": nodes, "edges": self.edges}


# ---- world model -----------------------------------------------------------
class WorldModel:
    """A collection of entity DAGs, JSON-file-backed (stdlib)."""

    def __init__(self, state_path: Optional[str] = None, max_nodes: int = 64):
        self.state_path = state_path
        self.max_nodes = max_nodes
        self.entities: Dict[str, EntityDAG] = {}
        if state_path and os.path.exists(state_path):
            self.load()

    def observe(self, entity_type: str, key: str, facts: Dict[str, Any],
                relations: Optional[List[Tuple[str, str, str]]] = None,
                ts: Optional[float] = None) -> Dict[str, Any]:
        """Observe an entity (create its DAG on first sight) and merge facts."""
        eid = entity_id(entity_type, key)
        if eid not in self.entities:
            self.entities[eid] = EntityDAG(eid, max_nodes=self.max_nodes)
        r = self.entities[eid].observe(facts, relations, ts)
        return {"entity_id": eid, "entity_type": entity_type, "key": key,
                "nodes": len(self.entities[eid].nodes), **r}

    def entity(self, entity_type: str, key: str) -> Optional[EntityDAG]:
        return self.entities.get(entity_id(entity_type, key))

    def prune_all(self) -> int:
        return sum(dag.prune() for dag in self.entities.values())

    def prune_to_optimum(self, dry_run: bool = False,
                         min_gain: float = 0.05) -> Dict[str, Any]:
        """Asymptotic dream-prune across every entity DAG."""
        reports = {eid: dag.prune_to_optimum(dry_run=dry_run, min_gain=min_gain)
                   for eid, dag in self.entities.items()}
        return {"entities": len(self.entities),
                "archived": sum(r.get("archived", 0) for r in reports.values()),
                "reports": reports}

    def render(self, entity_type: str, key: str,
               scrub_pii: bool = True) -> Optional[Dict[str, Any]]:
        dag = self.entity(entity_type, key)
        return dag.render(scrub_pii=scrub_pii) if dag else None

    def render_all(self, scrub_pii: bool = True) -> Dict[str, Dict[str, Any]]:
        return {eid: dag.render(scrub_pii=scrub_pii)
                for eid, dag in sorted(self.entities.items())}

    def save(self) -> Optional[str]:
        if not self.state_path:
            return None
        os.makedirs(os.path.dirname(self.state_path) or ".", exist_ok=True)
        payload = {"max_nodes": self.max_nodes,
                   "entities": {eid: {"nodes": dag.nodes, "edges": dag.edges,
                                      "archived": dag.archived}
                                for eid, dag in self.entities.items()}}
        tmp = self.state_path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(payload, f, indent=2)
        os.replace(tmp, self.state_path)
        return self.state_path

    def load(self) -> None:
        try:
            payload = json.load(open(self.state_path))
        except Exception:
            return
        self.max_nodes = payload.get("max_nodes", self.max_nodes)
        for eid, data in payload.get("entities", {}).items():
            dag = EntityDAG(eid, max_nodes=self.max_nodes)
            dag.nodes = data.get("nodes", {})
            dag.edges = [tuple(e) for e in data.get("edges", [])]
            dag.archived = data.get("archived", {})
            self.entities[eid] = dag

    def stats(self) -> Dict[str, Any]:
        return {"entities": len(self.entities),
                "total_nodes": sum(len(d.nodes) for d in self.entities.values()),
                "total_edges": sum(len(d.edges) for d in self.entities.values())}

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
