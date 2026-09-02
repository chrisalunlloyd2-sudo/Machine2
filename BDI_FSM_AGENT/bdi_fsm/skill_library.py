"""SKILL LIBRARY — verified code wins cached with NMCT-style seals.

When the brute foundry (or any verified source) produces a winner, the
agent stores it here keyed by name AND by parameter signature. Future
identical stubs are served from the library instead of re-mining —
compounding determinism (roadmap Phase 9: recipe/vault hit rate -> 100%).

Exports to the ToK Recipe Book so the memory harness can retrieve
canonical implementations. Pure stdlib, no cloud, no LLM.
"""

import hashlib
import json
import os
import re
import time
from typing import Any, Dict, List, Optional


class SkillLibrary:
    def __init__(self, state_dir: str):
        self.skills_dir = os.path.join(state_dir, "skills")
        self.index_path = os.path.join(state_dir, "skills_index.json")
        os.makedirs(self.skills_dir, exist_ok=True)
        self._index: Dict[str, Dict[str, Any]] = {}
        if os.path.exists(self.index_path):
            try:
                self._index = json.load(open(self.index_path, encoding="utf-8"))
            except Exception:
                self._index = {}
        self._hits = 0
        self._misses = 0
        self._hit_log = os.path.join(state_dir, "skills_hits.jsonl")

    # ---- persistence --------------------------------------------------
    def save_index(self) -> None:
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(self._index, f, indent=2, sort_keys=True)

    @staticmethod
    def _sha256(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:12]

    # ---- add ----------------------------------------------------------
    def add(self, name: str, code: str, source: str = "brute-foundry",
            params: Optional[List[str]] = None, examples: Optional[List[str]] = None,
            health: Optional[float] = None, doc: str = "") -> Dict[str, Any]:
        """Store a verified winner. Overwrites same-name entry (ADD/update only)."""
        safe = re.sub(r"[^A-Za-z0-9_]", "_", name)
        entry = {
            "name": name,
            "safe": safe,
            "source": source,
            "params": params or [],
            "examples": examples or [],
            "health": health,
            "doc": doc[:500],
            "sha256": self._sha256(code),
            "ts": time.time(),
        }
        self._index[safe] = entry
        with open(os.path.join(self.skills_dir, f"{safe}.py"), "w", encoding="utf-8") as f:
            f.write(code if code.endswith("\n") else code + "\n")
        self.save_index()
        return entry

    # ---- retrieval ----------------------------------------------------
    def get(self, name: str) -> Optional[Dict[str, Any]]:
        safe = re.sub(r"[^A-Za-z0-9_]", "_", name)
        entry = self._index.get(safe)
        if not entry:
            self._miss(entry)
            return None
        code_path = os.path.join(self.skills_dir, f"{safe}.py")
        if not os.path.exists(code_path):
            self._miss(entry)
            return None
        # seal check — never serve tampered code
        code = open(code_path, encoding="utf-8").read()
        if self._sha256(code) != entry.get("sha256"):
            return {"error": "TAMPERED", "name": name}
        entry = dict(entry)
        entry["code"] = code
        self._hit(entry)
        return entry

    def lookup_by_params(self, params: List[str]) -> Optional[Dict[str, Any]]:
        """Exact parameter-signature match — the compounding-determinism path."""
        sig = tuple(sorted(p.strip() for p in params if p.strip()))
        for e in self._index.values():
            if tuple(sorted(e.get("params", []))) == sig:
                return self.get(e["safe"])
        return None

    def search(self, desc: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Token-overlap scoring over name/doc/params. Deterministic."""
        toks = set(re.findall(r"[a-z0-9_]{2,}", desc.lower()))
        scored = []
        for e in self._index.values():
            hay = " ".join([e["name"].lower()] + e.get("params", []) + [e.get("doc", "").lower()])
            hay_toks = set(re.findall(r"[a-z0-9_]{2,}", hay))
            overlap = len(toks & hay_toks) / max(1, len(toks))
            scored.append((overlap, e["name"]))
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [{"name": n, "score": s} for s, n in scored[:top_k] if s > 0]

    # ---- hit tracking -------------------------------------------------
    def _hit(self, entry: Dict[str, Any]) -> None:
        self._hits += 1
        with open(self._hit_log, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.time(), "hit": entry.get("name")}) + "\n")

    def _miss(self, entry: Optional[Dict[str, Any]]) -> None:
        self._misses += 1
        with open(self._hit_log, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.time(), "miss": (entry or {}).get("name")}) + "\n")

    def stats(self) -> Dict[str, Any]:
        total = self._hits + self._misses
        return {
            "size": len(self._index),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / total, 4) if total else 0.0,
            "skills": sorted(self._index.keys()),
        }

    # ---- recipe book export --------------------------------------------
    def export_recipe_book(self, recipe_dir: str) -> int:
        """Write one recipe .md per skill for the ToK memory harness."""
        os.makedirs(recipe_dir, exist_ok=True)
        written = 0
        for e in self._index.values():
            code_path = os.path.join(self.skills_dir, f"{e['safe']}.py")
            if not os.path.exists(code_path):
                continue
            code = open(code_path, encoding="utf-8").read()
            md = (f"# Recipe: {e['name']}\n\n"
                  f"- **Source:** {e.get('source')}\n"
                  f"- **Params:** {', '.join(e.get('params', []))}\n"
                  f"- **Health:** {e.get('health')}\n"
                  f"- **Seal:** {e.get('sha256')}\n\n"
                  f"```python\n{code}\n```\n")
            with open(os.path.join(recipe_dir, f"{e['safe']}.md"), "w", encoding="utf-8") as f:
                f.write(md)
            written += 1
        return written

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
