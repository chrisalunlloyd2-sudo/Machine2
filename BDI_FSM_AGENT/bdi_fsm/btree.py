"""BEHAVIOR TREE — real executable actions, pullable by performative.

90s hybrid: behavior trees (Champandard) + the KQML performative layer.
Each Action node carries REAL platform code (Termux bash / PowerShell),
a performative tag, verb flags, and a never_try_twice linkage so the same
failed command is never attempted blind twice.

    "please save this code in repo x file a line 22"  (achieve)
        -> pull_by_performative("achieve", platform)
        -> filter by verb flags (save)
        -> nmtd.check()  (skip known_fail)
        -> execute real termux/powershell command
        -> nmtd.record(outcome)
        -> "It is done: ..."

Pure stdlib. No cloud, no LLM. Runs anywhere Python runs.
"""

import hashlib
import json
import os
import re
import subprocess
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

# node statuses
SUCCESS = "SUCCESS"
FAILURE = "FAILURE"
RUNNING = "RUNNING"


class BTNode:
    """Base behavior-tree node."""
    def tick(self, ctx: Dict[str, Any]) -> str:
        raise NotImplementedError


class Selector(BTNode):
    """OR gate — try children in order, first SUCCESS wins."""
    def __init__(self, children: List[BTNode]):
        self.children = children
    def tick(self, ctx):
        for c in self.children:
            if c.tick(ctx) == SUCCESS:
                return SUCCESS
        return FAILURE


class Sequence(BTNode):
    """AND gate — all children must succeed in order."""
    def __init__(self, children: List[BTNode]):
        self.children = children
    def tick(self, ctx):
        for c in self.children:
            if c.tick(ctx) != SUCCESS:
                return FAILURE
        return SUCCESS


class Condition(BTNode):
    """Gate — evaluate a predicate; no side effects."""
    def __init__(self, name: str, fn: Callable[[Dict], bool]):
        self.name = name
        self.fn = fn
    def tick(self, ctx):
        return SUCCESS if self.fn(ctx) else FAILURE


class Action(BTNode):
    """Leaf — executes REAL platform code with NMTD protection.

    platforms: {"termux": "...", "powershell": "..."} command templates.
    {repo} {file} {code} {msg} {tests} {url} are format placeholders
    filled from ctx by .format(**ctx).
    """

    def __init__(self, name: str, performatives: List[str], verbs: List[str],
                 platforms: Dict[str, str], check_cmd: Optional[str] = None,
                 timeout: int = 30, nmtd: Optional[Any] = None,
                 platform: str = "termux"):
        self.name = name
        self.performatives = performatives
        self.verbs = verbs
        self.platforms = platforms
        self.check_cmd = check_cmd
        self.timeout = timeout
        self.nmtd = nmtd            # injected never_try_twice checker
        self.platform = platform    # active platform: termux|powershell
        self.last_result: Dict[str, Any] = {}

    # ---- NMTD fingerprint: the same command+repo is never retried blind ----
    def fingerprint(self, ctx: Dict[str, Any]) -> str:
        cmd = self.render(ctx)
        repo = str(ctx.get("repo", ""))
        return hashlib.sha256(f"{self.name}|{repo}|{cmd}".encode()).hexdigest()[:12]

    def render(self, ctx: Dict[str, Any]) -> str:
        tpl = self.platforms.get(self.platform, "")
        return tpl.format(**ctx)

    def pre_check(self, ctx: Dict[str, Any]) -> Optional[str]:
        """Return block reason if NMTD says known_fail, else None."""
        if self.nmtd is None:
            return None
        fp = self.fingerprint(ctx)
        verdict = self.nmtd.check(fp) if hasattr(self.nmtd, "check") else None
        if verdict and verdict.get("outcome") == "fail" and verdict.get("fail_count", 0) >= 2:
            return f"never-try-twice: {fp} already failed {verdict['fail_count']}x"
        return None

    # ---- run each template in the shell it was WRITTEN for ----------------
    def _spawn(self, cmd: str, timeout: int):
        """Execute `cmd` under the interpreter its platform names.

        THE POWERSHELL TEMPLATES WERE BEING FED TO CMD.EXE.
        Chris 2026-09-03: "doesnt that mean btree is run through cmd when it
        SHOULD be run through powershell?" -- yes, exactly that.

        This was subprocess.run(cmd, shell=True), and on Windows shell=True is
        cmd.exe. The powershell templates separate their steps with `;`, which
        cmd.exe does not treat as a separator, so

            cd C:/Viper/scripts; git status --short; git log --oneline -3

        handed `cd` the whole line as one path. Measured 2026-09-03: exit 1,
        "The system cannot find the path specified." Since ok is
        `returncode == 0`, EVERY multi-step powershell action reported failure
        while being perfectly correct PowerShell. git_status and run_tests both
        sat red for that reason, and the BTree's red X on the wall was this.

        encoding="utf-8" is not decoration. subprocess.run(text=True) with no
        encoding decodes as cp1252 on this box -- already in the never_twice
        ledger -- so any command emitting a box-drawing character or an accent
        raised UnicodeDecodeError and read as a failed action.

        -NonInteractive so a prompt can never hang a cell instead of failing it.
        """
        if self.platform == "powershell":
            return subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=timeout)
        # termux / posix: the template is written for sh, so sh is correct.
        return subprocess.run(cmd, shell=True, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout)

    def tick(self, ctx: Dict[str, Any]) -> str:
        block = self.pre_check(ctx)
        if block:
            self.last_result = {"ok": False, "blocked": block, "action": self.name}
            return FAILURE
        cmd = self.render(ctx)
        try:
            r = self._spawn(cmd, self.timeout)
            ok = r.returncode == 0
        except subprocess.TimeoutExpired:
            ok, r = False, type("R", (), {"stdout": "", "stderr": f"timeout {self.timeout}s"})()
        # optional post-verify
        verified = None
        if ok and self.check_cmd:
            try:
                # Same shell as the action itself. A check written in PowerShell
                # and run by cmd.exe would fail every verification and turn a
                # working action into a reported fault -- which is the fault
                # this whole method just stopped doing.
                v = self._spawn(self.check_cmd.format(**ctx), 15)
                verified = v.returncode == 0
                ok = ok and verified
            except Exception:
                verified = False
                ok = False
        self.last_result = {
            "ok": ok, "action": self.name, "cmd": cmd[:200],
            "exit": getattr(r, "returncode", None),
            "stdout": (r.stdout or "")[-1500:], "stderr": (r.stderr or "")[-800:],
            "verified": verified, "ts": time.time(),
        }
        if self.nmtd is not None and hasattr(self.nmtd, "record"):
            self.nmtd.record(self.fingerprint(ctx),
                             {"cmd": cmd[:300], "outcome": "ok" if ok else "fail",
                              "repo": ctx.get("repo", ""), "action": self.name,
                              "ts": time.time()})
        return SUCCESS if ok else FAILURE

    def matches(self, performative: str, verbs: List[str]) -> bool:
        return performative in self.performatives and bool(set(verbs) & set(self.verbs))


class BehaviorTree:
    """Registry of Action nodes, pullable by performative + verb flags."""

    def __init__(self, actions: Optional[List[Action]] = None,
                 nmtd: Optional[Any] = None, platform: str = "termux"):
        self.actions = actions or []
        self.nmtd = nmtd
        self.platform = platform
        for a in self.actions:
            a.nmtd = nmtd
            a.platform = platform

    def add(self, action: Action) -> None:
        action.nmtd = self.nmtd
        action.platform = self.platform
        self.actions.append(action)

    def pull(self, performative: str, verbs: List[str],
             ctx: Optional[Dict] = None) -> List[Action]:
        """Pull action candidates by performative, verb flags, NMTD-safe."""
        ctx = ctx or {}
        cands = [a for a in self.actions if a.matches(performative, verbs)]
        # rank: more verb hits first, then stable order
        cands.sort(key=lambda a: -len(set(verbs) & set(a.verbs)))
        out = []
        for a in cands:
            block = a.pre_check(ctx)
            if block is None:
                out.append(a)
        return out

    def run(self, performative: str, verbs: List[str], ctx: Dict) -> Dict:
        cands = self.pull(performative, verbs, ctx)
        if not cands:
            return {"ok": False, "error": "no_action",
                    "performative": performative, "verbs": verbs}
        last = {}
        for a in cands:
            st = a.tick(ctx)
            last = a.last_result
            if st == SUCCESS:
                return {"ok": True, "action": a.name, "result": last,
                        "candidates": [x.name for x in cands]}
        return {"ok": False, "action": cands[0].name, "result": last,
                "candidates": [x.name for x in cands],
                "error": "all_candidates_failed"}

    def to_dict(self) -> Dict:
        return {"actions": [{"name": a.name, "performatives": a.performatives,
                             "verbs": a.verbs, "platforms": list(a.platforms)}
                            for a in self.actions]}

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
