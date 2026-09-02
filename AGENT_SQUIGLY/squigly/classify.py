r"""classify.py — say what a file is FOR, without asking a model.

Chris asked the index to "say what they are for". That could be an LLM captioning 400,000 files,
which would be slow, expensive, non-reproducible, and wrong in ways nobody could audit. It does not
need to be. Purpose is overwhelmingly determined by three things a machine can read directly:

    WHERE it is      tests/ means test, .github/workflows means CI, docs/ means documentation
    WHAT it is       .py is source, .sqlite is data, .jar is a build artefact
    WHAT IT SAYS     the first docstring or heading, which the author already wrote for a human

The third is the important one and the cheapest: every module in this fleet opens with a docstring
explaining itself, so the best description of a file is nearly always sitting in its first twenty
lines, written by the person who knew. Reading it is not inference, it is quotation.

CONFIDENCE IS REPORTED, NOT HIDDEN
    Every classification carries how it was reached -- `docstring`, `path`, `extension`, or
    `unknown`. A caption from the author's own words and a guess from a file extension are not the
    same claim, and an index that presents them identically teaches you to trust neither.
"""
import os
import re

# --------------------------------------------------------------------------------------------
# ROLE by directory. Checked against every path component, deepest match wins.
# --------------------------------------------------------------------------------------------
DIR_ROLE = {
    "tests": "tests", "test": "tests", "spec": "tests",
    "docs": "documentation", "doc": "documentation", "notes": "notes",
    "scripts": "operational script", "bin": "executable",
    "src": "source", "lib": "library", "app": "application",
    "config": "configuration", "conf": "configuration", "settings": "configuration",
    "databases": "database", "db": "database", "data": "data",
    "models": "model weights", "checkpoints": "model weights",
    "backups": "backup", "archive": "archive", "_archive": "archive",
    "migrations": "schema migration", "schema": "schema",
    "static": "web asset", "assets": "web asset", "public": "web asset",
    "templates": "template", "workflows": "CI pipeline",
    "logs": "log", "state": "runtime state", "cache": "cache",
    "projects": "project", "vendor": "third-party code",
}

# --------------------------------------------------------------------------------------------
# KIND by extension.
# --------------------------------------------------------------------------------------------
EXT_KIND = {
    ".py": "Python source", ".pyw": "Python source", ".ipynb": "notebook",
    ".js": "JavaScript source", ".ts": "TypeScript source", ".jsx": "React source",
    ".tsx": "React source", ".java": "Java source", ".kt": "Kotlin source",
    ".c": "C source", ".h": "C header", ".cpp": "C++ source", ".rs": "Rust source",
    ".go": "Go source", ".rb": "Ruby source", ".php": "PHP source", ".cs": "C# source",
    ".ps1": "PowerShell script", ".psm1": "PowerShell module", ".bat": "batch script",
    ".cmd": "batch script", ".sh": "shell script",
    ".sql": "SQL", ".db": "SQLite database", ".sqlite": "SQLite database",
    ".sqlite3": "SQLite database", ".jsonl": "JSON lines data", ".json": "JSON data",
    ".yaml": "YAML config", ".yml": "YAML config", ".toml": "TOML config",
    ".ini": "INI config", ".cfg": "config", ".env": "environment file",
    ".md": "Markdown document", ".rst": "reStructuredText", ".txt": "text",
    ".pdf": "PDF document", ".csv": "CSV data", ".tsv": "TSV data",
    ".html": "HTML", ".htm": "HTML", ".css": "stylesheet",
    ".jar": "Java build artefact", ".exe": "executable", ".dll": "library binary",
    ".gguf": "model weights", ".safetensors": "model weights", ".pt": "model weights",
    ".onnx": "model weights", ".bin": "binary",
    ".png": "image", ".jpg": "image", ".jpeg": "image", ".gif": "image", ".svg": "vector image",
    ".zip": "archive", ".gz": "archive", ".tar": "archive", ".7z": "archive",
    ".log": "log file", ".img": "disk image",
}

# Files whose NAME alone is definitive.
NAME_PURPOSE = {
    "readme.md": "project overview",
    "readme": "project overview",
    "license": "licence",
    "license.txt": "licence",
    "requirements.txt": "Python dependency list",
    "pyproject.toml": "Python project definition",
    "setup.py": "Python package setup",
    "package.json": "Node project definition",
    "dockerfile": "container build definition",
    "makefile": "build definition",
    ".gitignore": "git exclusion list",
    ".gitattributes": "git attributes",
    "conftest.py": "pytest fixtures",
    "__init__.py": "package marker",
    "claude.md": "agent instructions",
    "memory.md": "agent memory index",
}

_PY_DOC = re.compile(r'^\s*(?:#[^\n]*\n|\s*\n)*\s*[ru]?["\']{3}(.*?)["\']{3}', re.S)
_MD_H1 = re.compile(r"^\s*#\s+(.+?)\s*$", re.M)
_COMMENT = re.compile(r"^\s*(?:#|//|--|;)\s?(.+)$")


def _first_sentence(text, limit=160):
    """First meaningful line of a docstring or heading, trimmed to one idea."""
    for raw in (text or "").strip().splitlines():
        line = raw.strip()
        if not line:
            continue
        # module docstrings here conventionally open "name.py — what it is"
        for dash in (" — ", " -- ", " – "):
            if dash in line:
                line = line.split(dash, 1)[1].strip()
                break
        return line[:limit]
    return ""


def describe(path, ext=None, read_head=True):
    """What is this file for? Returns (purpose, source-of-that-answer).

    Reads at most 4 KB. The answer sought is a docstring or an H1, both of which live at the top
    by definition, and reading whole files across a 400,000-file census would dominate the runtime
    for information that is not in the tail.
    """
    ext = (ext or os.path.splitext(path)[1]).lower()
    name = os.path.basename(path).lower()

    if name in NAME_PURPOSE:
        return NAME_PURPOSE[name], "name"

    if read_head and ext in (".py", ".pyw", ".md", ".rst", ".ps1", ".sh", ".sql", ".js", ".ts"):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                head = f.read(4096)
        except OSError:
            head = ""
        if head:
            if ext in (".py", ".pyw"):
                m = _PY_DOC.match(head)
                if m:
                    s = _first_sentence(m.group(1))
                    if s:
                        return s, "docstring"
            if ext in (".md", ".rst"):
                m = _MD_H1.search(head)
                if m:
                    return m.group(1)[:160], "heading"
            for line in head.splitlines()[:6]:
                m = _COMMENT.match(line)
                if m and len(m.group(1).strip()) > 12:
                    return m.group(1).strip()[:160], "comment"

    parts = [p.lower() for p in os.path.normpath(path).split(os.sep)]
    for comp in reversed(parts[:-1]):
        if comp in DIR_ROLE:
            kind = EXT_KIND.get(ext, "file")
            return "%s (%s)" % (DIR_ROLE[comp], kind), "path"

    if ext in EXT_KIND:
        return EXT_KIND[ext], "extension"
    return "unclassified", "unknown"


def classify(rec):
    """Enrich one census row with purpose, kind and role. Pure function of the row plus the file."""
    purpose, how = describe(rec["path"], rec.get("ext"))
    parts = [p.lower() for p in os.path.normpath(rec["path"]).split(os.sep)]
    role = next((DIR_ROLE[c] for c in reversed(parts[:-1]) if c in DIR_ROLE), "")
    return dict(rec, purpose=purpose, purpose_from=how,
                kind=EXT_KIND.get(rec.get("ext", ""), "file"), role=role)
