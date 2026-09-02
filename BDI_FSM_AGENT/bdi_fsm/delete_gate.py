"""delete_gate.py — BDI_ALLOW_DELETE env gate, default OFF.

Chris 2026-08-15: "disable deletion for bdi." The agent's knowledge (recipes,
corpus, entity DAGs, notes) is append-only by doctrine — never hard-delete.
Destructive operations are gated behind BDI_ALLOW_DELETE=1; by default they
are NO-OPS (data is kept, never removed).

Temp scratch cleanup (git clone dirs in github_corpus) is NOT gated: those
are ephemeral working dirs, not knowledge — leaving them would break re-clone.
"""

import os


def allow_delete() -> bool:
    return os.environ.get("BDI_ALLOW_DELETE", "0") == "1"
