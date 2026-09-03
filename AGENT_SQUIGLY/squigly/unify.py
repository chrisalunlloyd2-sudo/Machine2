r"""unify.py — one command that runs the whole chain and keeps the master list refreshed.

Chris 2026-08-17: *"do the tape join, makesure we have hardened foundry acces and unification and
dont misxs anything"*.

THE CHAIN
    census    what exists, hashed for identity
    classify  what each file is for, quoted from the author where possible
    deps      what uses what, including the PowerShell and batch wiring
    weight    blast radius x scarcity -- what matters and what is fragile
    states    what changed since last time, as pressures producing new states
    tape      who did it, where the tape names a path

    Each stage is separately testable and none of them needs a model. Running them together is
    what makes the result a system rather than six scripts, which is the unification asked for.

REFRESH IS A DIFF AGAINST THE LAST RUN
    The master list is stored so the next run can say what MOVED, not merely what is there now. A
    census with no predecessor is a photograph; a census with one is a report. The first run on a
    machine therefore has no transitions and says so, rather than reporting every file as newly
    created -- which would be technically true and completely useless.

NOTHING HERE DELETES, MOVES, OR EXECUTES ANYTHING
    It reads the disk and writes one JSON file plus one Markdown report. Squigly's whole value is
    being the thing you can point at your entire drive without thinking twice about it.
"""
import json
import os
import time

from . import census, classify, deps, states, tape, weight

STATE_DIR = os.environ.get("SQUIGLY_STATE", r"C:\Viper\databases\squigly")
MASTER = os.path.join(STATE_DIR, "master.json")
REPORT = os.path.join(STATE_DIR, "MASTER.md")

# THE CODE, NOT THE DATA. This was [r"C:\Viper"], and C:\Viper is mostly not
# code. Measured 2026-09-02, after .eml was excluded:
#
#     chats       22,621 files   15 MB    conversation logs
#     databases    6,137 files 2,439 MB   sqlite, master lists, the mail store
#     backups      1,631 files   190 MB
#     projects     2,082 files    63 MB   <- code
#     scripts        878 files    23 MB   <- code
#     logs/quarantine/build/models  456 files
#
# 33,889 files walked and hashed so that 2,960 of them -- 9% -- could be
# catalogued. The full pass took 601.7s against a 600s deadline, so it never
# once COMPLETED: it hit the wall and stopped, every time, and the partial
# result was indistinguishable from a finished one. That is the run that took
# the whole hive down for seven hours on 2026-09-01.
#
# 601.7s is also the exact figure never_twice recorded for this cell on
# 2026-08-28. The cost was measured, written down, and never acted on.
#
# This is a CODE census: it builds an import graph and detects moved source.
# Chat logs and a 1.4 GB mail store are data with their own indexes. Naming the
# code roots is more honest than blocking a dozen generic directory names, and
# a caller who wants a wider sweep can still pass roots= explicitly.
# EXHAUSTIVE, and that is the point. Chris 2026-09-02: "it doesn't matter
# really as long as the backup is exhaustive... that USB is never leaving, its a
# permanent backup in case the system hard fails and we lose everything."
#
# So this walks all of C:\Viper -- chats, databases, backups, the lot. It was
# briefly narrowed to scripts+projects to make it fit a 600s deadline, which
# solved the wrong problem: this census is the inventory behind a permanent
# backup, and an inventory that skips 91% of the files is not an inventory.
#
# The cost is real and is now BUDGETED rather than clipped:
#
#     chats       22,621 files            databases  6,137 (2,439 MB)
#     backups      1,631                 projects   2,082   scripts 878
#     33,889 total -- 601.7s against a 600s deadline, so it never once
#     COMPLETED. It hit the wall every run and the partial result was
#     indistinguishable from a finished one.
#
# It gets 19 minutes every 20 as a SERVICE, not a hive cell. A 1,140s cell
# would hold the hive for 95% of every hour: hive_daemon runs cells strictly
# sequentially, so all 70 others would starve -- which is precisely the
# 2026-09-01 outage put on a timer. Same reasoning that made miner_daemon and
# coding_engine.soak services.
# CODE FIRST, THEN EVERYTHING. Still exhaustive -- C:\Viper is the last root and
# nothing is excluded -- but the ORDER now decides what a deadline costs.
#
# Measured 2026-09-03 against the 2026-08-29 baseline: of C:\Viper's 24 top-level
# directories the census had captured SEVEN -- agents, backups, build, chats,
# config, data, databases -- and stopped dead inside `databases` (85,088 of its
# 101,733 rows). os.walk yields top-level names alphabetically, `databases` is
# the 7th and the largest, and the deadline fired there every single run. So
# `projects`, `scripts`, `models`, `quarantine`, `reports`, `snapshots` and ten
# others were never once walked.
#
# Which means the change tracker's baseline did not contain Chris's CODE, and a
# transition report built on it would have covered email archives and chats
# while reporting nothing at all about scripts. Chris 2026-09-03, on being told:
# *"what? OK let's fix this."*
#
# scripts BEFORE projects on purpose. Both are junctions into gan-otg-db and
# `projects` CONTAINS viper-scripts, so whichever is walked first wins the path
# recorded. walk() dedupes by os.path.realpath in a `seen_dirs` set built once
# across all roots, so the loser is skipped rather than walked twice -- putting
# scripts first records her code under C:\Viper\scripts, the path she actually
# uses, instead of C:\Viper\projects\viper-scripts.
#
# This is ordering only. No root is dropped and no new tree is added, so a
# completed census produces exactly the same set of files as before.
DEFAULT_ROOTS = [
    r"C:\Viper\scripts",    # her code, first, so a cut never costs it
    r"C:\Viper\projects",   # the rest of gan-otg-db
    r"C:\Viper",            # exhaustive; dedupes against the two above
]


def _load_master():
    try:
        with open(MASTER, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _save_master(doc):
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp = "%s.%d.tmp" % (MASTER, os.getpid())
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1)
    os.replace(tmp, MASTER)


def refresh(roots=None, hash_files=True, emit_registry=None, write_report=True,
            deadline_s=None):
    """Run the whole chain. Returns a summary; writes the master list and the report.

    `emit_registry` is an optional symbolic registry. Passed in rather than imported so Squigly
    stays usable on a machine with no BDI agent installed -- a census tool that cannot run without
    the thing it feeds has its dependency pointing the wrong way.
    """
    roots = roots or DEFAULT_ROOTS
    t0 = time.time()

    prev = _load_master()
    prev_rows = prev.get("rows", []) if prev else []
    prev_by_path = {r["path"]: r for r in prev_rows}

    c = census.census(roots, hash_files=hash_files, deadline_s=deadline_s,
                      prev_by_path=prev_by_path)
    rows = c["rows"]

    # THE DEADLINE MUST COVER THE GRAPH TOO, not just the walk.
    #
    # Measured: a full-tree refresh with deadline_s=3000 burned 22,548 SECONDS OF CPU -- over six
    # CPU-hours -- and was still going. The walk stopped on time; build_graph did not, because it
    # ast.parses every Python file and regexes every text file AFTER the census returns, and
    # nothing bounded it. A deadline that covers the cheap half of a job and not the expensive
    # half is not a deadline.
    #
    # The graph is also the part that degrades gracefully: a census with no dependency edges is
    # still a complete inventory of what exists and what changed, which is most of the value. So
    # when the budget is gone, skip the graph and say so, rather than silently taking six hours.
    spent = time.time() - t0
    graph_budget = (deadline_s - spent) if deadline_s else None
    if graph_budget is not None and graph_budget <= 0:
        edges, _idx, unresolved = {}, {}, {}
        graph_skipped = True
    else:
        edges, _idx, unresolved = deps.build_graph(rows, roots, deadline_s=graph_budget)
        graph_skipped = False
    rev = deps.dependents(edges)
    weights = weight.weigh(rows, rev)

    # A PARTIAL CENSUS MUST NOT BE DIFFED. It covers fewer files by design, so every file the
    # walk did not reach would be reported LOST -- the most alarming and least true thing this
    # system could say. A partial run still refreshes what it saw; it just does not claim to know
    # what it did not look at.
    trans = states.transitions(prev_rows, rows) if (prev_rows and not c.get("partial")) else []
    named, coverage = tape.name_pressures(trans) if trans else ([], {
        "transitions": 0, "named_by_tape": 0, "unattributed": 0, "coverage_pct": 0.0,
        "note": ("partial census -- not diffed, because unvisited files would read as lost"
                 if c.get("partial") else
                 "first census on this machine -- nothing to diff against yet")})

    emitted = None
    if emit_registry is not None and named:
        emitted = states.emit_to_symbolic(emit_registry, rows, named)

    # Store a slim row: enough to diff and to weigh, without a 400 MB master file.
    slim = [{"path": r["path"], "size": r["size"], "mtime": r["mtime"],
             "sha256": r.get("sha256"), "name": r["name"], "ext": r["ext"]} for r in rows]
    doc = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "roots": roots,
           "files": c["files"], "bytes": c["bytes"], "rows": slim}
    _save_master(doc)

    summary = {
        "files": c["files"],
        "partial": c.get("partial", False),
        "hashes_reused": c.get("hashes_reused", 0),
        "gb": round(c["bytes"] / 1073741824, 3),
        "census_secs": c["secs"],
        "edges": len(edges),
        "graph_skipped": graph_skipped,
        "depended_upon": len(rev),
        "unresolved_modules": len(unresolved),
        "transitions": states.summarise(named or trans) if (named or trans) else {"total": 0},
        "tape_coverage": coverage,
        "emitted_to_symbolic": emitted,
        "heaviest": weight.ranked(weights, limit=15),
        "secs": round(time.time() - t0, 1),
    }
    if write_report:
        _write_report(summary, rows, rev)
    return summary


def _write_report(summary, rows, rev):
    """The human-readable master list. Chris's policy: a person must be able to read it cold."""
    os.makedirs(STATE_DIR, exist_ok=True)
    cov = summary["tape_coverage"]
    L = [
        "# Squigly master list",
        "",
        "Generated %s. Rewritten every refresh — do not edit." % summary.get("at", time.strftime("%Y-%m-%d %H:%M")),
        "",
        "**%d files, %.2f GB.** Census %.1fs, whole chain %.1fs."
        % (summary["files"], summary["gb"], summary["census_secs"], summary["secs"]),
        "",
        "## What changed since last time",
        "",
    ]
    t = summary["transitions"]
    if not t.get("total"):
        L.append("Nothing — or this is the first census on this machine, which has nothing to")
        L.append("diff against. A census with no predecessor is a photograph, not a report.")
    else:
        L.append("| Pressure | Count |")
        L.append("|---|---:|")
        for k, v in sorted(t.get("counts", {}).items()):
            L.append("| %s | %d |" % (k, v))
        if t.get("lost"):
            L += ["", "### Lost — content that is nowhere else", ""]
            L += ["- `%s`" % p for p in t["lost"][:25]]
    L += [
        "",
        "## Who did it",
        "",
        "%d of %d transitions were attributed to a named tool by the tape (%.1f%%)."
        % (cov.get("named_by_tape", 0), cov.get("transitions", 0), cov.get("coverage_pct", 0.0)),
        "",
        cov.get("note", ""),
        "",
        "## Heaviest files — blast radius × scarcity",
        "",
        "Blast radius is the *transitive* count of what stops working if this file goes, not the",
        "direct dependent count. `agent_toolkit.py` has one direct dependent and thirty-four",
        "transitive: by a flat count it reads as trivial and prunable, and it is load-bearing.",
        "",
        "| File | Weight | Blast radius | Direct |",
        "|---|---:|---:|---:|",
    ]
    for r in summary["heaviest"]:
        L.append("| `%s` | %.3f | %d | %d |"
                 % (r["name"], r["weight"], r["blast_radius"], r["direct_dependents"]))
    L += [
        "",
        "## Blind spots, stated on purpose",
        "",
        "Dynamic imports, `importlib` by computed name, and paths built by concatenation are not",
        "found. `%%VAR%%` and `$env:` expansions in scripts are skipped rather than guessed. So an",
        "orphan list is **candidates for review, never a delete list** — one that is quietly wrong",
        "is more dangerous than one that names what it cannot see, because someone eventually",
        "deletes from it.",
        "",
        "**Squigly never deletes, moves, or executes anything.**",
        "",
    ]
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


def tick():
    """Hive entrypoint. Never raises: a crashed cell must land as a failed cell, not a dead pass."""
    try:
        s = refresh(deadline_s=600)
        return {"ok": True, "files": s["files"], "edges": s["edges"],
                "transitions": s["transitions"].get("total", 0),
                "tape_coverage_pct": s["tape_coverage"].get("coverage_pct", 0.0),
                "secs": s["secs"],
                # so hive_daemon._touched can tape what this run produced
                "wrote": [MASTER, REPORT]}
    except Exception as e:
        return {"ok": False, "error": "%s: %s" % (type(e).__name__, str(e)[:200])}


def summary_line():
    """Summary line (function)."""
    m = _load_master()
    if not m:
        return "squigly: no census yet"
    return "squigly: %d files, %.2f GB, last censused %s" % (
        m.get("files", 0), m.get("bytes", 0) / 1073741824, m.get("at", "?"))
