r"""tape.py — give a state transition its VERB, from the tool tape.

Chris 2026-08-17: *"oh sophia plus tape! =win"* / *"do the tape join"*.

THE PROBLEM THIS SOLVES
    states.transitions() can see that a file changed, and can prove a move by content hash. What
    it cannot see is WHO. Every pressure it emits is generic -- created, moved, modified, lost --
    and a symbolic registry fed on generic pressures learns that "modified" leads to "modified".
    The verb is the whole content of the evidence.

WHAT THE TAPE ACTUALLY CONTAINS (measured, 2026-08-17)
    14,966 rows, 46 distinct tools, spanning 2026-08-03 to 2026-08-17. And 5 rows with any args at
    all: hive_daemon was the only producer and it passed args=None literally. So for almost every
    row the tape knows a cell ticked and nothing about what it touched.

    That was fixed at the source (hive_daemon._touched now records the paths cells report), but it
    only fixes rows written from now on. Fourteen thousand existing rows cannot be retro-fitted,
    and this module must be honest about that rather than inventing coverage.

WHY THERE IS NO TIME-ONLY FALLBACK
    It would be easy to attribute a file change to whichever cell was running when the mtime says
    it happened, and it would look like it worked -- every transition would get a verb, coverage
    would read 100%, and the registry would fill up. It would also be wrong. On a box running
    thirty cells on overlapping schedules, "was running at the time" is true of several cells for
    almost any instant, and picking one is a coin flip recorded as a fact. Bans are computed from
    counts of observed transitions; feeding them coin flips does not add noise to the evidence, it
    manufactures evidence that was never observed.

    So: a transition gets a verb when a tape row NAMES its path, and stays generic otherwise. The
    coverage number is allowed to be small. It is not allowed to be fictional.
"""
import json
import os
import sqlite3

DEFAULT_DB = r"C:\Viper\databases\telemetry\telemetry.db"

# How far apart a tape row and a file's mtime may be and still be considered the same event, once
# a path has ALREADY matched. This is a tie-breaker between candidate rows, never a way in.
WINDOW_S = 900


def _norm(p):
    """Compare paths the way the filesystem does: absolute, one separator, case-folded on Windows."""
    try:
        return os.path.normcase(os.path.abspath(p))
    except Exception:
        return (p or "").lower()


def tape_rows(db=DEFAULT_DB, since=None, limit=200000):
    """Tape rows that name at least one path. Returns [] if the tape is absent or unreadable.

    An absent telemetry DB is a normal state on a fresh machine, not an error -- Squigly must run
    on a box that has never had the hive installed.
    """
    if not os.path.isfile(db):
        return []
    q = "SELECT ts, tool, args, prev_tool, secs FROM tool_tape WHERE args IS NOT NULL AND args != ''"
    params = []
    if since:
        q += " AND ts >= ?"
        params.append(since)
    q += " ORDER BY ts DESC LIMIT ?"
    params.append(int(limit))
    try:
        con = sqlite3.connect("file:%s?mode=ro" % db.replace("\\", "/"), uri=True)
        con.row_factory = sqlite3.Row
        rows = con.execute(q, params).fetchall()
        con.close()
    except sqlite3.Error:
        return []

    out = []
    for r in rows:
        try:
            args = json.loads(r["args"])
            # Unwrap double encoding. Rows written before the producer was fixed hold a JSON
            # STRING containing JSON, so one decode yields a str rather than a dict. Reading those
            # is free; refusing them would discard real evidence over a formatting mistake.
            if isinstance(args, str):
                args = json.loads(args)
        except (ValueError, TypeError):
            continue
        paths = args.get("paths") if isinstance(args, dict) else None
        if not paths:
            continue
        out.append({"ts": r["ts"], "tool": r["tool"], "prev_tool": r["prev_tool"],
                    "secs": r["secs"], "paths": [_norm(p) for p in paths]})
    return out


def index_by_path(rows):
    """{normalised path: [tape row, ...]} newest first."""
    idx = {}
    for r in rows:
        for p in r["paths"]:
            idx.setdefault(p, []).append(r)
    return idx


def name_pressures(trans, tape=None, db=DEFAULT_DB):
    """Attach the responsible tool to each transition WHERE THE TAPE NAMES ITS PATH.

    Returns (enriched transitions, coverage report). Each transition gains:
        `verb`       the tool, when known; otherwise the generic pressure unchanged
        `verb_from`  "tape" or "unattributed" -- so a consumer can tell evidence from default

    A transition whose path no tape row mentions keeps its generic pressure and is counted as
    unattributed. That count is the honest measure of how much the tape can currently explain.
    """
    idx = index_by_path(tape if tape is not None else tape_rows(db))
    named = 0
    out = []
    for t in trans:
        target = t.get("end") or t.get("begin")
        hits = idx.get(_norm(target)) if target else None
        if hits:
            best = hits[0]
            out.append(dict(t, verb=best["tool"], verb_from="tape",
                            verb_ts=best["ts"], prev_tool=best.get("prev_tool")))
            named += 1
        else:
            out.append(dict(t, verb=t["pressure"], verb_from="unattributed"))
    total = len(trans)
    return out, {
        "transitions": total,
        "named_by_tape": named,
        "unattributed": total - named,
        "coverage_pct": round(100.0 * named / total, 1) if total else 0.0,
        "tape_paths_known": len(idx),
        "note": ("Coverage is limited by how many tape rows carry paths. hive_daemon._touched "
                 "records them from now on; rows written before 2026-08-17 have none and cannot "
                 "be retro-fitted. No time-only attribution is performed, by design."),
    }


def to_observations(named):
    """Transitions ready for symbolic.observe(begin, pressure, end).

    ONLY the tape-attributed ones. An unattributed transition still describes a real change and is
    worth reporting to a human, but as evidence it says "something modified this file", which is
    true of every modification and therefore carries no information. Bans computed over it would
    be bans over a tautology.
    """
    return [{"begin": t.get("begin") or "absent",
             "pressure": t["verb"],
             "end": t.get("end") or "absent",
             "ts": t.get("verb_ts")}
            for t in named if t.get("verb_from") == "tape"]
