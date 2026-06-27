from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Iterable


PROJECT_ID = "VIPER_JAVA_RISC"
AGENT_ID = "viperAI"


@dataclass(frozen=True)
class LayerSignal:
    name: str
    score: float
    confidence: float = 1.0
    safety: float = 1.0
    cost: float = 0.0
    latency_ms: int = 0


@dataclass(frozen=True)
class ChoiceOption:
    name: str
    layers: tuple[LayerSignal, ...]
    prior: float = 0.5


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def layer_utility(layer: LayerSignal) -> float:
    score = clamp(layer.score)
    confidence = clamp(layer.confidence)
    safety = clamp(layer.safety)
    cost_penalty = clamp(layer.cost)
    latency_penalty = clamp(layer.latency_ms / 60000.0)
    return (score * confidence * safety) - (0.35 * cost_penalty) - (0.15 * latency_penalty)


def option_utility(option: ChoiceOption, temperature: float = 0.25) -> dict:
    layer_values = [layer_utility(layer) for layer in option.layers]
    if not layer_values:
        combined = clamp(option.prior) * 0.1
    else:
        # One or many layers: product rewards agreement, mean keeps weak layers from zeroing the whole choice.
        product = math.prod(max(0.001, clamp(value, -1.0, 1.0) + 1.0) for value in layer_values)
        geometric = (product ** (1.0 / len(layer_values))) - 1.0
        arithmetic = sum(layer_values) / len(layer_values)
        combined = (0.62 * arithmetic) + (0.28 * geometric) + (0.10 * clamp(option.prior))
    safety_floor = min((clamp(layer.safety) for layer in option.layers), default=1.0)
    gated = combined if safety_floor >= 0.7 else min(combined, 0.0)
    logit = gated / max(0.05, temperature)
    return {
        "name": option.name,
        "utility": round(gated, 6),
        "logit": round(logit, 6),
        "safety_floor": round(safety_floor, 6),
        "layers": [asdict(layer) | {"utility": round(layer_utility(layer), 6)} for layer in option.layers],
        "status": "candidate" if safety_floor >= 0.7 else "blocked_by_safety_floor",
    }


def choose(options: Iterable[ChoiceOption], temperature: float = 0.25) -> dict:
    scored = [option_utility(option, temperature=temperature) for option in options]
    if not scored:
        return {
            "project_id": PROJECT_ID,
            "agent_id": AGENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "no_options_available",
            "winner": None,
            "options": [],
        }
    max_logit = max(item["logit"] for item in scored)
    exp_values = [math.exp(item["logit"] - max_logit) if item["status"] == "candidate" else 0.0 for item in scored]
    total = sum(exp_values) or 1.0
    for item, exp_value in zip(scored, exp_values):
        item["probability"] = round(exp_value / total, 6)
    winner = max(scored, key=lambda item: (item["probability"], item["utility"]))
    return {
        "project_id": PROJECT_ID,
        "agent_id": AGENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "kind": "viper_stochastic_logic_decider",
        "status": "live_stochastic_evaluator",
        "formula": "utility=(score*confidence*safety)-(0.35*cost)-(0.15*latency_norm); softmax over one-or-many layer utilities; safety floor blocks below 0.7",
        "winner": winner["name"] if winner["status"] == "candidate" else None,
        "options": scored,
    }


def demo_options() -> list[ChoiceOption]:
    return [
        ChoiceOption(
            "house_chat",
            (
                LayerSignal("real_model_source", 0.98, confidence=0.95, safety=0.95, cost=0.4, latency_ms=25000),
                LayerSignal("markov_continuity", 0.72, confidence=0.70, safety=0.95, cost=0.05, latency_ms=20),
            ),
            prior=0.8,
        ),
        ChoiceOption(
            "sprite_route",
            (
                LayerSignal("explicit_action_terms", 0.88, confidence=0.9, safety=0.9, cost=0.15, latency_ms=500),
                LayerSignal("proposal_gate", 0.92, confidence=0.9, safety=0.98, cost=0.1, latency_ms=500),
            ),
            prior=0.65,
        ),
        ChoiceOption(
            "scripted_chat",
            (
                LayerSignal("speed", 0.95, confidence=1.0, safety=0.2, cost=0.01, latency_ms=1),
            ),
            prior=0.0,
        ),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="VIPER stochastic logic skeleton; offline/proposal only.")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--temperature", type=float, default=0.25)
    args = parser.parse_args()
    payload = choose(demo_options(), temperature=args.temperature)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
