"""WRAPPED TOC-TOK TOWER — hex-anchored Tree of Knowledge.

Every project / phase / task / knowledge node carries a hex coordinate
plus a parent path. The agent navigates by TREE path AND by SPACE (FOW):
  - tree <path>      : walk the tree
  - at <hex>         : nodes at hex + 1-hop neighbours
  - search <term>    : keyword lookup
  - add <path> <hex> : register a node
  - path <name>      : resolve node -> its full path + hex

Deterministic, pure stdlib, file-backed (survives restarts).
Negative hexes supported via explicit --hex or auto-protected positional.
"""

import json
import os
from typing import Any, Dict, List, Optional, Tuple


def axial_neighbors(q: int, r: int) -> List[Tuple[int, int]]:
    dirs = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)]
    return [(q + dq, r + dr) for dq, dr in dirs]


class TocTokTower:
    def __init__(self, path: str):
        self.store_path = path
        os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(path) else None
        if not os.path.exists(path):
            self._write({"nodes": [], "meta": {"version": 1}})

    def _read(self) -> Dict[str, Any]:
        return json.load(open(self.store_path, encoding="utf-8"))

    def _write(self, data: Dict[str, Any]) -> None:
        tmp = self.store_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, self.store_path)

    # ---- add ---------------------------------------------------------
    def add(self, name: str, hex_q: int, hex_r: int, kind: str = "node",
            parent: Optional[str] = None, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        data = self._read()
        node = {
            "name": name, "hex": [hex_q, hex_r], "kind": kind,
            "parent": parent, "meta": meta or {},
        }
        data["nodes"].append(node)
        self._write(data)
        return node

    # ---- tree ----------------------------------------------------------
    def tree(self, root: Optional[str] = None) -> List[Dict[str, Any]]:
        nodes = self._read()["nodes"]
        if root is None:
            return nodes
        return [n for n in nodes if (n.get("parent") or "").startswith(root)]

    def children_of(self, parent: str) -> List[Dict[str, Any]]:
        return [n for n in self._read()["nodes"] if n.get("parent") == parent]

    # ---- space -----------------------------------------------------------
    def at(self, q: int, r: int, hop: int = 1) -> List[Dict[str, Any]]:
        nodes = self._read()["nodes"]
        if hop <= 0:
            return [n for n in nodes if n["hex"] == [q, r]]
        visible = set()
        frontier = [(q, r)]
        for _ in range(hop):
            nxt = []
            for hq, hr in frontier:
                visible.add((hq, hr))
                for nq, nr in axial_neighbors(hq, hr):
                    visible.add((nq, nr))
            frontier = [(nq, nr) for hq, hr in frontier for nq, nr in axial_neighbors(hq, hr)]
        return [n for n in nodes if tuple(n["hex"]) in visible]

    # ---- search ------------------------------------------------------------
    def search(self, term: str) -> List[Dict[str, Any]]:
        term_l = term.lower()
        out = []
        for n in self._read()["nodes"]:
            hay = json.dumps(n).lower()
            if term_l in hay:
                out.append(n)
        return out

    # ---- path ---------------------------------------------------------------
    def resolve_path(self, name: str) -> Optional[Dict[str, Any]]:
        nodes = self._read()["nodes"]
        node = next((n for n in nodes if n["name"] == name), None)
        if node is None:
            return None
        chain = [node["name"]]
        parent = node.get("parent")
        while parent:
            pnode = next((n for n in nodes if n["name"] == parent), None)
            if pnode is None:
                break
            chain.append(pnode["name"])
            parent = pnode.get("parent")
        return {"node": node, "path": list(reversed(chain))}

    def count(self) -> int:
        return len(self._read()["nodes"])
