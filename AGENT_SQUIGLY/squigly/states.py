r"""states.py — the census as STATES, and every change as a PRESSURE that produced a new one.

Chris 2026-08-17, on being asked what to do with local files:
    *"use them"* / *"is that 'applying something' yes"* / *"and then we get a new state"* /
    *"doesnt that fit??"*

It fits exactly. This module is that observation made executable.

WHY THIS IS NOT JUST A DIFF
    A census taken twice produces a diff: 17 added, 4 lost, 2 changed. A diff is a fact about two
    lists. What Chris described is a fact about the SYSTEM: something was applied, and the world
    moved from one state to another. The difference matters because a diff cannot be reasoned
    over and a transition can -- symbolic.py already computes bans of evidence over transitions,
    chains them (a + b + c = d), and answers "apply X to A" without a model anywhere in the loop.

THE MISSING NOUNS
    symbolic.py learned its 303 symbols from tool_tape, which records what the fleet DID. Those
    are verbs: tools, actions, pressures. It never had the nouns, so "apply X to A" could never
    have a file as its A. The census supplies them. That is the whole reason this bridge exists
    and why the census had to come first.

THE TRANSITIONS, AND WHY MOVE IS THE INTERESTING ONE
    absent  -> present          something was created
    present -> present_moved    same content hash, different path
    present -> present_modified same path, different hash
    present -> absent           genuinely gone

    Move is the one that pays for the hashing. Without content identity a reorganised folder
    reports as N losses and N creations -- the two loudest events in the system, both false, and
    the losses are the ones that scare you. With it, a move is one quiet fact. An index that
    cries wolf about reorganisation is an index nobody reads twice.
"""
import os

# The four pressures a file can be under. Deliberately few: these are the ones observable from two
# censuses alone, without a filesystem watcher and without guessing intent.
CREATED = "created"
MOVED = "moved"
MODIFIED = "modified"
LOST = "lost"


def _by_path(rows):
    return {r["path"]: r for r in rows}


def _by_hash(rows):
    out = {}
    for r in rows:
        h = r.get("sha256")
        if h:
            out.setdefault(h, []).append(r)
    return out


def transitions(before, after):
    """Every state change between two censuses, as (pressure, begin, end) records.

    Order matters. Moves are resolved BEFORE losses and creations are reported, because a moved
    file looks exactly like a loss plus a creation until content identity is checked. Resolving
    them first is what keeps the loss list short enough to be worth reading.
    """
    b_path, a_path = _by_path(before), _by_path(after)
    b_hash, a_hash = _by_hash(before), _by_hash(after)

    gone = set(b_path) - set(a_path)
    fresh = set(a_path) - set(b_path)
    out = []

    # 1. MOVES: content present on both sides, at different paths.
    moved_from, moved_to = set(), set()
    for h, olds in b_hash.items():
        news = a_hash.get(h)
        if not news:
            continue
        old_gone = [r for r in olds if r["path"] in gone]
        new_fresh = [r for r in news if r["path"] in fresh]
        for old, new in zip(old_gone, new_fresh):
            out.append({"pressure": MOVED, "begin": old["path"], "end": new["path"],
                        "sha256": h, "size": new["size"],
                        "why": "identical content at a different path"})
            moved_from.add(old["path"])
            moved_to.add(new["path"])

    # 2. MODIFIED: same path, different content.
    for p in set(b_path) & set(a_path):
        ob, oa = b_path[p], a_path[p]
        if ob.get("sha256") and oa.get("sha256") and ob["sha256"] != oa["sha256"]:
            out.append({"pressure": MODIFIED, "begin": p, "end": p,
                        "sha256_before": ob["sha256"], "sha256_after": oa["sha256"],
                        "size": oa["size"], "why": "same path, content changed"})

    # 3. LOST and CREATED: whatever the first two passes did not explain.
    for p in sorted(gone - moved_from):
        out.append({"pressure": LOST, "begin": p, "end": None,
                    "sha256": b_path[p].get("sha256"), "size": b_path[p]["size"],
                    "why": "no file at this path, and its content is nowhere else"})
    for p in sorted(fresh - moved_to):
        out.append({"pressure": CREATED, "begin": None, "end": p,
                    "sha256": a_path[p].get("sha256"), "size": a_path[p]["size"],
                    "why": "new content, not a move of anything known"})
    return out


def summarise(trans):
    """Counts per pressure, plus the losses spelled out. Losses are the ones a human must see."""
    counts = {}
    for t in trans:
        counts[t["pressure"]] = counts.get(t["pressure"], 0) + 1
    return {"counts": counts, "total": len(trans),
            "lost": [t["begin"] for t in trans if t["pressure"] == LOST][:50]}


def emit_to_symbolic(registry, rows, trans, source="squigly"):
    """Register files as SYMBOLS and their changes as OBSERVED TRANSITIONS.

    This is the join Chris described. Every file becomes a token of type "file", so it can be the
    A in "apply X to A"; every change becomes evidence that pressure X moved a file from one state
    to another. Once enough of those accumulate, symbolic.apply answers what a pressure does to a
    file, and chain() sums the bans across a sequence -- with no model involved at any point.

    Takes the registry as an argument rather than importing it. Squigly must stay usable on a
    machine that has no BDI agent installed; a census tool that cannot run without the thing it
    feeds is a dependency pointing the wrong way.
    """
    n_sym = n_obs = 0
    for r in rows:
        try:
            registry.token("file", r["path"])
            n_sym += 1
        except Exception:
            continue
    for t in trans:
        begin = t.get("begin") or "absent"
        end = t.get("end") or "absent"
        try:
            registry.observe(begin, t["pressure"], end)
            n_obs += 1
        except Exception:
            continue
    return {"source": source, "symbols": n_sym, "observations": n_obs}


# --------------------------------------------------------------------------------------------
# SELFTEST -- states had no direct test of its own. census and deps carried `__main__`
# selftests since 2026-09-23; states, the module that decides WHAT HAPPENED on the disk
# (move beats loss+create, the whole point of hashing), did not. Added 2026-09-29. Pure:
# no disk, no DB, no model -- the transitions logic is arithmetic over two row lists.
# --------------------------------------------------------------------------------------------
def _selftest():
    fails = []

    def row(p, h, size=100):
        return {"path": p, "sha256": h, "size": size}

    before = [row(r"C:\a\x.py", "h1"), row(r"C:\b\gone.py", "h2"), row(r"C:\c\edit.py", "h3"),
              row(r"C:\d\same.py", "h4")]
    after = [row(r"C:\a2\x.py", "h1"),  # moved: same hash, new path
             row(r"C:\c\edit.py", "h3b"),  # modified: same path, new hash
             row(r"C:\d\same.py", "h4"),  # unchanged
             row(r"C:\e\new.py", "h5")]  # created

    trans = transitions(before, after)

    def only(pressure):
        return [t for t in trans if t["pressure"] == pressure]

    m = only(MOVED)
    if len(m) != 1 or m[0]["begin"] != r"C:\a\x.py" or m[0]["end"] != r"C:\a2\x.py":
        fails.append("move not resolved as one move from C:\\a\\x.py: %r" % m)
    mo = only(MODIFIED)
    if len(mo) != 1 or mo[0]["sha256_before"] != "h3" or mo[0]["sha256_after"] != "h3b":
        fails.append("modified not detected on same path, new hash: %r" % mo)
    lo = only(LOST)
    if len(lo) != 1 or lo[0]["begin"] != r"C:\b\gone.py":
        fails.append("genuinely gone content not reported lost: %r" % lo)
    cr = only(CREATED)
    if len(cr) != 1 or cr[0]["end"] != r"C:\e\new.py":
        fails.append("genuinely new content not reported created: %r" % cr)

    # The one the hashing pays for: a reorganisation must NOT report a loss.
    reorg_before = [row(r"C:\old\k.py", "hk")]
    reorg_after = [row(r"C:\new\k.py", "hk")]
    reorg = transitions(reorg_before, reorg_after)
    if any(t["pressure"] == LOST for t in reorg):
        fails.append("a move with identical content reported LOST -- the wolf-crying bug")

    s = summarise(trans)
    if s["total"] != len(trans) or s["counts"].get(LOST) != 1 or s["counts"].get(MOVED) != 1:
        fails.append("summarise counts wrong: %r" % s["counts"])
    if s["lost"] != [r"C:\b\gone.py"]:
        fails.append("summarise did not spell out the loss: %r" % s["lost"])

    # Two identical censuses: no transitions at all, not 'everything created'.
    none = transitions(before, before)
    if none:
        fails.append("identical censuses produced transitions: %r" % none[:3])

    for f in fails:
        print("FAIL:", f)
    print("states selftest:", "ok" if not fails else "FAILED")
    return 0 if not fails else 1


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
