"""DOMAIN NODE — environment boundary + Bayesian intersection synthesis.

Chris directive 2026-08-12: "env is important too." A self-training agent must
be BOUNDED by where it actually lives. On Android/Termux it may only touch
Android Framework APIs, ADB, and Gradle; on a Linux box it may only touch the
shell, git, python. The domain node is that hard boundary.

The pipeline (same BDI + Logic DAG + BanLedger loop, applied to code):

  1. DOMAIN GATE (Logic DAG) — prune every import/command/tool outside the
     environment. Zero compute: a prefix check rejects the whole namespace.
  2. SYMBOL MAPPER — align variables between two reference projects by type
     + lifecycle scope (deterministic similarity, not invented names).
  3. INTERSECTION SYNTHESIS (BanLedger) — every candidate code construct
     (onCreate, Context, a given API) accumulates log-evidence from BOTH
     reference projects. A construct present in both gains dBan; present in
     one loses dBan. The constructs that clear the threshold are the
     structural intersection — the only code that is synthesized.

This fixes three bugs in the original prototype:
  (a) the BanLedger was declared but never USED (synthesis was a hardcoded
      template) — now the intersection is genuinely evidence-driven.
  (b) validate_command() checked a hardcoded literal, not the real input —
      now the gate validates the actual import/command lists.
  (c) startswith(pkg) accepted "android.contentEvil" — now matches pkg or
      pkg + "." only.

Pure stdlib. Deterministic. Zero LLM.
"""
import math
from typing import Dict, List, Optional, Set, Tuple

from .bayes_engine import BanLedger


# --- 1. Environment boundary -------------------------------------------------
class DomainSpec:
    """The allowed vocabulary of one environment (packages, commands, tools)."""

    def __init__(self, name: str, allowed_packages: Set[str],
                 allowed_commands: Set[str], allowed_tools: Set[str] = ()):
        self.name = name
        self.allowed_packages = set(allowed_packages)
        self.allowed_commands = set(allowed_commands)
        self.allowed_tools = set(allowed_tools)

    def allows_import(self, import_stmt: str) -> bool:
        """True iff import_stmt is a package or a subpackage of an allowed
        namespace. Bounds at the '.' so 'android.contentEvil' is rejected."""
        s = import_stmt.strip()
        for pkg in self.allowed_packages:
            if s == pkg or s.startswith(pkg + "."):
                return True
        return False

    def allows_command(self, cmd: str) -> bool:
        return cmd.strip() in self.allowed_commands


class DomainGate:
    """Hard boundary — reports every violation, never silently permits."""

    def __init__(self, spec: DomainSpec):
        self.spec = spec

    def violations(self, imports: List[str], commands: List[str]) -> Tuple[List[str], List[str]]:
        bad_imports = [i for i in imports if not self.spec.allows_import(i)]
        bad_cmds = [c for c in commands if not self.spec.allows_command(c)]
        return bad_imports, bad_cmds

    def permits(self, imports: List[str], commands: List[str]) -> bool:
        b_i, b_c = self.violations(imports, commands)
        return not b_i and not b_c


# --- 2. Symbol / variable mapping -------------------------------------------
class SymbolNode:
    __slots__ = ("name", "type_hint", "scope", "project")
    def __init__(self, name: str, type_hint: str, scope: str, project: str):
        self.name = name
        self.type_hint = type_hint
        self.scope = scope
        self.project = project


class SymbolMapper:
    """Maps symbols across two reference projects by type + scope alignment."""

    TYPE_MATCH_DBAN = 15.0
    SCOPE_MATCH_DBAN = 10.0
    MAP_THRESHOLD = 20.0

    def __init__(self):
        self.project_a: Dict[str, SymbolNode] = {}
        self.project_b: Dict[str, SymbolNode] = {}

    def register(self, project: str, name: str, type_hint: str, scope: str = "Activity"):
        node = SymbolNode(name, type_hint, scope, project)
        (self.project_a if project == "A" else self.project_b)[name] = node

    def find_intersections(self) -> List[Tuple[SymbolNode, SymbolNode, float]]:
        """Symbol pairs whose type+scope similarity clears the mapping threshold."""
        out = []
        for a in self.project_a.values():
            for b in self.project_b.values():
                score = 0.0
                if a.type_hint == b.type_hint:
                    score += self.TYPE_MATCH_DBAN
                if a.scope == b.scope:
                    score += self.SCOPE_MATCH_DBAN
                if score >= self.MAP_THRESHOLD:
                    out.append((a, b, score))
        return out


# --- 3. BanLedger intersection synthesis ------------------------------------
class IntersectionSynthesizer:
    """Extract the structural intersection of N projects by Bayesian evidence.

    Each candidate construct is a hypothesis "is this shared across the
    projects?". Every project votes: present => +dBan, absent => -dBan.
    Constructs present in ALL projects accumulate past the threshold; the rest
    are eliminated. This is the Banburismus reduction, applied to code.
    """

    PRESENT = (0.80, 0.30)   # P(present|shared), P(present|not-shared)  -> +4.26 dBan
    ABSENT = (0.20, 0.70)    # P(absent|shared),  P(absent|not-shared)   -> -5.44 dBan

    def __init__(self, threshold_dban: float = 5.0):
        self.threshold_dban = threshold_dban
        self.ledger = BanLedger(threshold_dban=threshold_dban)
        self.constructs: List[str] = []

    def register_constructs(self, constructs: List[str]):
        self.constructs = list(constructs)
        for c in self.constructs:
            self.ledger.register(c, prior_prob=0.5)

    def observe_project(self, project_features: Set[str]):
        for c in self.constructs:
            p_h, p_nh = self.PRESENT if c in project_features else self.ABSENT
            self.ledger.observe(c, p_h, p_nh)

    def extract(self) -> List[str]:
        """Constructs that cleared the threshold (the intersection)."""
        return [c for c in self.constructs
                if self.ledger.scores.get(c, float("-inf")) >= self.threshold_dban]

    def scores(self) -> Dict[str, float]:
        return {c: round(self.ledger.scores.get(c, float("-inf")), 2)
                for c in self.constructs}


if __name__ == "__main__":
    # worked example: Bluetooth app vs Network app
    synth = IntersectionSynthesizer(threshold_dban=5.0)
    synth.register_constructs(["Context", "onCreate", "onResume", "onDestroy",
                               "BluetoothAdapter", "ConnectivityManager"])
    project_a = {"Context", "onCreate", "onResume", "BluetoothAdapter"}
    project_b = {"Context", "onCreate", "onDestroy", "ConnectivityManager"}
    synth.observe_project(project_a)
    synth.observe_project(project_b)
    print("scores:", synth.scores())
    print("intersection (in BOTH):", synth.extract())

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
