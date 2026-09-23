r"""deps.py — what uses what. The topological half of the census.

Chris 2026-08-17: *"if we need one file it is linked to the program that uses it like
dependencies, so any file lost or moved or added the system knows"*.

A list of files tells you what exists. It does not tell you what BREAKS when one goes missing, and
that is the question actually being asked. A file with forty dependents is not the same object as a
file with none, even when they are the same size and the same age.

READ, NEVER EXECUTE
    Imports are resolved by parsing, not by importing. Importing a module to discover its imports
    runs it -- module-level code, side effects, network calls, whatever the author put at the top --
    across every file on the disk. An indexer that executes what it indexes is a remote code
    execution engine with good intentions. ast.parse never runs anything.

WHAT IT FINDS, AND WHAT IT ADMITS IT MISSES
    Python imports resolved to real paths, plus literal path strings appearing in any text file
    (configs naming scripts, batch files calling programs, scheduled tasks). Dynamic imports,
    importlib by computed name, and paths built by concatenation are NOT found, and pretending
    otherwise would be worse than the gap -- an "orphan" list that is quietly wrong is more
    dangerous than one that says which cases it cannot see, because someone will eventually delete
    something from it.
"""
import ast
import os
import re
import threading
import time

# A path-looking literal: quoted, with a separator and an extension.
_PATH_LIT = re.compile(r"""["']([A-Za-z]:\\[^"']{3,200}|\.{0,2}[/\\][^"']{3,200})["']""")
_TEXT_EXT = (".py", ".ps1", ".bat", ".cmd", ".sh", ".json", ".yaml", ".yml", ".toml",
             ".ini", ".cfg", ".xml", ".md", ".txt")


def python_imports(path):
    """Module names imported by a Python file. Parses; never imports. Returns [] on a syntax error.

    A file that does not parse is a real condition on a live disk -- half-saved, Python 2, a
    template with placeholders -- and it must not stop a census of forty thousand others.
    """
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            tree = ast.parse(f.read())
    except (OSError, SyntaxError, ValueError, RecursionError):
        return []
    mods = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:            # relative import: resolve against the package directory
                base = os.path.basename(os.path.dirname(path))
                mods.append("%s.%s" % (base, node.module) if node.module else base)
            elif node.module:
                mods.append(node.module)
    return mods


def path_literals(path, ext):
    """Literal filesystem paths mentioned inside a text file.

    This is how the non-Python half of a fleet is wired together: a scheduled task naming a .ps1,
    a config pointing at a database, a batch file launching a jar. None of that is visible to an
    import graph, and all of it breaks the same way when a file moves.
    """
    if ext not in _TEXT_EXT:
        return []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read(200_000)
    except OSError:
        return []
    return [m.group(1) for m in _PATH_LIT.finditer(text)]


# PowerShell and batch wire this fleet together far more than imports do: scheduled tasks launch
# .ps1, .bat files call java and python with a script path, wrappers dot-source helpers. None of
# that is an import and all of it breaks identically when a file moves.
_PS_REFS = (
    re.compile(r"^\s*\.\s+([^\s;|]+\.ps1)", re.M | re.I),            # dot-sourcing
    re.compile(r"Import-Module\s+([^\s;|]+)", re.I),
    re.compile(r"&\s*[\"']?([^\s\"';|]+\.(?:ps1|exe|bat|cmd|jar|py))", re.I),
    re.compile(r"-File\s+[\"']?([^\s\"';|]+)", re.I),
    re.compile(r"Start-Process\s+[\"']?([^\s\"';|]+)", re.I),
    re.compile(r"(?:python|pythonw|java|node)\s+[\"']?([^\s\"';|]+\.(?:py|jar|js))", re.I),
)
_BAT_REFS = (
    re.compile(r"^\s*call\s+[\"']?([^\s\"'&|]+)", re.M | re.I),
    re.compile(r"^\s*start\s+(?:[\"'][^\"']*[\"']\s+)?[\"']?([^\s\"'&|]+)", re.M | re.I),
    # REWRITTEN 2026-09-23. The nested-quantifier middle section -- (?:[^\s]*\s+)*? -- is a
    # textbook ReDoS: with no re.M, \s matches newlines too, so on a non-matching line (no
    # trailing .py/.jar/.ps1/.bat/.cmd token after the launcher keyword) the engine can try
    # exponentially many ways to partition the REST OF THE FILE into word+space groups before
    # giving up. Measured: a single 381-char PowerShell one-liner in a real 139-line .bat file
    # (AEGIS_Launch.bat) made this pattern hang for 11+ HOURS, burning ~93.5% CPU continuously --
    # a single re.finditer() call does not yield the GIL mid-match, so it also starved
    # hive_daemon's watchdog thread in the same process, defeating even its own abort mechanism.
    # `.*?` is a single simple lazy quantifier (no internal ambiguity to backtrack over) and,
    # since `.` does not match `\n` by default, it naturally stays confined to one line the same
    # way the old pattern was clearly intended to. Confirmed: 0.0004s on the pathological input
    # that used to hang, same matches on every legitimate case in this file's own test fixtures.
    re.compile(r"""(?:python|pythonw|java|javaw|powershell|pwsh)\b.*?["']?([^\s"'&|]+\.(?:py|jar|ps1|bat|cmd))""", re.I),
)


def script_refs(path, ext):
    """Files a PowerShell or batch script invokes or dot-sources.

    Kept separate from path_literals because these are INVOCATIONS, not mentions. A quoted path in
    a config might be data; `call foo.bat` is a hard dependency, and the difference matters when
    the question is what breaks.
    """
    if ext not in (".ps1", ".psm1", ".bat", ".cmd"):
        return []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read(200_000)
    except OSError:
        return []
    pats = _PS_REFS if ext in (".ps1", ".psm1") else _BAT_REFS
    me = os.path.basename(path).lower()
    out = []
    for pat in pats:
        for m in pat.finditer(text):
            ref = m.group(1).strip().strip("'\"")
            if not ref:
                continue
            # A PARAMETER IS NOT A FILE. `Start-Process -FilePath x` and `... -ErrorAction Stop`
            # both put a flag where the regex expected a target, and the first version happily
            # recorded "-FilePath" and "-ErrorAction" as dependencies. A graph with invented edges
            # is worse than a sparse one: it makes orphan detection wrong in the direction that
            # gets files deleted.
            if ref.startswith("-"):
                continue
            # %VAR% and $env: expansions cannot be resolved statically; skip rather than guess
            if "%" in ref or "$" in ref:
                continue
            # DOCUMENTATION IS NOT A DEPENDENCY. Usage strings are full of <path>, path\to\module.py
            # and stray backticks, and the first version recorded all of them. A help message is
            # the one place a script names files it does NOT use.
            if any(ch in ref for ch in "<>`*?|"):
                continue
            if ref.lower().startswith(("path\\to", "path/to")):
                continue
            # Must actually look like something runnable or importable, or it is a regex fragment
            # ("match"), a cmdlet noun, or prose that happened to sit after a keyword.
            if os.path.splitext(ref)[1].lower() not in _RUNNABLE_EXT:
                continue
            # A script naming ITSELF -- a re-launch guard, a usage line, a comment -- depends on
            # nothing. Compared by basename: the ref is usually relative, and resolving it against
            # the current working directory (which is wherever the census was started, not the
            # script's own folder) made every self-reference look like a different file.
            if os.path.basename(ref).lower() == me:
                continue
            out.append(ref)
    return sorted(set(out))


_RUNNABLE_EXT = {".ps1", ".psm1", ".bat", ".cmd", ".py", ".pyw", ".jar", ".exe", ".js", ".sh"}


# How long ANY ONE file gets before it is abandoned and skipped. Found 2026-09-23: the OUTER
# deadline_s below is only checked BETWEEN files, so one file whose open() stalls -- a bad USB
# connection, an antivirus scan delay, a stale network path -- can block the whole graph build
# past deadline_s indefinitely, exactly the same shape as the graph-vs-refresh gap the comment
# below already documents, one level deeper. This wedged hive_daemon's squigly cell three times
# in one session (measured: 93.5% CPU sustained for 11+ hours with the deadline_s=600 passed in
# from unify.tick() never once taking effect).
PER_FILE_TIMEOUT_S = float(os.environ.get("SQUIGLY_PER_FILE_TIMEOUT_S", "15"))


def _scan_row(r, by_module, by_name):
    """Everything build_graph does for ONE row. Split out so it can be time-boxed -- see
    _scan_row_bounded. Returns (used, unresolved_here)."""
    p, ext = r["path"], r.get("ext", "")
    used = []
    unresolved_here = {}

    for mod in python_imports(p) if ext == ".py" else []:
        hit = by_module.get(mod) or by_module.get(mod.split(".")[-1])
        if hit:
            used.extend(h for h in hit if h != p)
        else:
            # stdlib and site-packages land here; counted, not listed, so the number stays
            # meaningful without the list becoming a dump of every third-party import
            unresolved_here[mod] = unresolved_here.get(mod, 0) + 1

    # invocations from PowerShell/batch resolve the same way as literals, but they are hard
    # dependencies rather than mentions
    for ref in script_refs(p, ext):
        hit = by_name.get(os.path.basename(ref).lower())
        if hit:
            used.extend(h for h in hit if h != p)
        elif os.path.isabs(ref) and os.path.isfile(ref):
            used.append(os.path.normpath(ref))

    for lit in path_literals(p, ext):
        cand = os.path.normpath(lit)
        if os.path.isabs(cand):
            if os.path.isfile(cand):
                used.append(cand)
            continue
        hit = by_name.get(os.path.basename(cand).lower())
        if hit:
            used.extend(h for h in hit if h != p)

    return used, unresolved_here


def _scan_row_bounded(r, by_module, by_name, timeout):
    """Runs _scan_row in a background thread and gives up after `timeout`.

    Python cannot cancel a running thread -- the same limitation hive_daemon._call_with_deadline
    already documents and accepts. The abandoned thread keeps running (and, if it really is stuck
    on a hung syscall, keeps costing nothing further since it is blocked, not spinning), but the
    CALLER -- this loop -- is never blocked past `timeout` for any single file again.

    Returns None on timeout (caller records and skips), else (used, unresolved_here). A real
    exception on one file is swallowed here exactly as it always was inline: one bad file must
    not stop the graph for the other 7000.
    """
    box = {}

    def _work():
        try:
            box["value"] = _scan_row(r, by_module, by_name)
        except BaseException as e:                # noqa: BLE001 -- one file, never fatal
            box["exc"] = e

    t = threading.Thread(target=_work, daemon=True, name="squigly-scan")
    t.start()
    t.join(timeout)
    if t.is_alive():
        return None
    return box.get("value", ([], {}))


def build_graph(rows, roots, deadline_s=None):
    """Edges from every file to the files it uses. Returns (edges, index, unresolved).

    `edges` is {user_path: [used_path, ...]}. The reverse -- who uses X -- is what answers "what
    breaks if this goes", and dependents() computes it from the same structure rather than storing
    it twice and letting the two disagree.
    """
    by_module, by_name = {}, {}
    for r in rows:
        p = r["path"]
        stem = os.path.splitext(r["name"])[0]
        if r.get("ext") == ".py":
            by_module.setdefault(stem, []).append(p)
            pkg = os.path.basename(os.path.dirname(p))
            by_module.setdefault("%s.%s" % (pkg, stem), []).append(p)
        by_name.setdefault(r["name"].lower(), []).append(p)

    edges, unresolved = {}, {}
    t0 = time.time()
    timed_out = []
    for r in rows:
        # Bounded. Parsing every Python file and regexing every text file across a full tree is
        # the single most expensive thing squigly does -- measured at six CPU-hours unbounded --
        # and a partial graph is still useful, while a six-hour one is not. This check alone is
        # not sufficient (see PER_FILE_TIMEOUT_S above); both bounds apply together now.
        if deadline_s and (time.time() - t0) > deadline_s:
            unresolved["_stopped_early"] = len(rows)
            break
        result = _scan_row_bounded(r, by_module, by_name, PER_FILE_TIMEOUT_S)
        if result is None:
            timed_out.append(r["path"])
            continue
        used, unresolved_here = result
        for mod, n in unresolved_here.items():
            unresolved[mod] = unresolved.get(mod, 0) + n
        if used:
            edges[r["path"]] = sorted(set(used))
    if timed_out:
        unresolved["_timed_out_files"] = len(timed_out)
    return edges, by_name, unresolved


def dependents(edges):
    """Reverse the graph: who uses X. The direction that answers 'what breaks if this goes'."""
    rev = {}
    for user, used in edges.items():
        for u in used:
            rev.setdefault(u, []).append(user)
    return {k: sorted(set(v)) for k, v in rev.items()}


def orphans(rows, edges, rev):
    """Files nothing references. A candidate list for review, NEVER a delete list.

    Everything in the "what it misses" note above lands here as a false positive: entry points
    nobody imports, files loaded by computed name, data read by a glob. That is exactly why this
    returns candidates for a human to look at and why nothing in Squigly deletes anything.
    """
    used = set(rev)
    out = []
    for r in rows:
        p = r["path"]
        if p in used or p in edges:
            continue
        if r["name"].lower() in ("readme.md", "__init__.py", "license", ".gitignore"):
            continue
        out.append(p)
    return sorted(out)


def _selftest():
    """OFFLINE, no real filesystem paths. Proves the 2026-09-23 fixes:
      1. the ReDoS in the old _BAT_REFS launcher-keyword pattern is gone (bounded time, not just
         "eventually correct" -- a slow-but-technically-terminating regex would still wedge a hive);
      2. legitimate call/start/launcher references in .bat files still resolve;
      3. _scan_row_bounded actually returns None (not hangs) when the wrapped work does not return.
    """
    import tempfile
    fails = []

    # 1. THE EXACT SHAPE THAT WEDGED THE HIVE for 11+ hours (AEGIS_Launch.bat, 2026-09-23): a
    # launcher keyword followed by a long line with no trailing .py/.jar/.ps1/.bat/.cmd token.
    pathological = (r'powershell -Command "$log = Get-Content C:\Users\x\tunnel.log -Tail 50 '
                    r"| Select-String 'https://.*\.trycloudflare\.com'; if ($log) { $url = "
                    r"$log.Matches[0].Value; Write-Output $url; $url | Out-File -Encoding ascii "
                    "C:\\Users\\x\\tunnel_url.txt } else { Write-Output 'no match found' }\"\n")
    d = tempfile.mkdtemp(prefix="deps_selftest_")
    import os as _os
    bat = _os.path.join(d, "pathological.bat")
    with open(bat, "w", encoding="utf-8") as f:
        f.write(pathological * 3)      # 3x: the old pattern's cost grows with content, not just once
    t0 = time.time()
    refs = script_refs(bat, ".bat")
    dt = time.time() - t0
    if dt > 2.0:
        fails.append("ReDoS regression: script_refs took %.2fs on the pathological shape (must be <2s)" % dt)

    # 2. Real references must still resolve.
    real = _os.path.join(d, "real.bat")
    with open(real, "w", encoding="utf-8") as f:
        f.write("call helper.bat\n" + r"python C:\tools\build.py --release" + "\nstart notepad.exe\n")
    refs2 = script_refs(real, ".bat")
    if "helper.bat" not in refs2:
        fails.append("lost the 'call helper.bat' reference: %r" % refs2)
    if not any(r.endswith("build.py") for r in refs2):
        fails.append("lost the 'python ... build.py' reference: %r" % refs2)

    # 3. The per-file bound must actually bound a function that never returns.
    def _never_returns(*_a, **_kw):
        while True:
            time.sleep(0.05)

    real_scan_row = globals()["_scan_row"]
    globals()["_scan_row"] = _never_returns
    try:
        t0 = time.time()
        r = _scan_row_bounded({"path": "x"}, {}, {}, 0.5)
        dt = time.time() - t0
        if r is not None:
            fails.append("_scan_row_bounded did not report a timeout on work that never returns")
        if dt > 2.0:
            fails.append("_scan_row_bounded itself blocked for %.2fs against a 0.5s timeout" % dt)
    finally:
        globals()["_scan_row"] = real_scan_row

    for f in fails:
        print("FAIL:", f)
    print("deps selftest:", "ok" if not fails else "FAILED")
    return 0 if not fails else 1


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
