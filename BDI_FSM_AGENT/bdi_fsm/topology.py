"""topology.py — the 8-vector universal code topology (precedence-correct).

Chris 2026-08-15: reduce programming to its fundamental physics — Data
Transformation and Control Flow. Every language maps to 8 Universal
Programmatic Actions; syntax changes, topology is identical. This module maps a
line of code (or a sensory/metaphorical concept word) into the 8-vector space.

Fixes over the original sketch:
  * precedence-correct: '==' is EVALUATE, not TRANSITION (bare '=' excludes
    comparison operators via lookbehind/lookahead)
  * returns a vector SET per line (a line can do several things at once)
  * stable sha256 line hash (Python's hash() is salted per-process)
  * stdlib only, no numpy

Deterministic, zero-LLM.
"""

from __future__ import annotations

import hashlib
import re
from typing import Dict, List, Tuple

VECTOR_NAMES: Dict[int, str] = {
    0: "ALLOCATE",    # creation / birth
    1: "EMIT",        # output / talk
    2: "TRANSITION",  # mutation / state shift
    3: "EVALUATE",    # conditional / comparison
    4: "PURGE",       # destruction / death
    5: "BIND",        # coupling / import
    6: "LOOP",        # iteration / pulse
    7: "LISTEN",      # ingestion / input
}

# (vector_id, regex) — checked in order; a line collects ALL matching vectors.
PATTERNS: List[Tuple[int, str]] = [
    # ALLOCATE — instantiation, memory reservation
    (0, r"\b(let|var|const|def|class|struct|fn|func|function|type|enum|new|"
         r"malloc|create|CREATE\s+TABLE)\b"),
    # EVALUATE — conditional / comparison (checked BEFORE bare '=')
    (3, r"\b(if|elif|else|switch|case|match|when|guard|where|assert|unless|"
         r"cond|and|or|not|in|is)\b"),
    (3, r"==|!=|<=|>=|&&|\|\|"),
    # TRANSITION — compound assignment, then bare assignment (excludes == <= >= !=)
    (2, r"(?:\+=|-=|\*=|/=|%=|&=|\|=|\^=|<<=|>>=)"),
    (2, r"(?<![=!<>+\-*/%&|^])=(?!=)"),
    (2, r"\b(set|update|mutate|alter|append|push|pop|inc|dec|assign)\b"),
    # PURGE — garbage collection, destruction
    (4, r"\b(del|free|drop|delete|DROP|remove|destroy|close|clear|dispose|"
         r"release|unset)\b"),
    # BIND — coupling, linking, import
    (5, r"\b(import|require|include|use|using|join|attach|extend|implements|"
         r"with|link)\b"),
    # LOOP — iteration, continuous execution
    (6, r"\b(for|while|loop|foreach|repeat|until|do)\b"),
    # LISTEN — ingestion, listening, reading
    (7, r"\b(read|fetch|get|input|listen|receive|select|SELECT|scan|readline|"
         r"subscribe)\b"),
    # EMIT — output, broadcasting
    (1, r"\b(print|return|yield|echo|write|send|emit|respond|log)\b"),
]

# sensory / metaphorical lexicon -> vector (the "sensory stripping" layer)
CONCEPT_MAP: Dict[str, int] = {
    # PURGE
    "eat": 4, "consume": 4, "destroy": 4, "forget": 4, "die": 4, "delete": 4,
    # BIND
    "touch": 5, "connect": 5, "grab": 5, "marry": 5, "attach": 5, "link": 5,
    # LISTEN
    "hear": 7, "smell": 7, "see": 7, "receive": 7, "listen": 7, "watch": 7,
    # EMIT
    "speak": 1, "talk": 1, "paint": 1, "show": 1, "shine": 1, "write": 1,
    # LOOP
    "walk": 6, "breathe": 6, "pulse": 6, "repeat": 6, "cycle": 6,
    # TRANSITION
    "move": 2, "change": 2, "shift": 2, "grow": 2, "drift": 2,
    # EVALUATE
    "decide": 3, "feel": 3, "check": 3, "taste": 3, "judge": 3,
    # ALLOCATE
    "create": 0, "birth": 0, "spawn": 0, "imagine": 0, "born": 0,
}


def map_code_line(line: str) -> Tuple[int, ...]:
    """Classify a line of code into a SET of the 8 universal vectors."""
    found = []
    for vector_id, pattern in PATTERNS:
        if re.search(pattern, line, re.IGNORECASE):
            if vector_id not in found:
                found.append(vector_id)
    if not found:
        found.append(2)  # default fallback: TRANSITION (state shift)
    return tuple(sorted(found))


def map_concept_word(word: str) -> int:
    """Translate a sensory/metaphorical word into a system-action vector."""
    clean = (word or "").lower().strip()
    if clean in CONCEPT_MAP:
        return CONCEPT_MAP[clean]
    # deterministic fallback for unseen edge-case concepts
    return len(clean) % 8


def line_hash(line: str) -> int:
    """Stable, reproducible line hash (sha256, not Python's salted hash())."""
    return int(hashlib.sha256(line.encode("utf-8")).hexdigest(), 16) % 1000


def indent_depth(line: str, tab_width: int = 4) -> int:
    """Structural tree depth from leading whitespace (tabs = tab_width)."""
    stripped = line.lstrip(" \t")
    leading = line[: len(line) - len(stripped)]
    return sum(tab_width if c == "\t" else 1 for c in leading) // tab_width


def process_file(file_content: str, file_extension: str) -> List[Dict]:
    """Parse any source/config into a stream of 8-vector topology frames."""
    frames = []
    for idx, line in enumerate(file_content.splitlines()):
        clean = line.strip()
        if not clean or clean.startswith(("#", "//", ";")):
            continue
        vectors = map_code_line(clean)
        frames.append({
            "line_num": idx + 1,
            "raw_line": clean,
            "file_type": file_extension,
            "vectors": vectors,
            "universal_actions": [VECTOR_NAMES[v] for v in vectors],
            "depth": indent_depth(line),
            "line_hash": line_hash(clean),
        })
    return frames

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
