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
    re.compile(r"(?:python|pythonw|java|javaw|powershell|pwsh)\s+"
               r"(?:[^\s]*\s+)*?[\"']?([^\s\"'&|]+\.(?:py|jar|ps1|bat|cmd))", re.I),
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
    import time as _time
    _t0 = _time.time()
    for r in rows:
        # Bounded. Parsing every Python file and regexing every text file across a full tree is
        # the single most expensive thing squigly does -- measured at six CPU-hours unbounded --
        # and a partial graph is still useful, while a six-hour one is not.
        if deadline_s and (_time.time() - _t0) > deadline_s:
            unresolved["_stopped_early"] = len(rows)
            break
        p, ext = r["path"], r.get("ext", "")
        used = []

        for mod in python_imports(p) if ext == ".py" else []:
            hit = by_module.get(mod) or by_module.get(mod.split(".")[-1])
            if hit:
                used.extend(h for h in hit if h != p)
            else:
                # stdlib and site-packages land here; counted, not listed, so the number stays
                # meaningful without the list becoming a dump of every third-party import
                unresolved[mod] = unresolved.get(mod, 0) + 1

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

        if used:
            edges[p] = sorted(set(used))
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
