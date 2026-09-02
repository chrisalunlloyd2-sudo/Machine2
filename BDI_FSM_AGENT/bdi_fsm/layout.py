"""layout.py — layout-strategy meta-state + rule bank + trace training.

Chris 2026-08-15: "Introduce meta-states for layout strategy ... chooselayoutstrategy:
strategy = 'table' | 'list' | 'cards'. That state is where training rules apply.
Once chosen, the lower-level FSM just enforces structural correctness. Keep a
rule bank keyed by outcome features. Training = editing this bank from traces."

Rules are deterministic objects — no probabilities, just more precise symbolic
conditions. A correction (e.g. user switched ul->table) becomes a guard rule
("IF columns >= 2 THEN avoid ul"). Deterministic, zero-LLM.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

# words that signal a comparison intent (-> prefer table)
_COMPARISON_WORDS = {"compare", "comparison", "comparing", "versus", "vs",
                     "difference", "differences", "diff", "between"}

DEFAULT_RULE_BANK: List[Dict[str, Any]] = [
    {"name": "prefer_table_for_comparison",
     "if": {"intent": "comparison", "columns_min": 2},
     "then": {"layout": "table"}},
]


def features_from(question: str, intents: List[str],
                  content: List[str]) -> Dict[str, Any]:
    """Derive outcome features: intent, item count, column count."""
    q = (question or "").lower()
    qwords = set(q.split())
    if any(w in qwords for w in _COMPARISON_WORDS):
        intent = "comparison"
    elif "table" in intents:
        intent = "table"
    elif any(b in intents for b in ("list", "ordered_list")):
        intent = "list"
    else:
        intent = None
    return {"intent": intent, "item_count": len(content),
            "columns": max(1, len(content))}


def _match(cond: Dict[str, Any], features: Dict[str, Any]) -> bool:
    """Match a rule's 'if' against features. Supports intent equality and
    numeric *_min / *_max bounds (columns_min -> features['columns'] >= v)."""
    for k, v in cond.items():
        if k == "intent":
            if features.get("intent") != v:
                return False
        elif k.endswith("_min"):
            if features.get(k[:-4], 0) < v:
                return False
        elif k.endswith("_max"):
            if features.get(k[:-4], 0) > v:
                return False
        elif features.get(k) != v:
            return False
    return True


class RuleBank:
    """Ordered rule bank consulted when entering a strategy state."""

    def __init__(self, rules: Optional[List[Dict[str, Any]]] = None):
        # None -> default bank; a LIST (even empty) is taken literally,
        # so RuleBank([]) really is empty (the falsy-list bug).
        self.rules = list(DEFAULT_RULE_BANK if rules is None else rules)

    def match(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        for rule in self.rules:
            if _match(rule["if"], features):
                return rule["then"]
        return None

    def add_rule(self, rule: Dict[str, Any]) -> None:
        # replace a same-name rule in place (idempotent training)
        for i, r in enumerate(self.rules):
            if r["name"] == rule["name"]:
                self.rules[i] = rule
                return
        self.rules.append(rule)

    def choose_layout(self, features: Dict[str, Any], default: str = "list") -> str:
        then = self.match(features)
        return then["layout"] if then else default

    def to_json(self) -> str:
        return json.dumps(self.rules, indent=2)


def correction_to_rule(features: Dict[str, Any], wrong: str,
                       correct: str) -> Dict[str, Any]:
    """Turn a user correction (ul -> table) into a guard rule."""
    cond: Dict[str, Any] = {}
    if features.get("intent"):
        cond["intent"] = features["intent"]
    if features.get("columns"):
        cond["columns_min"] = features["columns"]
    if features.get("item_count"):
        cond["item_count_min"] = features["item_count"]
    return {"name": f"prefer_{correct}_over_{wrong}",
            "if": cond, "then": {"layout": correct}}


def train_correction(bank: RuleBank, features: Dict[str, Any],
                     wrong: str, correct: str) -> Dict[str, Any]:
    """Train from a correction: diff intent (wrong->correct) -> add a guard."""
    rule = correction_to_rule(features, wrong, correct)
    bank.add_rule(rule)
    return rule


def log_trace(path: str, entry: Dict[str, Any]) -> None:
    """Append one outcome trace (features + chosen layout + judgment)."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(entry) + "\n")


def load_traces(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    out = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def choose_strategy(features: Dict[str, Any],
                    bank: Optional[RuleBank] = None) -> str:
    """Module-level strategy chooser (the chooselayoutstrategy meta-state)."""
    bank = bank or RuleBank()
    return bank.choose_layout(features)

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
