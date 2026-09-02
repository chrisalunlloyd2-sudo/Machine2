r"""weight.py — how much does this file matter, as a number nobody had to assign.

Chris 2026-08-17: *"Good point weight the files"* — following the observation that a file with
twenty dependents is not the same object as a file with none.

WEIGHT IS COMPUTED, NEVER DECLARED
    A hand-assigned importance field rots the day someone refactors and nobody updates it, and it
    encodes an opinion that cannot be checked. Everything here is derived from the dependency graph
    and the copy count, so it is recomputed from the disk every census and can only ever be as
    wrong as the graph is.

THE TWO FACTORS, AND WHY THEY MULTIPLY

    BLAST RADIUS -- how many files stop working if this one vanishes. Not the direct dependent
    count: if resource_governor.py breaks, everything importing its twenty dependents breaks too.
    That is the transitive closure of the reverse graph, and it is the honest answer to "what
    breaks if this goes".

    SCARCITY -- how few copies exist. A file with a blast radius of 200 that lives in git, the
    OneDrive mirror and the vault is well defended. The same file existing only on C: is one bad
    sector from taking 200 others with it.

    They multiply because neither alone is danger. A critical file with four copies is safe; a
    unique file nothing depends on is expendable. Danger is the product -- important AND fragile --
    and it is the product, not either factor, that should decide what gets attention first.

WHAT WEIGHT IS FOR
    Ordering. Which files to back up first when the pass is bounded, which to protect from prune,
    which to surface to Aegis when something moves. It is a priority, not a verdict, and nothing in
    Squigly deletes anything regardless of what it computes.
"""
import math
import os

# Weight below which a file is unremarkable. Used only to keep reports short.
NOTABLE = 2.0


def blast_radius(rev, path, _seen=None, _memo=None):
    """How many distinct files transitively depend on `path`.

    Memoised depth-first with a cycle guard, because import graphs contain cycles routinely (two
    modules importing each other is legal and common) and a naive closure would not terminate.
    A node currently on the stack contributes nothing rather than recursing -- it is already
    counted by the frame that is expanding it.
    """
    if _memo is None:
        _memo = {}
    if _seen is None:
        _seen = set()
    if path in _memo:
        return _memo[path]
    if path in _seen:
        return set()
    _seen.add(path)

    out = set()
    for user in rev.get(path, ()):
        out.add(user)
        out |= blast_radius(rev, user, _seen, _memo)
    _seen.discard(path)
    _memo[path] = out
    return out


def all_blast_radii(rev):
    """Blast radius for every file that has one. Shares a memo across the whole graph."""
    memo = {}
    return {p: blast_radius(rev, p, set(), memo) for p in rev}


def scarcity(copies):
    """Fragility from copy count. 1 copy -> 1.0, 2 -> 0.5, 3 -> 0.33, 4+ -> diminishing.

    Deliberately 1/n rather than a cliff at some threshold. The jump from one copy to two is the
    one that matters enormously -- it is the difference between "loss is possible" and "loss
    requires two independent failures" -- and every copy after that helps less than the one before.
    1/n has that shape built in and needs no tuning.
    """
    return 1.0 / max(1, int(copies))


def weigh(rows, rev, copies_of=None):
    """Weight every file. Returns {path: {...}} sorted-ready, never raising on a missing input.

    `copies_of` is an optional callable path -> int. When absent every file is treated as having
    one copy, which OVER-states danger uniformly. That is the safe direction to be wrong in: it
    makes things look more fragile than they are, so nothing gets quietly deprioritised because
    Squigly could not reach the backup ledger.
    """
    radii = all_blast_radii(rev)
    out = {}
    for r in rows:
        p = r["path"]
        radius = len(radii.get(p, ()))
        direct = len(rev.get(p, ()))
        try:
            n_copies = int(copies_of(p)) if copies_of else 1
        except Exception:
            n_copies = 1
        # log1p keeps one enormously-depended-upon file from flattening every other score to noise
        importance = math.log1p(radius)
        w = importance * scarcity(n_copies)
        out[p] = {"weight": round(w, 4), "blast_radius": radius, "direct_dependents": direct,
                  "copies": n_copies, "scarcity": round(scarcity(n_copies), 3),
                  "name": r.get("name", os.path.basename(p))}
    return out


def ranked(weights, limit=25, notable=NOTABLE):
    """Heaviest first. The order to back up in, and the order to worry in."""
    rows = [dict(v, path=k) for k, v in weights.items() if v["weight"] >= 0]
    rows.sort(key=lambda d: (-d["weight"], -d["blast_radius"], d["path"]))
    return [r for r in rows[:limit] if r["weight"] >= notable or r["blast_radius"] > 0]
