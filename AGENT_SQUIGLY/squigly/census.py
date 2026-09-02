r"""census.py — walk every drive and say what is actually there. Deterministic, zero LLM.

Chris 2026-08-17: *"the main reason for innaction is the lack of context and system data... squigly
just lists all files and folders, blocks all windows program folders and has a refreshed master
list with the topological linking and usage so if we need one file it is linked to the program that
uses it like dependencies, so any file lost or moved or added the system knows and so does aegis"*.

THE DIAGNOSIS IS THE DESIGN
    An agent that cannot see the disk cannot act on it. viper_sync knows seven curated paths;
    symbolic.py knows 303 symbols learned from tool observations; master_graph knows the nodes it
    was told about. None of them can answer "where is that file", "what uses it", or "what moved".
    Squigly is the census that makes those answerable, and it is deliberately dumb: a walk, a
    hash, a table. Nothing here infers, so nothing here can be wrong in an interesting way.

WHAT IT REFUSES TO LOOK AT
    Windows and the program directories are blocked outright. Not for safety -- reading is
    harmless -- but for SIGNAL. C:\Windows alone is ~128,000 files that no one will ever move,
    lose, or wonder about, and burying four hundred real project files in that is how an index
    becomes something nobody opens. A census that includes everything tells you nothing.

MOVE DETECTION IS A HASH, NOT A GUESS
    A file that vanishes from one path and appears at another with the same content hash MOVED.
    That is a fact, not a heuristic, and it is the difference between "17 files lost, 17 files
    added" and "you reorganised a folder". Only content that is genuinely gone gets reported as
    lost, which is what makes the report worth reading.
"""
import hashlib
import os
import stat
import time

# --------------------------------------------------------------------------------------------
# BLOCKED — never walked, at any depth
# --------------------------------------------------------------------------------------------
# Matched case-insensitively against each directory NAME as the walk descends, so a blocked name
# anywhere prunes that whole subtree without a path-prefix comparison per file.
BLOCKED_NAMES = {
    # Windows itself
    "windows", "winsxs", "system volume information", "$recycle.bin", "recovery",
    "programdata", "perflogs", "documents and settings", "msocache", "$windows.~bt",
    "$windows.~ws", "onedrivetemp", "intel", "amd", "nvidia",
    # program installs -- Chris: "blocks all windows program folders"
    "program files", "program files (x86)", "common files", "windowsapps",
    # machine-generated: regenerates from source, so tracking it is noise and churn
    "__pycache__", ".git", "node_modules", ".venv", "venv", "env", "site-packages",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox", ".gradle", ".m2",
    "dist-info", "egg-info", ".next", ".nuxt", "target", "obj", "bin_debug",
    # caches that are large, volatile, and meaningless to an index
    "cache", "caches", "temp", "tmp", "logs.old", "crashdumps", "thumbnails",
    # BACKUP COPIES OF THE TREE BEING CENSUSED. vault_staging holds a full copy of everything
    # viper_sync preserves -- 34,000 files that are byte-identical to their originals. Indexing
    # them doubles the census, and worse, every original acquires a same-hash twin, which is the
    # exact signature move detection looks for. A census that indexes its own backups reports a
    # reorganisation every time the backup runs.
    "vault_staging", "g_image", "otg_archive", "recovery", "pyc_ghosts",
    # NOT "archive". Tried and REVERTED 2026-09-02.
    #
    # The reasoning looked sound -- C:\Viper\databases\email\archive holds
    # 84,105 .eml files, and BLOCKED_EXT skips them from the record while the
    # walk still enumerates every one -- so pruning the subtree should have
    # been the real saving. Measured: 245.4s before, 240.7s after, and the file
    # count moved 6,124 -> 6,134. Five seconds.
    #
    # So enumeration was never the cost; hashing the files that REMAIN is. The
    # .eml exclusion is what did the work (about 90,000 files down to 6,100).
    # A generic name like "archive" would prune any directory called that
    # anywhere in the estate, and buying a 2% saving with that risk is a bad
    # trade. Left here as a measured dead end so it is not tried again.
}

# Extensions never recorded: regenerated, or so large the hash cost buys nothing.
#
# .eml ADDED 2026-09-02, and it is the whole reason this census stopped the hive.
#
# Measured from the last completed master.json: 101,733 rows, and 84,105 of them
# -- 83% -- were .eml files under C:\Viper\databases\email\archive. 7.01 GB of
# harvested mail, walked and hashed every six hours for move detection on data
# that is not code and does not move.
#
# The cost was not only time. refresh() loads the PREVIOUS master into
# prev_by_path while building the new rows, so 101k row dicts are held twice,
# plus a dependency graph over them, on a 16 GB box already running ~6 GB of
# services. On 2026-09-01 that spike landed at 579.9s of a 600s deadline; the
# hive's watchdog thread died at that instant -- it had no exception guard, so a
# MemoryError ended it in silence -- and no abort ever came. 69 cells starved
# for seven hours while the sitter reported the hive UP, because the PID was
# live.
#
# Inbound mail belongs to the email pipeline, which has its own index. A code
# census hashing it is answering a question nobody asked, 84,105 times.
BLOCKED_EXT = (".pyc", ".pyo", ".pyd", ".obj", ".o", ".class", ".lock",
               ".swp", ".swo", ".bak~", ".crdownload", ".partial",
               ".eml")

# Above this, record the file but do NOT hash it. Hashing a 4 GB model to notice it moved costs
# more than the answer is worth, and size+mtime already identifies it well enough to spot a move.
HASH_MAX_BYTES = 32 * 1024 * 1024


def is_blocked(dirname):
    """Is this directory name one we refuse to descend into?"""
    return dirname.lower() in BLOCKED_NAMES


def _hash(path, size):
    """SHA256, or None when the file is too big, unreadable, or vanished mid-walk.

    None is a legitimate answer here and callers must handle it. On a live box files are deleted
    between the moment os.walk lists them and the moment we open them; treating that as an error
    would mean the census fails whenever the machine is doing anything, which is always.
    """
    if size > HASH_MAX_BYTES:
        return None
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            while True:
                b = f.read(1 << 20)
                if not b:
                    break
                h.update(b)
        return h.hexdigest()
    except (OSError, ValueError):
        return None


def walk(roots, hash_files=True, follow_links=False):
    """Yield one dict per file. Never raises; unreadable branches are skipped, not fatal.

    Symlinks are not followed by default. A junction pointing back up its own tree turns a census
    into an infinite walk, and Windows has more of those than people expect (every user profile
    has several for backwards compatibility).
    """
    seen_dirs = set()
    for root in roots:
        root = os.path.abspath(root)
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root, topdown=True,
                                                    onerror=lambda e: None,
                                                    followlinks=follow_links):
            dirnames[:] = [d for d in dirnames if not is_blocked(d)]

            # Guard against junction loops even when followlinks is on: a directory whose real
            # path we have already walked is not walked twice.
            try:
                real = os.path.realpath(dirpath)
                if real in seen_dirs:
                    dirnames[:] = []
                    continue
                seen_dirs.add(real)
            except OSError:
                continue

            for fn in filenames:
                if fn.lower().endswith(BLOCKED_EXT):
                    continue
                p = os.path.join(dirpath, fn)
                try:
                    st = os.lstat(p)
                    if stat.S_ISLNK(st.st_mode):
                        continue
                    size = st.st_size
                except OSError:
                    continue
                yield {
                    "path": p,
                    "dir": dirpath,
                    "name": fn,
                    "ext": os.path.splitext(fn)[1].lower(),
                    "size": size,
                    "mtime": int(st.st_mtime),
                    "sha256": _hash(p, size) if hash_files else None,
                }


def census(roots, hash_files=True, progress_every=0, deadline_s=None, prev_by_path=None):
    """Full census as a list plus totals. The one call most callers want.

    TWO THINGS KEEP THIS INSIDE A CELL BUDGET, and they matter because the first full run did not
    finish in 600s twice:

    `prev_by_path` REUSES THE LAST CENSUS'S HASH when size and mtime are unchanged. Hashing is
    essentially the entire cost of a census, and on a fleet where a few hundred files change
    between runs, re-reading forty thousand unchanged ones buys nothing. The fallback is the same
    trade viper_sync makes: same size and mtime within a second is trusted, and the worst case is
    a stale hash on a file edited without moving either, which shows up on the next run that does
    see a difference. Getting that wrong costs a missed move, not a lost file.

    `deadline_s` stops the walk cleanly rather than being killed mid-write. A partial census is
    still a valid census -- it just covers fewer files -- and the caller is told, so it can decide
    whether to diff against it. Silently diffing a partial census against a full one would report
    every unvisited file as LOST, which is the single most alarming and least true thing this
    system could say.
    """
    t0 = time.time()
    rows, total, reused = [], 0, 0
    stopped = False
    for rec in walk(roots, hash_files=False):
        if deadline_s and (time.time() - t0) > deadline_s:
            stopped = True
            break
        if hash_files:
            prev = prev_by_path.get(rec["path"]) if prev_by_path else None
            if (prev and prev.get("sha256")
                    and prev.get("size") == rec["size"]
                    and abs(int(prev.get("mtime", -1)) - rec["mtime"]) <= 1):
                rec["sha256"] = prev["sha256"]
                reused += 1
            else:
                rec["sha256"] = _hash(rec["path"], rec["size"])
        rows.append(rec)
        total += rec["size"]
        if progress_every and len(rows) % progress_every == 0:
            print("  %d files, %.1f GB, %.0fs (%d hashes reused)"
                  % (len(rows), total / 1073741824, time.time() - t0, reused), flush=True)
    return {"files": len(rows), "bytes": total, "secs": round(time.time() - t0, 1),
            "roots": list(roots), "rows": rows,
            "hashes_reused": reused, "partial": stopped}
