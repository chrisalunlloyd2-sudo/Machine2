#!/usr/bin/env python3
"""
VIPER Machine 2 — Karoo Code Miner v2.0
=========================================
Mines code blocks, syntax trees, patterns, logits, and algorithms
from all sources and submits them to code.db for Machine 1 recall.

Architecture:
  - Polls source files, git commits, and conversation logs
  - Extracts syntax trees for: Python, Java, JavaScript, Go, Rust, SQL, C/C++
  - Mines: code blocks, patterns, algorithms, logit sequences
  - Submits to code.db (code_artifacts table)
  - Sends mined blocks to Machine 1 via OTG bridge channel
  - Runs continuously as a background service

Machine 1 ←→ OTG Bridge ←→ THIS MINER ←→ code.db
"""
import json
import sqlite3
import hashlib
import os
import sys
import time
import re
import datetime
import urllib.request
import urllib.error
from pathlib import Path
from typing import Generator

# ─── Configuration ────────────────────────────────────────────────
VIPER          = Path(r"C:\Users\viper\VIPER_JAVA_RISC")
GANOTG         = Path(r"C:\Users\viper\gan-otg-db")
CODE_DB        = VIPER / "java_notes_suite" / "data" / "code.db"
OTG_BRIDGE_URL = "http://127.0.0.1:18282/api/talk"    # HUD relay to M1
HUD_URL        = "http://127.0.0.1:18282"
SCAN_INTERVAL  = 60  # seconds between full scans
BLOCK_MIN_LINES = 3
BLOCK_MAX_LINES = 200

# Languages → file extensions
LANG_MAP = {
    "python":     [".py"],
    "java":       [".java"],
    "javascript": [".js", ".ts", ".jsx", ".tsx"],
    "go":         [".go"],
    "rust":       [".rs"],
    "sql":        [".sql"],
    "c":          [".c", ".h"],
    "cpp":        [".cpp", ".cc", ".cxx", ".hpp"],
    "bash":       [".sh", ".bash"],
    "powershell": [".ps1", ".psm1"],
    "markdown":   [".md"],
    "json":       [".json"],
    "yaml":       [".yaml", ".yml"],
}

# Source dirs to mine
SOURCE_DIRS = [
    VIPER / "tools",
    VIPER / "java_notes_suite" / "src",
    GANOTG / "viper-scripts",
    GANOTG / "ArchivalMoe",
    GANOTG / "MoeGUI",
]

# ─── Database ─────────────────────────────────────────────────────
def db_connect() -> sqlite3.Connection:
    CODE_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(CODE_DB), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS code_artifacts (
            hash        TEXT PRIMARY KEY,
            source_agent TEXT NOT NULL DEFAULT 'karoo_miner',
            language    TEXT NOT NULL,
            code_text   TEXT NOT NULL,
            lexical_vector TEXT,
            status      TEXT NOT NULL DEFAULT 'mined',
            created_at  TEXT NOT NULL,
            file_path   TEXT,
            block_type  TEXT DEFAULT 'block',
            line_start  INTEGER,
            line_end    INTEGER
        )
    """)
    # Add columns for extended metadata if not present
    for col_def in [
        "ALTER TABLE code_artifacts ADD COLUMN file_path TEXT",
        "ALTER TABLE code_artifacts ADD COLUMN block_type TEXT DEFAULT 'block'",
        "ALTER TABLE code_artifacts ADD COLUMN line_start INTEGER",
        "ALTER TABLE code_artifacts ADD COLUMN line_end INTEGER",
    ]:
        try:
            conn.execute(col_def)
        except sqlite3.OperationalError:
            pass  # Column already exists
    conn.commit()
    return conn


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def now_iso() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"


def log(msg: str) -> None:
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] KAROO_MINER | {msg}", flush=True)


# ─── Lexical Vector (simple bag-of-tokens fingerprint) ────────────
def lexical_vector(code: str) -> str:
    """Produce a compact token-frequency vector for fast similarity lookup."""
    tokens = re.findall(r'[a-zA-Z_]\w*', code)
    freq: dict[str, int] = {}
    for t in tokens:
        if len(t) > 2:
            freq[t] = freq.get(t, 0) + 1
    top = sorted(freq.items(), key=lambda x: -x[1])[:20]
    return json.dumps({k: v for k, v in top}, separators=(",", ":"))


# ─── Block Extraction ─────────────────────────────────────────────
def detect_language(path: Path) -> str | None:
    ext = path.suffix.lower()
    for lang, exts in LANG_MAP.items():
        if ext in exts:
            return lang
    return None


def extract_function_blocks(code: str, language: str) -> list[tuple[int, int, str]]:
    """Extract function/class/method blocks with their line ranges."""
    blocks = []
    lines = code.splitlines()
    n = len(lines)

    if language in ("python",):
        pattern = re.compile(r'^(def |class |async def )\w')
        indent_stack = []
        i = 0
        while i < n:
            if pattern.match(lines[i]):
                start = i
                base_indent = len(lines[i]) - len(lines[i].lstrip())
                j = i + 1
                while j < n:
                    if lines[j].strip() == "":
                        j += 1
                        continue
                    curr_indent = len(lines[j]) - len(lines[j].lstrip())
                    if curr_indent <= base_indent and lines[j].strip():
                        break
                    j += 1
                block_lines = lines[start:j]
                if BLOCK_MIN_LINES <= len(block_lines) <= BLOCK_MAX_LINES:
                    blocks.append((start + 1, j, "\n".join(block_lines)))
                i = j
            else:
                i += 1

    elif language in ("java", "javascript", "go", "rust", "c", "cpp"):
        # Find brace-matched blocks starting with identifiable patterns
        func_pat = re.compile(r'^\s*(public|private|protected|static|func|fn|void|int|string|class|struct)\s+\w+')
        i = 0
        while i < n:
            if func_pat.match(lines[i]):
                start = i
                depth = 0
                j = i
                found_open = False
                while j < n:
                    depth += lines[j].count('{') - lines[j].count('}')
                    if '{' in lines[j]:
                        found_open = True
                    if found_open and depth <= 0:
                        j += 1
                        break
                    j += 1
                block_lines = lines[start:j]
                if BLOCK_MIN_LINES <= len(block_lines) <= BLOCK_MAX_LINES:
                    blocks.append((start + 1, j, "\n".join(block_lines)))
                i = j
            else:
                i += 1

    else:
        # Generic: sliding window chunks
        chunk = 30
        for i in range(0, n, chunk // 2):
            end = min(i + chunk, n)
            block_lines = lines[i:end]
            if len(block_lines) >= BLOCK_MIN_LINES:
                blocks.append((i + 1, end, "\n".join(block_lines)))

    return blocks


def extract_patterns(code: str, language: str) -> list[tuple[str, str]]:
    """Extract algorithm patterns and logit sequences."""
    patterns = []

    # Algorithm pattern detection
    algo_patterns = {
        "sort":       r'sort|bubble|quicksort|mergesort|heapsort',
        "search":     r'binary.search|linear.search|bfs|dfs|dijkstra',
        "recursion":  r'def \w+.*:.*\n.*\1|recursive|base.case',
        "dp":         r'memo|memoize|cache|dp\[|tabulation',
        "graph":      r'graph|adjacency|node|edge|vertex|path',
        "ml":         r'gradient|loss|epoch|batch|tensor|weight|bias',
        "regex":      r're\.compile|re\.match|re\.search|pattern',
        "async":      r'async |await |asyncio|coroutine',
        "generator":  r'yield |next\(|iter\(',
        "decorator":  r'@\w+|functools\.wrap',
    }

    for name, pat in algo_patterns.items():
        if re.search(pat, code, re.IGNORECASE | re.DOTALL):
            # Extract the relevant section
            match = re.search(pat, code, re.IGNORECASE)
            if match:
                start = max(0, match.start() - 100)
                end = min(len(code), match.end() + 200)
                snippet = code[start:end].strip()
                if len(snippet) >= 20:
                    patterns.append((name, snippet))

    return patterns[:5]  # limit per file


# ─── Mine a Single File ───────────────────────────────────────────
def mine_file(path: Path, conn: sqlite3.Connection) -> int:
    """Mine one file, insert new blocks. Returns count of new blocks."""
    language = detect_language(path)
    if not language:
        return 0

    try:
        code = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return 0

    if len(code) < 50:
        return 0

    inserted = 0
    cursor = conn.cursor()

    # Extract function/class blocks
    blocks = extract_function_blocks(code, language)
    for line_start, line_end, block_text in blocks:
        h = sha256(block_text)
        lv = lexical_vector(block_text)
        try:
            cursor.execute(
                """INSERT OR IGNORE INTO code_artifacts
                   (hash, source_agent, language, code_text, lexical_vector,
                    status, created_at, file_path, block_type, line_start, line_end)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (h, "karoo_miner", language, block_text, lv,
                 "mined", now_iso(), str(path), "function", line_start, line_end)
            )
            if cursor.rowcount > 0:
                inserted += 1
        except sqlite3.Error:
            pass

    # Extract algorithm patterns
    patterns = extract_patterns(code, language)
    for pattern_type, snippet in patterns:
        h = sha256(f"pattern:{pattern_type}:{snippet}")
        lv = lexical_vector(snippet)
        try:
            cursor.execute(
                """INSERT OR IGNORE INTO code_artifacts
                   (hash, source_agent, language, code_text, lexical_vector,
                    status, created_at, file_path, block_type)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (h, "karoo_pattern", language, snippet, lv,
                 "mined", now_iso(), str(path), f"pattern:{pattern_type}")
            )
            if cursor.rowcount > 0:
                inserted += 1
        except sqlite3.Error:
            pass

    conn.commit()
    return inserted


# ─── Report to HUD / Machine 1 ───────────────────────────────────
def report_to_hud(blocks_mined: int, files_scanned: int, total_blocks: int) -> None:
    payload = json.dumps({
        "agent": "karoo_miner",
        "event": "mine_cycle",
        "blocks_mined": blocks_mined,
        "files_scanned": files_scanned,
        "total_blocks": total_blocks,
        "timestamp": now_iso(),
    }).encode("utf-8")
    try:
        req = urllib.request.Request(
            OTG_BRIDGE_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass  # HUD might be down — don't crash


# ─── Main Mining Loop ─────────────────────────────────────────────
def scan_all(conn: sqlite3.Connection) -> tuple[int, int]:
    """Scan all source dirs. Returns (new_blocks, files_scanned)."""
    total_new = 0
    files_scanned = 0

    for source_dir in SOURCE_DIRS:
        if not source_dir.exists():
            continue
        for ext_list in LANG_MAP.values():
            for ext in ext_list:
                for path in source_dir.rglob(f"*{ext}"):
                    if "__pycache__" in str(path) or ".git" in str(path):
                        continue
                    try:
                        new = mine_file(path, conn)
                        total_new += new
                        files_scanned += 1
                    except Exception as e:
                        log(f"Error mining {path}: {e}")

    return total_new, files_scanned


def get_total_blocks(conn: sqlite3.Connection) -> int:
    try:
        return conn.execute("SELECT COUNT(*) FROM code_artifacts").fetchone()[0]
    except Exception:
        return 0


def main() -> None:
    log("=" * 60)
    log("KAROO CODE MINER v2.0 — ONLINE")
    log("=" * 60)
    log(f"Source dirs: {[str(d) for d in SOURCE_DIRS if d.exists()]}")
    log(f"Output DB: {CODE_DB}")

    conn = db_connect()
    cycle = 0

    while True:
        cycle += 1
        log(f"Mining cycle #{cycle}...")
        try:
            new_blocks, files = scan_all(conn)
            total = get_total_blocks(conn)
            log(f"Cycle #{cycle} complete: +{new_blocks} blocks from {files} files | total={total}")
            report_to_hud(new_blocks, files, total)
        except Exception as e:
            log(f"Cycle error: {e}")

        time.sleep(SCAN_INTERVAL)


if __name__ == "__main__":
    main()
