"""BRUTE FOUNDRY ADAPTER — merge with the local brute-foundry repo.

brute-foundry is a deterministic, no-LLM code generator (mine/harden/
render/gate). This adapter shells out to it, feeds its mined winner
through the hardened sandbox + NMCT vault, and exposes it as a
candidate source for the genetic foundry.

Pure subprocess + file IO. No cloud, no model.
"""

import json
import os
import sys
import subprocess
import tempfile
from typing import Any, Dict, List, Optional

# Candidate locations for brute-foundry, in preference order. The hardcoded default was
# /root/scan_tmp/brute-foundry -- the phone's path. On the Viper host that directory does not
# exist, so available() was always False and EVERY pool cycle returned
# "brute-foundry not found" while reporting ok:false rather than crashing. Silent and total: the
# agent's only real candidate source was never once reachable.
FOUNDRY_CANDIDATES = [
    os.environ.get("VIPER_FOUNDRY_DIR", ""),
    r"C:\Viper\projects\brute-foundry",
    "/root/scan_tmp/brute-foundry",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "..", "brute-foundry"),
]


def find_foundry() -> str:
    """First candidate that actually contains foundry.py; else the first non-empty candidate.

    Returning a real path when one exists (rather than a fixed default) is what makes this
    portable between the phone and the Xeon without a config edit.
    """
    for c in FOUNDRY_CANDIDATES:
        if c and os.path.exists(os.path.join(c, "foundry.py")):
            return os.path.abspath(c)
    return next((c for c in FOUNDRY_CANDIDATES if c), "")


DEFAULT_FOUNDRY_DIR = find_foundry()


class BruteFoundryAdapter:
    def __init__(self, foundry_dir: Optional[str] = None,
                 timeout: int = 30):
        self.foundry_dir = foundry_dir or find_foundry()
        self.timeout = timeout

    def available(self) -> bool:
        return os.path.exists(os.path.join(self.foundry_dir, "foundry.py"))

    def mine(self, name: str, params: List[str],
             examples: List[str], doc: str = "") -> Dict[str, Any]:
        """Run: python foundry.py mine <name> "<p1,p2>" "<ex1;ex2;...>"
        Returns parsed winner or error."""
        if not self.available():
            return {"ok": False, "error": "brute-foundry not found",
                    "foundry_dir": self.foundry_dir}
        cmd = [sys.executable, os.path.join(self.foundry_dir, "foundry.py"),
               "mine", name, ",".join(params), ";".join(examples), doc]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True,
                               timeout=self.timeout, cwd=self.foundry_dir)
            out = r.stdout
            return {"ok": r.returncode == 0, "exit": r.returncode,
                    "stdout": out[-4000:], "stderr": r.stderr[-1000:],
                    "foundry_dir": self.foundry_dir}
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": f"timeout after {self.timeout}s"}

    def extract_winner(self, result: Dict[str, Any]) -> Optional[str]:
        """Pull the mined code block (before the # health= comment)."""
        if not result.get("ok"):
            return None
        out = result.get("stdout", "")
        marker = "# health="
        if marker in out:
            return out.split(marker)[0].rstrip()
        return out.strip() or None

    def mine_to_file(self, name: str, params: List[str], examples: List[str],
                     target_path: str) -> Dict[str, Any]:
        """Mine a candidate and write the winner to target_path (for the
        hardened sandbox to verify)."""
        res = self.mine(name, params, examples)
        winner = self.extract_winner(res)
        if winner:
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(winner)
            res["winner_len"] = len(winner)
            res["target"] = target_path
        return res

    # ---- more brute foundry: harden / render / gate --------------------
    def run_sub(self, subcommand: str, args: List[str]) -> Dict[str, Any]:
        """Generic passthrough: python foundry.py <sub> <args...>."""
        if not self.available():
            return {"ok": False, "error": "brute-foundry not found"}
        cmd = [sys.executable, os.path.join(self.foundry_dir, "foundry.py"),
               subcommand] + args
        try:
            r = subprocess.run(cmd, capture_output=True, text=True,
                               timeout=self.timeout, cwd=self.foundry_dir)
            return {"ok": r.returncode == 0, "exit": r.returncode,
                    "stdout": r.stdout[-4000:], "stderr": r.stderr[-1000:]}
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": f"timeout after {self.timeout}s"}

    def harden(self, name: str, code: str) -> Dict[str, Any]:
        return self.run_sub("harden", [name, code])

    def render(self, name: str) -> Dict[str, Any]:
        return self.run_sub("render", [name])

    def gate(self) -> Dict[str, Any]:
        return self.run_sub("gate", [])

    # ---- batch mining + skill library -----------------------------------
    def batch_mine(self, stubs: List[Dict[str, Any]],
                   skill_lib=None) -> List[Dict[str, Any]]:
        """Mine several stubs sequentially. Each: {name, params, examples,
        doc}. Winners optionally cached in a SkillLibrary (compounding
        determinism). Returns one result dict per stub."""
        results = []
        for s in stubs:
            name = s["name"]
            r = self.mine(name, s.get("params", []), s.get("examples", []),
                          s.get("doc", ""))
            winner = self.extract_winner(r) if r.get("ok") else None
            entry = None
            if winner and skill_lib is not None:
                entry = skill_lib.add(name, winner, source="brute-foundry",
                                      params=s.get("params", []),
                                      examples=s.get("examples", []),
                                      doc=s.get("doc", ""))
            results.append({
                "name": name, "ok": r.get("ok"), "exit": r.get("exit"),
                "winner": winner, "skill_entry": entry,
                "error": r.get("error"),
            })
        return results

    def mine_to_skill(self, name: str, params: List[str], examples: List[str],
                      doc: str, skill_lib) -> Dict[str, Any]:
        """Mine one stub, store the verified winner in the SkillLibrary,
        and return the skill entry (or error)."""
        r = self.mine(name, params, examples, doc)
        if not r.get("ok"):
            return {"ok": False, "error": r.get("error", "mine failed")}
        winner = self.extract_winner(r)
        if not winner:
            return {"ok": False, "error": "no winner extracted"}
        entry = skill_lib.add(name, winner, source="brute-foundry",
                              params=params, examples=examples, doc=doc)
        return {"ok": True, "skill": entry, "code": winner}

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
