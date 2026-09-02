"""emotion.py — the emotional fiber bundle (colors for feelings).

Chris 2026-08-15: 1D sentiment [-1,+1] is "woefully inadequate" (nostalgia =
happy+sad, awe = fear+wonder). Attach to every point in the fuzzy logic space
an n-dimensional emotional color — an HSV coordinate:
    hue        -> core emotional category (red=urgency, blue=melancholy,
                  yellow=curiosity)
    saturation -> intensity
    value      -> cognitive weight / seriousness

"Continuous empathy": the reasoning path must maintain COLOR CONTINUITY — a
sudden discontinuity in the color manifold is an error. Deterministic, zero-LLM.
"""

from __future__ import annotations

import math
from typing import Dict, List, Tuple


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


class EmotionColor:
    """An HSV emotional color (hue in degrees, saturation/value in [0,1])."""

    __slots__ = ("hue", "saturation", "value")

    def __init__(self, hue: float, saturation: float = 0.5, value: float = 0.5):
        self.hue = hue % 360.0
        self.saturation = _clamp(saturation)
        self.value = _clamp(value)

    def to_hsv(self) -> Tuple[float, float, float]:
        return (self.hue, self.saturation, self.value)

    def __repr__(self) -> str:
        return (f"EmotionColor(h={self.hue:.0f}, s={self.saturation:.2f}, "
                f"v={self.value:.2f})")


# emotional categories -> hue (degrees around the color wheel)
EMOTION_HUES: Dict[str, float] = {
    "urgency": 0, "anger": 10, "passion": 20,
    "joy": 55, "curiosity": 60, "hope": 90,
    "calm": 150, "trust": 160,
    "melancholy": 240, "sadness": 250, "grief": 270, "nostalgia": 285,
    "wonder": 300, "awe": 310, "fear": 330,
}

# lexicon: word -> (emotion, saturation)
EMOTION_LEXICON: Dict[str, Tuple[str, float]] = {
    "angry": ("anger", 0.9), "urgent": ("urgency", 0.85), "joy": ("joy", 0.9),
    "happy": ("joy", 0.7), "glad": ("joy", 0.6), "curious": ("curiosity", 0.7),
    "hope": ("hope", 0.7), "hopeful": ("hope", 0.8), "calm": ("calm", 0.5),
    "sad": ("sadness", 0.8), "sorrow": ("sadness", 0.85), "grief": ("grief", 0.9),
    "nostalgia": ("nostalgia", 0.85), "nostalgic": ("nostalgia", 0.8),
    "awe": ("awe", 0.9), "fear": ("fear", 0.85), "afraid": ("fear", 0.8),
    "scared": ("fear", 0.85), "wonder": ("wonder", 0.8), "miss": ("nostalgia", 0.7),
    "remember": ("nostalgia", 0.5), "love": ("passion", 0.85),
    "melancholy": ("melancholy", 0.85), "lonely": ("melancholy", 0.8),
}


def emotion_of(text: str) -> EmotionColor:
    """Deterministic emotional color: blend matched emotion words.

    Hue = saturation-weighted circular mean of matched hues; saturation = max
    matched; value = cognitive weight (word count / cap).
    """
    t = (text or "").lower()
    hues: List[float] = []
    sats: List[float] = []
    for word, (emo, sat) in EMOTION_LEXICON.items():
        if word in t:
            hues.append(EMOTION_HUES[emo])
            sats.append(sat)
    value = _clamp(len(t.split()) / 40.0)
    if not hues:
        return EmotionColor(0, 0.0, value)  # neutral (gray)
    x = sum(math.cos(math.radians(h)) * s for h, s in zip(hues, sats))
    y = sum(math.sin(math.radians(h)) * s for h, s in zip(hues, sats))
    hue = (math.degrees(math.atan2(y, x)) + 360) % 360
    return EmotionColor(hue, max(sats), value)


def hue_distance(h1: float, h2: float) -> float:
    d = abs(h1 - h2) % 360
    return min(d, 360 - d)


def continuity(c1: EmotionColor, c2: EmotionColor) -> float:
    """0 = identical, 1 = maximally jarring (weighted HSV distance)."""
    dh = hue_distance(c1.hue, c2.hue) / 180.0
    ds = abs(c1.saturation - c2.saturation)
    dv = abs(c1.value - c2.value)
    return 0.6 * dh + 0.25 * ds + 0.15 * dv


def is_continuous(c1: EmotionColor, c2: EmotionColor, max_jump: float = 0.4) -> bool:
    """Color-continuity gate: a reasoning step is valid only if not jarring."""
    return continuity(c1, c2) <= max_jump
