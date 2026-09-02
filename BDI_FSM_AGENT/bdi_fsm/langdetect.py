"""LANGDETECT — deterministic programming-language detection (zero LLM).

Leaf module (no internal deps) so the NMCT vault, NMTD recorder, and LangDB
can all tag entries by language without circular imports. Detection order:
filename extension -> slot-name hint -> code-content regex. Falls back to
"unknown" — an explicit, honest signal, never a guess.
"""
import re
from typing import Dict, List, Tuple

EXT_LANG: Dict[str, str] = {
    ".py": "python", ".pyw": "python",
    ".js": "javascript", ".mjs": "javascript", ".ts": "typescript",
    ".java": "java", ".kt": "kotlin",
    ".c": "c", ".h": "c", ".cpp": "cpp", ".cc": "cpp", ".hpp": "cpp",
    ".rs": "rust", ".go": "go",
    ".html": "html", ".htm": "html", ".css": "css",
    ".sh": "bash", ".zsh": "zsh", ".fish": "fish",
    ".sql": "sql", ".rb": "ruby", ".php": "php", ".swift": "swift",
    ".md": "markdown", ".json": "json", ".yaml": "yaml", ".yml": "yaml",
    ".toml": "toml", ".lua": "lua",
    # POWERSHELL AND BATCH. Absent until 2026-09-01, which is why the NMCT vault
    # held 849 python files and zero of the 141 .ps1/.bat/.cmd files this system
    # is actually driven from. Chris: "I built everything around the batch
    # powershell and to be used with it. even parts of it for our servers ...
    # again the nmct database would have shown this as well." It could not: the
    # module whose whole job is naming the language did not know these two.
    ".ps1": "powershell", ".psm1": "powershell", ".psd1": "powershell",
    ".bat": "batch", ".cmd": "batch",
}

CODE_HINTS: List[Tuple[str, "re.Pattern"]] = [
    # PowerShell before python: `function Foo {` and `param(` are unambiguous,
    # and a .ps1 with a `$var = ...` line would otherwise fall through to the
    # generic hints and come back "unknown".
    ("powershell", re.compile(
        r"^\s*function\s+[\w-]+\s*\{|^\s*param\s*\(|\[CmdletBinding\(\)\]|"
        r"\$PSScriptRoot|Write-Host|\$LASTEXITCODE", re.M | re.I)),
    ("batch", re.compile(
        r"^\s*@echo\s+off|^\s*setlocal|^\s*goto\s+:?\w+|%~dp0", re.M | re.I)),
    ("python", re.compile(r"^\s*(def|class)\s+\w+|^\s*(import|from)\s+\w+", re.M)),
    ("rust", re.compile(r"\bfn\s+\w+\s*\(|impl\s+\w+|\blet\s+mut\b", re.M)),
    ("go", re.compile(r"\bfunc\s+\w+\s*\(|\bpackage\s+\w+\b", re.M)),
    ("java", re.compile(r"\bpublic\s+(static\s+)?(class|void|int|String)\b", re.M)),
    ("cpp", re.compile(r"#include\s*[<\"]|\bstd::|->|\bint\s+main\s*\(", re.M)),
    ("c", re.compile(r"#include\s*<.*\.h>|printf\(", re.M)),
    ("typescript", re.compile(r"\binterface\s+\w+|:\s*(string|number|boolean)\b", re.M)),
    ("javascript", re.compile(r"\b(function|const|let|var)\b|=>|console\.log", re.M)),
    ("bash", re.compile(r"^#!/(bin/)?(ba|z)?sh|^\s*(echo|cd|ls|grep|set -e)", re.M)),
    ("html", re.compile(r"<!DOCTYPE html|<html|</?[a-z]+>", re.I)),
    ("sql", re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE|CREATE TABLE)\b", re.I)),
]


def detect_language(code: str = "", filename: str = "", slot: str = "") -> str:
    """Deterministic language tag from the strongest available signal."""
    # 1. filename extension
    if filename:
        low = filename.lower()
        for ext, lang in EXT_LANG.items():
            if low.endswith(ext):
                return lang
    # 2. slot-name hint. EXTENSION FIRST, then the language name as a WHOLE WORD.
    #
    # This read `for lang, _ in CODE_HINTS: if lang in low` -- a substring test
    # against the language NAME. One of those names is "c", so any slot
    # containing the letter c matched it: "nmct-guard.ps1" was detected as C,
    # and so was every other NMCT file on this box. The extension was checked
    # only afterwards, so it never got the chance to be right.
    #
    # Fifth sighting of this exact bug in one day -- the :8765 keyword matcher
    # ("hi" inside "this"), talon.extract_directive, the NMCT capability regex
    # ("write up" inside "Write upsert_auditor.py"), the duplicate-name probe,
    # and now this. Substring matching a short token is never safe.
    if slot:
        low = slot.lower()
        for ext, lang in EXT_LANG.items():
            if low.endswith(ext):
                return lang
        for lang, _ in CODE_HINTS:
            if re.search(r"(?:^|[^a-z])%s(?:[^a-z]|$)" % re.escape(lang), low):
                return lang
        for ext, lang in EXT_LANG.items():
            bare = ext.lstrip(".")
            if re.search(r"(?:^|[^a-z0-9])%s(?:[^a-z0-9]|$)" % re.escape(bare), low):
                return lang
    # 3. code-content regex
    if code:
        for lang, pat in CODE_HINTS:
            if pat.search(code):
                return lang
    return "unknown"
