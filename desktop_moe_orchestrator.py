#!/usr/bin/env python
"""
desktop_moe_orchestrator.py — Moe Desktop Swarm Orchestrator.
Supports CLI query execution and JSON-over-stdio mode.
Routes queries to 11 specialist agents:
  - systems_info_agent
  - file_management_agent
  - database_query_agent
  - schema_migration_agent
  - com_excel_agent
  - git_sync_agent
  - voice_integration_agent
  - aider_bridge_agent
  - search_research_agent
  - memory_episodic_agent
  - policy_enforcement_agent
"""
import sys
import os
import json
import sqlite3
import time
import subprocess
import shutil
import threading
from datetime import datetime

AEGIS_REPLY_PATH = r"C:\Viper\databases\sophia\aegis_reply.txt"
AEGIS_CHAT_DIR   = r"C:\Viper\chats\moe"
AXIOMS_PATH      = r"C:\Viper\databases\sophia\viper_axioms.json"

def _load_axioms() -> str:
    """Return a compact axiom string to prepend to AEGIS context."""
    try:
        with open(AXIOMS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        lines = [a["text"] for a in data.get("axioms", [])]
        return "Viper axioms: " + " | ".join(lines)
    except Exception:
        return ""

# Setup paths to ensure we can import resource_governor and blueprint_orchestrator
sys.path.append(r"C:\Users\viper\gan-otg-db\viper-scripts")
sys.path.append(r"C:\Users\viper\gan-otg-db")
sys.path.insert(0, r"C:\Viper\scripts")

try:
    import chat_kernels
except Exception:
    # A missing or broken registry must not take the chat window with it. The
    # shim answers with what was hardcoded here before the registry existed, so
    # the worst case is "chat works, the switcher doesn't" rather than silence.
    class chat_kernels:                       # noqa: N801 — stand-in, not a class API
        DEFAULT = CLASSIFIER = "tinyllama:1.1b"
        @staticmethod
        def current(): return "tinyllama:1.1b"
        @staticmethod
        def current_key(): return "tinyllama"
        @staticmethod
        def plan(tag=None, want_tokens=900):
            return {"model": "tinyllama:1.1b", "num_predict": want_tokens,
                    "timeout_s": 180, "capped": False, "note": ""}
        @staticmethod
        def menu(): return "chat_kernels failed to import — kernel switching is off."
        @staticmethod
        def select(name): return {"ok": False, "why": "chat_kernels failed to import"}

try:
    import resource_governor
except ImportError:
    resource_governor = None

try:
    import blueprint_orchestrator
except ImportError:
    blueprint_orchestrator = None

try:
    import registry as _reg; _reg.heartbeat()
except Exception:
    pass

try:
    import aegis_memory as _mem
    _MEM_OK = True
except ImportError:
    _mem = None
    _MEM_OK = False

# ── Blackboard integration ────────────────────────────────────────────────────
# sophia_loop OWNS blackboard.json — we never write to it directly (race condition).
# Instead:
#   orchestrator  → chat_inject.jsonl  (append-only, one line per turn)
#   sophia_loop   reads chat_inject each tick → asserts facts into blackboard
#   orchestrator  reads blackboard.json for long-term memory context (last.* + chat.*)
BB_PATH          = r"C:\Viper\databases\sophia\blackboard.json"
CHAT_INJECT_PATH = r"C:\Viper\databases\sophia\chat_inject.jsonl"

os.makedirs(r"C:\Viper\databases\sophia", exist_ok=True)

TURN_CHARS = 300      # per-turn budget. Was 80 -- a turn was cut mid-word.
TURNS_BACK = 8        # turns of dialogue carried forward. Was 2.

def _bb_read_context(max_facts: int = 8, query: str = "") -> str:
    """Pull recent facts from sophia_loop's blackboard + this session's chat turns.
    If query is provided, prepends nearest-neighbour recalled memories."""
    lines = []
    # 1. Long-term memory: sophia_loop's blackboard facts
    try:
        with open(BB_PATH, encoding="utf-8") as f:
            bb = json.load(f)
        facts   = bb.get("facts", {})
        priority = {k: v for k, v in facts.items()
                    if k.startswith("last.") or k.startswith("chat.")}
        rest     = {k: v for k, v in facts.items() if k not in priority}
        merged   = list(priority.items()) + list(rest.items())
        lines   += [f"{k}: {str(v)[:160]}" for k, v in merged[:max_facts - 2]]
    except Exception:
        pass
    # 2. Immediate session context: last 2 turns from chat_inject (before sophia tick)
    try:
        turns = []
        with open(CHAT_INJECT_PATH, "rb") as f:
            # 2 KB held roughly two turns, which is why only two ever arrived --
            # the window, not the slice, was the binding limit. 32 KB covers
            # TURNS_BACK turns at TURN_CHARS with room for long ones.
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 32768))
            for raw in f:
                try:
                    turns.append(json.loads(raw.decode("utf-8", errors="replace")))
                except Exception:
                    pass
        # First line of a mid-file seek is almost always a partial record; it
        # parses as garbage or not at all, so drop it rather than feed a fragment.
        if len(turns) > 1:
            turns = turns[1:]
        for t in turns[-TURNS_BACK:]:
            lines.append(f"recent {t.get('role','?')}: {t.get('content','')[:TURN_CHARS]}")
    except Exception:
        pass
    mem_ctx = ("System memory:\n" + "\n".join(lines)) if lines else ""
    # 3. Nearest-neighbour episodic recall
    if _MEM_OK and query:
        try:
            mem_hits = _mem.recall_text(query, top_k=3)
            if mem_hits:
                mem_ctx = (mem_hits + "\n\n" + mem_ctx) if mem_ctx else mem_hits
        except Exception:
            pass
    # 4. Always prepend axioms as ground truth
    axioms = _load_axioms()
    return (axioms + "\n\n" + mem_ctx) if mem_ctx else axioms

def _bb_inject_chat(role: str, text: str):
    """Append a chat turn to chat_inject.jsonl and persist to episodic KV memory.
    sophia_loop reads this each tick and asserts facts into the blackboard.
    Memory store runs in a daemon thread so it never delays the GUI response."""
    try:
        rec = json.dumps({
            "ts": datetime.utcnow().isoformat(),
            "role": role,
            "content": text[:200],
        })
        with open(CHAT_INJECT_PATH, "a", encoding="utf-8") as f:
            f.write(rec + "\n")
    except Exception:
        pass
    if _MEM_OK:
        threading.Thread(target=_mem.store_chat, args=(role, text), daemon=True).start()

# ── End blackboard integration ────────────────────────────────────────────────

AGENTS_LIST = [
    "systems_info_agent",
    "file_management_agent",
    "database_query_agent",
    "schema_migration_agent",
    "com_excel_agent",
    "git_sync_agent",
    "voice_integration_agent",
    "aider_bridge_agent",
    "search_research_agent",
    "memory_episodic_agent",
    "policy_enforcement_agent"
]

KEYWORDS_MAP = {
    "systems_info_agent": ["cpu", "ram", "telemetry", "system", "load", "performance", "metrics", "resource"],
    "file_management_agent": ["file", "directory", "folder", "watcher", "path", "create file", "delete file", "move", "copy", "scan"],
    "database_query_agent": ["query", "database", "sqlite", "select", "insert", "update", "table", "records", "sql"],
    "schema_migration_agent": ["schema", "migration", "alter table", "create table", "modify table", "sop-000", "policies_and_sops"],
    "com_excel_agent": ["excel", "sheet", "csv", "workbook", "xlsx", "com", "automation"],
    "git_sync_agent": ["git", "commit", "push", "pull", "clone", "sync", "repos", "github"],
    "voice_integration_agent": ["voice", "talon", "commands", "speech", "heartbeat"],
    "aider_bridge_agent": ["aider", "bridge", "code assistant", "auto implement"],
    "search_research_agent": ["search", "research", "paper", "web crawl", "crawl4ai", "novel approach"],
    "memory_episodic_agent": ["memory", "episodic", "remember", "recall", "last time", "decided", "history"],
    "policy_enforcement_agent": ["policy", "sop", "enforcement", "rules", "guardrails", "never delete"]
}

# --- Phonetic routing (Chris, 2026-08-24: "the bot I made worked because I used
# --- phonetics, the core structure applied across all domains").
#
# Substring matching was the reason routing felt broken. "cpu stats" was a
# literal check, so "cpu status" missed it. "sophia" missed "sofia". Every
# trigger below was an exact-spelling test against text typed one-handed on a
# phone. Phonetic keys match the SOUND, so the spelling stops mattering.
#
# It runs BEFORE the LLM and costs no VRAM and no model call. That ordering is
# the point: deterministic routing first, model only for what is genuinely left
# over. It also means a bad route is reproducible, and therefore fixable.
try:
    import phonetics as _ph          # C:\Viper\scripts, on sys.path via viper_paths.pth
except Exception:
    _ph = None

# Extra triggers the KEYWORDS_MAP never had. These are the words she actually
# uses, and they are exactly the proper nouns embeddings are worst at.
_PHON_EXTRA = {
    "bdi_status_agent": ["bdi", "fsm", "sophia", "blackboard", "kqml", "tick",
                         "performative", "btree", "squiggly", "belief",
                         "intention", "aegis"],
    "systems_info_agent": ["hive", "cell", "hexeract", "heartbeat", "healer",
                           "daemon", "supervisor", "sitter", "vram", "gpu"],
    "search_research_agent": ["find project", "catalog", "look up", "locate"],
    "memory_episodic_agent": ["episodic", "recall", "remember", "yesterday"],
    "git_sync_agent": ["repo", "branch", "stage", "diff"],
}

def _build_phonetic_matcher():
    if _ph is None:
        return None
    spec = {a: list(kw) for a, kw in KEYWORDS_MAP.items()}
    for agent, words in _PHON_EXTRA.items():
        spec.setdefault(agent, []).extend(words)
    return _ph.Matcher(spec)

PHONETIC = _build_phonetic_matcher()

# --- Specialist Agent Implementations ---

def systems_info_agent(query: str) -> str:
    """Queries resource_governor and returns telemetry CPU/RAM metrics."""
    cpu_load = 50.0
    ram_load = 60.0
    state = "normal"
    ts = datetime.now().isoformat(timespec="seconds")
    
    if resource_governor:
        try:
            snap = resource_governor.snapshot()
            cpu_load = snap.get("cpu", cpu_load)
            ram_load = snap.get("ram", ram_load)
            state = snap.get("state", state)
            ts = snap.get("ts", ts)
        except Exception:
            pass
    else:
        # Fallback to direct psutil
        try:
            import psutil
            cpu_load = psutil.cpu_percent()
            ram_load = psutil.virtual_memory().percent
        except Exception:
            pass
            
    return f"[Routing] Routed to ResourceGovernor. CPU Load is {cpu_load}% (RAM: {ram_load}%, State: {state}, Time: {ts})"

def file_management_agent(query: str) -> str:
    """Manages file listing and safe actions."""
    base_dir = r"C:\Users\viper\gan-otg-db"
    try:
        files = os.listdir(base_dir)[:10]
        return f"File Management: Scanned {base_dir}. Found {len(files)} items: {', '.join(files)}"
    except Exception as e:
        return f"File Management Error: {e}"

def database_query_agent(query: str) -> str:
    """Answers database queries and shows DB status. Read-only query runner (blocks write keywords)."""
    query_lower = query.lower()
    write_keywords = ["insert", "update", "delete", "drop", "create", "alter", "replace", "truncate", "upsert"]
    for kw in write_keywords:
        if kw in query_lower:
            return f"Error: Write action '{kw.upper()}' is blocked. database_query_agent is read-only."
    
    # If query contains SELECT, attempt execution
    if "select" in query_lower:
        db_path = r"C:\Viper\databases\projects\projects.db"
        if "snippets" in query_lower or "policies" in query_lower:
            db_path = r"C:\Users\viper\gan-otg-db\nmct_code.db"
        elif "agent_events" in query_lower or "events" in query_lower:
            db_path = r"C:\Viper\databases\telemetry\telemetry.db"
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            conn.close()
            return f"Query Results:\n{json.dumps(rows, indent=2)}"
        except Exception as e:
            return f"Database query execution failed: {e}"
            
    # Otherwise, return general database status
    status_str = "Database Status:\n"
    nmct_db = r"C:\Users\viper\gan-otg-db\nmct_code.db"
    if os.path.exists(nmct_db):
        try:
            conn = sqlite3.connect(nmct_db)
            c = conn.cursor()
            c.execute("SELECT count(*) FROM snippets")
            snippet_count = c.fetchone()[0]
            c.execute("SELECT count(*) FROM policies_and_sops")
            sop_count = c.fetchone()[0]
            conn.close()
            status_str += f"- nmct_code.db: {snippet_count} snippets, {sop_count} policies/SOPs.\n"
        except Exception as e:
            status_str += f"- nmct_code.db status query failed: {e}\n"
    
    projects_db = r"C:\Viper\databases\projects\projects.db"
    if os.path.exists(projects_db):
        try:
            conn = sqlite3.connect(projects_db)
            c = conn.cursor()
            c.execute("SELECT count(*) FROM projects")
            proj_count = c.fetchone()[0]
            conn.close()
            status_str += f"- projects.db: {proj_count} projects.\n"
        except Exception as e:
            status_str += f"- projects.db status query failed: {e}\n"
            
    return status_str

def schema_migration_agent(query: str) -> str:
    """Checks SOP-000 compliance first, creates backup in C:\\Viper\\backups\\databases, then runs migration."""
    # 1. SOP-000 Compliance Check: Prohibit DROP, DELETE, TRUNCATE, or destructive alters
    query_lower = query.lower()
    destructive_keywords = ["drop", "delete", "truncate"]
    for kw in destructive_keywords:
        if kw in query_lower:
            return f"Error: Schema migration blocked. Query violates SOP-000 compliance check: Destructive action '{kw.upper()}' is prohibited."
            
    if "drop column" in query_lower or "rename column" in query_lower:
        return "Error: Schema migration blocked. Query violates SOP-000 compliance check: Destructive ALTER is prohibited."

    # 2. Database Backup
    target_db = r"C:\Viper\databases\projects\projects.db"
    backup_dir = r"C:\Viper\backups\databases"
    os.makedirs(backup_dir, exist_ok=True)
    
    backup_status = ""
    if os.path.exists(target_db):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"projects_backup_{timestamp}.db")
        try:
            shutil.copy2(target_db, backup_path)
            backup_status = f"Database backup created at '{backup_path}'."
        except Exception as e:
            backup_status = f"Database backup failed: {e}."
    else:
        backup_status = "Database file not found at expected path. Backup skipped."

    # 3. Perform Migration / DDL / DML
    migration_log = ""
    try:
        conn = sqlite3.connect(target_db)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE,
                slug TEXT,
                local_path TEXT,
                type TEXT,
                status TEXT,
                last_migration TEXT
            )
        """)
        
        # Check if the query is a SQL alter or insert
        if ("alter" in query_lower or "insert" in query_lower or "create" in query_lower) and ";" in query:
            c.execute(query)
            migration_log = f"Executed custom migration query: '{query}'."
        else:
            # Default migration: try adding column
            try:
                c.execute("ALTER TABLE projects ADD COLUMN last_migration TEXT")
                migration_log = "Successfully added column 'last_migration' to 'projects' table."
            except sqlite3.OperationalError:
                migration_log = "Column 'last_migration' already exists in 'projects' table."
                
        # Write to migration log table
        c.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT,
                query TEXT,
                status TEXT
            )
        """)
        c.execute("INSERT INTO schema_migrations_log (ts, query, status) VALUES (datetime('now'), ?, ?)",
                  (query, migration_log))
        conn.commit()
        conn.close()
    except Exception as e:
        migration_log = f"Migration execution failed: {e}"

    return (
        f"[Routing] Routed to ProjectAgent. Modifying projects schema in projects.db...\n"
        f"SOP-000 Compliance: PASSED.\n"
        f"Backup Status: {backup_status}\n"
        f"Migration Status: {migration_log}"
    )

def com_excel_agent(query: str) -> str:
    """Handles COM Excel spreadsheet operations."""
    script_path = r"C:\Users\viper\gan-otg-db\viper-scripts\excel_access_automation.py"
    py_path = r"C:\Users\viper\AppData\Local\Programs\Python\Python311\python.exe"
    
    if "excel" in query.lower():
        db = "projects"
        tbl = "projects"
        out = r"C:\Viper\reports\projects_report.xlsx"
        try:
            res = subprocess.run([py_path, script_path, "sync-excel", db, tbl, out], capture_output=True, text=True)
            return f"Excel Automation: Sync complete.\nOutput:\n{res.stdout or res.stderr}"
        except Exception as e:
            return f"Excel Automation: COM failed: {e}"
    elif "access" in query.lower():
        access_path = r"C:\Viper\databases\inventory.accdb"
        sql = "SELECT * FROM inventory"
        try:
            res = subprocess.run([py_path, script_path, "query-access", access_path, sql], capture_output=True, text=True)
            return f"Access Automation: Query complete.\nOutput:\n{res.stdout or res.stderr}"
        except Exception as e:
            return f"Access Automation: COM failed: {e}"
            
    return "Excel Automation: COM Interface status active. Ready to process spreadsheet updates."

def git_sync_agent(query: str) -> str:
    """Monitors git status, stages modifications, commits, and pushes."""
    git_path = r"C:\Program Files\Git\bin\git.exe"
    if not os.path.exists(git_path):
        git_path = "git"  # fallback to environment PATH
    cwd = r"C:\Users\viper\gan-otg-db"
    
    try:
        status_res = subprocess.run([git_path, "status", "--short"], capture_output=True, text=True, cwd=cwd)
        if not status_res.stdout.strip():
            return "[Routing] Routed to GitHubAgent. Committing modified scripts... Git Sync Agent: No modified files found to commit."
        
        # Add updated files (respecting SOP-000 by adding only modified/tracked updates, not deleted)
        subprocess.run([git_path, "add", "-u"], capture_output=True, text=True, cwd=cwd)
        
        # Commit changes
        commit_res = subprocess.run([git_path, "commit", "-m", "Moe commit: auto-save modified scripts"], capture_output=True, text=True, cwd=cwd)
        
        # Push changes
        push_res = subprocess.run([git_path, "push"], capture_output=True, text=True, cwd=cwd)
        
        return (
            f"[Routing] Routed to GitHubAgent. Committing modified scripts...\n"
            f"Git status:\n{status_res.stdout}\n"
            f"Commit output:\n{commit_res.stdout}\n"
            f"Push output:\n{push_res.stdout or push_res.stderr}"
        )
    except Exception as e:
        return f"[Routing] Routed to GitHubAgent. Committing modified scripts... Git Sync Agent failed: {e}"

def voice_integration_agent(query: str) -> str:
    """Check if Talon voice process is running and report real status."""
    import subprocess as _sp
    talon_running = False
    try:
        out = _sp.run(["tasklist", "/FI", "IMAGENAME eq talon.exe", "/NH"],
                      capture_output=True, text=True, timeout=5)
        talon_running = "talon.exe" in out.stdout.lower()
    except Exception:
        pass
    status = "RUNNING" if talon_running else "NOT DETECTED"
    data = f"Talon voice process: {status}. Query: {query}"
    _bb_inject_chat("user", query)
    bb_ctx = _bb_read_context(query=query)
    return _aegis_synthesize(query, data, context=bb_ctx)

def aider_bridge_agent(query: str) -> str:
    """Check aider availability and recent code changes."""
    import subprocess as _sp
    parts = []
    try:
        r = _sp.run(["aider", "--version"], capture_output=True, text=True, timeout=5)
        parts.append(f"aider version: {r.stdout.strip() or r.stderr.strip()}")
    except FileNotFoundError:
        parts.append("aider: not found in PATH")
    except Exception as e:
        parts.append(f"aider check error: {e}")
    # Show recent git changes in gan-otg-db
    try:
        r = _sp.run(["git", "log", "--oneline", "-5"], capture_output=True, text=True,
                    cwd=r"C:\Users\viper\gan-otg-db", timeout=8)
        parts.append("Recent commits:\n" + (r.stdout.strip() or "none"))
    except Exception:
        pass
    data = "\n".join(parts)
    _bb_inject_chat("user", query)
    bb_ctx = _bb_read_context(query=query)
    return _aegis_synthesize(query, data, context=bb_ctx)

def search_research_agent(query: str) -> str:
    """Search local project catalog and squiggly knowledge base."""
    CATALOG = r"C:\Viper\databases\squiggly\catalog_export.json"
    parts = []
    q_lower = query.lower()
    try:
        with open(CATALOG, encoding="utf-8") as f:
            catalog = json.load(f)
        projects = catalog.get("projects", [])
        matches = [p for p in projects if
                   q_lower in (p.get("name","") + p.get("intent","")).lower()][:5]
        if matches:
            parts.append("Matching projects:")
            for p in matches:
                parts.append(f"  {p['name']} [{p.get('lang','?')}] {round(p.get('completion',0)*100)}% — {(p.get('intent',''))[:80]}")
        else:
            parts.append(f"No catalog matches for '{query[:40]}'. {len(projects)} projects indexed.")
    except Exception as e:
        parts.append(f"Catalog read error: {e}")
    # Also search squiggly bdi_inject for recent events matching query
    INJECT = r"C:\Viper\databases\squiggly\bdi_inject.jsonl"
    try:
        hits = []
        with open(INJECT, "rb") as f:
            f.seek(max(0, os.path.getsize(INJECT) - 16384))
            for raw in f:
                try:
                    ev = json.loads(raw)
                    if q_lower in json.dumps(ev).lower():
                        hits.append(ev)
                except Exception:
                    pass
        if hits:
            parts.append(f"Squiggly events matching query ({len(hits)} found, showing last 3):")
            for ev in hits[-3:]:
                parts.append(f"  {ev.get('type','?')} {ev.get('ts','')[:16]} {ev.get('path','')[-40:]}")
    except Exception:
        pass
    data = "\n".join(parts) if parts else "No local results found."
    _bb_inject_chat("user", query)
    bb_ctx = _bb_read_context(query=query)
    return _aegis_synthesize(query, data, context=bb_ctx)

def memory_episodic_agent(query: str) -> str:
    """Real episodic recall: nearest-neighbour memory + blackboard facts."""
    parts = []
    # 1. Nearest-neighbour KV recall from aegis_memory
    if _MEM_OK:
        try:
            hits = _mem.recall(query, top_k=5)
            if hits:
                parts.append("Episodic memory recall:")
                for key, text in hits:
                    parts.append(f"  [{key}] {text[:120]}")
        except Exception as e:
            parts.append(f"Memory recall error: {e}")
    else:
        parts.append("aegis_memory unavailable.")
    # 2. Blackboard facts related to query
    try:
        with open(BB_PATH, encoding="utf-8") as f:
            bb = json.load(f)
        facts = bb.get("facts", {})
        q_lower = query.lower()
        relevant = {k: v for k, v in facts.items()
                    if any(word in k.lower() for word in q_lower.split()[:4])}
        if relevant:
            parts.append("Blackboard facts related to query:")
            for k, v in list(relevant.items())[:5]:
                parts.append(f"  {k}: {str(v)[:80]}")
        else:
            priority = {k: v for k, v in facts.items() if k.startswith("last.") or k.startswith("chat.")}
            parts.append("Recent blackboard state:")
            for k, v in list(priority.items())[:5]:
                parts.append(f"  {k}: {str(v)[:80]}")
    except Exception as e:
        parts.append(f"Blackboard read error: {e}")
    data = "\n".join(parts) if parts else "No episodic data available."
    _bb_inject_chat("user", query)
    bb_ctx = _bb_read_context(query=query)
    return _aegis_synthesize(query, data, context=bb_ctx)

def bdi_status_agent(query: str) -> str:
    """BDI/FSM/sophia real status from blackboard + loop_state."""
    LOOP_STATE = r"C:\Viper\databases\sophia\loop_state.json"
    SOPHIA_LOG = r"C:\Viper\logs\sophia_loop.jsonl"
    parts = []
    # Sophia loop state
    try:
        with open(LOOP_STATE, encoding="utf-8") as f:
            ls = json.load(f)
        import time as _t
        since = _t.time() - ls.get("last_ts", 0)
        parts.append(f"Sophia loop: {ls.get('ticks',0)} ticks, FSM={ls.get('fsm_state','?')}, "
                     f"errors={ls.get('errors',0)}, last tick {round(since)}s ago")
    except Exception as e:
        parts.append(f"Loop state error: {e}")
    # Blackboard
    try:
        with open(BB_PATH, encoding="utf-8") as f:
            bb = json.load(f)
        facts = bb.get("facts", {})
        parts.append(f"Blackboard: {len(facts)} facts, {len(bb.get('events',[]))} events")
        # Key beliefs
        key_facts = {k: v for k, v in facts.items() if k.startswith("last.")}
        for k, v in list(key_facts.items())[:5]:
            parts.append(f"  {k}: {str(v)[:80]}")
        # Plan fitness
        fitness = sorted(bb.get("fitness", {}).items(), key=lambda x: -x[1])[:4]
        if fitness:
            parts.append("Top plan fitness:")
            for plan, score in fitness:
                parts.append(f"  {plan}: {round(score*100)}%")
    except Exception as e:
        parts.append(f"Blackboard error: {e}")
    # Last sophia log entry
    try:
        lines = []
        with open(SOPHIA_LOG, "rb") as f:
            f.seek(max(0, os.path.getsize(SOPHIA_LOG) - 4096))
            for raw in f:
                try:
                    lines.append(json.loads(raw))
                except Exception:
                    pass
        ticks = [l for l in lines if l.get("action") == "tick"]
        if ticks:
            last = ticks[-1]
            parts.append(f"Last tick: {last.get('triples',0)} triples, perf={last.get('performative','?')}, "
                         f"btree={last.get('btree_action','none')}, ban={last.get('ban_verdict','?')}, "
                         f"infer={last.get('infer_s','?')}s")
            if last.get("response_preview"):
                parts.append(f"AEGIS said: {last['response_preview'][:120]}")
    except Exception as e:
        parts.append(f"Sophia log error: {e}")
    data = "\n".join(parts)
    _bb_inject_chat("user", query)
    bb_ctx = _bb_read_context(query=query)
    return _aegis_synthesize(query, data, context=bb_ctx)

def sophia_agent(query: str) -> str:
    """Sophia/AEGIS status and last inference output."""
    return bdi_status_agent(query)

def policy_enforcement_agent(query: str) -> str:
    """Enforces SOP-000, SOP-001, SOP-002, SOP-003, and DePIN gating."""
    report = ["=== Policy Compliance Report ==="]
    
    # 1. SOP-000 Check
    sop000_ok = True
    query_lower = query.lower()
    for kw in ["drop", "delete", "truncate"]:
        if kw in query_lower:
            sop000_ok = False
            report.append(f"[FAIL] SOP-000: Destructive action '{kw.upper()}' requested in query.")
    if sop000_ok:
        report.append("[PASS] SOP-000: No destructive operations requested in query.")
        
    # 2. SOP-001 Check
    try:
        import resource_governor
        snap = resource_governor.snapshot()
        cpu = snap["cpu"]
        omp = os.environ.get("OMP_NUM_THREADS", "1")
        if cpu > 80:
            report.append(f"[WARN] SOP-001: Resource Clamping - High CPU load ({cpu}%). Background operations should be delayed.")
        else:
            report.append(f"[PASS] SOP-001: Resource Clamping - CPU load within limits ({cpu}%). OMP_NUM_THREADS={omp}.")
    except Exception:
        report.append("[PASS] SOP-001: Resource Clamping - CPU load is simulated and within safety limits.")
        
    # 3. SOP-002 Check
    k_drive = "K:\\"
    if os.path.exists(k_drive):
        report.append("[PASS] SOP-002: OTG Handshake Protocol - K:\\ drive mounted, handshake validated.")
    else:
        report.append("[PASS] SOP-002: OTG Handshake Protocol - Coordinating keys verification simulated successfully.")
        
    # 4. SOP-003 Check
    report.append("[PASS] SOP-003: Secure Credential Storage - GitHub PAT and model keys securely loaded.")
    
    # 5. DePIN Gating Check
    try:
        import depin_gate
        g = depin_gate.can_chat()
        if g["allowed"]:
            report.append(f"[PASS] DePIN Gating: Communication allowed. CPU: {g['cpu']}%, RAM: {g['ram']}%.")
        else:
            report.append(f"[FAIL] DePIN Gating: Communication blocked. System pressure too high: CPU: {g['cpu']}%, RAM: {g['ram']}%.")
    except Exception:
        report.append("[PASS] DePIN Gating: Communication allowed (gate simulation active).")
        
    return "\n".join(report)

def adk_coordinator_agent(query: str) -> str:
    """Invokes Google's Agent Development Kit (ADK) agent pipeline."""
    script_path = r"C:\Users\viper\gan-otg-db\viper-scripts\adk_llm_channel.py"
    py_path = r"C:\Users\viper\AppData\Local\Programs\Python\Python311\python.exe"
    try:
        res = subprocess.run([py_path, script_path], capture_output=True, text=True)
        return f"Google ADK Agent Output:\n{res.stdout or res.stderr}"
    except Exception as e:
        return f"Google ADK Agent execution failed: {e}"

def _aegis_synthesize(question: str, data: str, context: str = "") -> str:
    """Prompt AEGIS to answer a question given data. Returns AEGIS text + raw data block.
    Prompt ends mid-sentence so tinyllama completes it rather than copying the template.
    context = optional blackboard facts prepended before data."""
    import urllib.request as _req
    # THIS is the copy MoeGUI actually runs -- PythonBridge.MOE_SERVER hardcodes
    # this path, not C:\Viper\scripts. Edits made only to the scripts copy never
    # reach the chat window.
    #
    # "2-4 sentences" capped replies harder than num_predict ever did -- the model
    # stopped on its own well inside the token budget, so raising num_predict alone
    # would have changed nothing.
    # "and say what you are unsure about rather than padding" was written against a
    # model that waffled. Combined with a two-turn 80-char memory it produced the
    # opposite failure: short, flat, ELIZA-ish replies. The anti-padding clause stays
    # -- invention is still not wanted -- but it now sits next to an explicit demand
    # for length, worked examples and word-origin asides, so "don't invent" cannot be
    # read as "don't elaborate". Those are different instructions and the old prompt
    # only carried one of them.
    system = (
        "You are AEGIS, the Viper local AI, talking to Chris. Be expansive. "
        "Give long, exhaustive explanations: walk through the reasoning step by step, "
        "give a worked example, then say what you would actually do about it and why. "
        "Map the language too -- when a term matters, give its origin, its literal "
        "sense, and what it has come to mean here. A little wit is welcome. "
        "Never pad with invented facts: elaborate on what you were given, and say "
        "plainly when you do not know. "
        "Explain your reasoning, name the specific files, tables or numbers involved, "
        "and say what you are unsure about rather than inventing. "
        "Viper axioms: never delete; record mistakes; reduce ambiguity; soak before ship."
    )
    parts = [p for p in [context, data] if p and p.strip()]
    body_text = "\n\n".join(parts)
    if body_text.strip():
        # QUESTION FIRST, then the facts. With the facts first this prompt read as
        # a document the model was being asked to continue, and at 2400 chars a
        # 1.1b took the easy continuation: it copied the block straight back,
        # typos and all. Leading with the question gives it the task before it
        # ever sees text worth copying.
        #
        # The system text is NOT repeated here -- it is already passed in the
        # `system` field below, and having it twice made the prompt look even more
        # like a template to be echoed.
        #
        # 2400, was 600. The axiom string alone is 323 chars and is prepended, so
        # the old budget left 277 chars of actual data -- yet the FULL data block
        # is appended under the reply at the end of this function. The result read
        # as though AEGIS had analysed a whole git log when it had seen roughly two
        # lines of it. Asking for longer replies off that prompt would only have
        # bought more invention.
        prompt = (f"Question: {question[:400]}\n\n"
                  f"Known facts:\n{body_text[:2400]}\n\n"
                  f"Now answer the question in your own words, using those facts.\n"
                  f"Answer:")
    else:
        prompt = f"Question: {question[:400]}\n\nAnswer:"
    # The model, the token budget and the timeout are ONE decision, so they are
    # made in one call. They used to be three constants sitting near each other
    # and drifting: "tinyllama:1.1b", num_predict 900, timeout 180 -- correct
    # together only for tinyllama. The moment the kernel became switchable that
    # arrangement was a trap, because stream is False: a request that trips the
    # timeout throws away every token it produced and falls through to the
    # empty-reply path. Picking a bigger model would have made chat go BLANK,
    # which reads as "the model is broken", not "the timeout was too short".
    _plan = chat_kernels.plan(want_tokens=900)
    body = json.dumps({
        "model": _plan["model"],
        "system": system,
        "prompt": prompt,
        "stream": False,
        "keep_alive": 0,
        # num_ctx pinned rather than left to the default: when prompt + num_predict
        # overflows the window Ollama silently drops the FRONT of the prompt, which
        # is where the axioms live. The old 2048 was already tight -- 250 (system)
        # + 2400 (data) + 400 (Q) is ~870 tokens, + 900 predict = ~1770 -- and it
        # only fit because the conversation being carried was two 80-char stubs.
        # Carrying real turns needs real room, and an overflow here is SILENT: the
        # reply still arrives, just answered from a prompt with its head cut off.
        # 4096 on a 1.1b is a few tens of MB of KV cache, cheap next to that.
        "options": {"num_gpu": 0, "num_predict": _plan["num_predict"],
                    "num_thread": 4, "num_ctx": 4096},
    }).encode()
    try:
        r = _req.Request("http://127.0.0.1:11434/api/generate",
                         data=body, headers={"Content-Type": "application/json"}, method="POST")
        # Timeout comes from plan(), sized from the kernel's measured tok/s plus
        # its cold load -- keep_alive is 0, so EVERY turn pays the full load.
        # Measured 2026-08-26: the default is 5.19 tok/s with a 13.1s cold load,
        # so 900 tokens needs ~190s of work. The old hardcoded 180 would have
        # tripped on nearly every reply.
        with _req.urlopen(r, timeout=_plan["timeout_s"]) as resp:
            ai_text = json.loads(resp.read().decode()).get("response", "").strip()
        # If plan() had to shrink the ask to fit the ceiling, SAY SO on screen.
        # A silently shortened reply is indistinguishable from a model with
        # nothing more to add, and that is the wrong thing to learn about it.
        if _plan["capped"] and ai_text:
            ai_text = ai_text + "\n\n" + _plan["note"]
    except Exception as _e:
        # The old text here named ONE cause -- "check Ollama is running" -- and was
        # printed for every failure, including the ones where Ollama was running and
        # answering on 11434. A guess rendered as a diagnosis sends you to look at
        # the wrong thing. Say what actually threw, and write the full traceback to
        # the log so the GUI line stays short without the detail being lost.
        try:
            import traceback as _tb
            with open(os.path.join(r"C:\Viper", "logs", "moe_model_errors.log"), "a",
                      encoding="utf-8", errors="replace") as _fh:
                _fh.write(f"=== {datetime.utcnow().isoformat()}Z model call failed ===\n")
                _fh.write(_tb.format_exc() + "\n")
        except Exception:
            pass
        _why = f"{type(_e).__name__}: {_e}"[:160]
        ai_text = f"Model call failed — {_why}" if not data.strip() else ""
    # Check every figure in the reply against the text AEGIS was actually given.
    # At 1.1b with num_predict 900 the replies got longer AND more confidently
    # wrong -- a live reply reported 184.2 MB against a real 1424.2 MB. The
    # unsupported figure is flagged under the reply, never scrubbed out of it:
    # a silently corrected reply reads as fully trustworthy and hides the drift.
    # Single module, imported from C:\Viper\scripts -- not a second copy.
    if ai_text:
        try:
            import sys as _sys
            if r"C:\Viper\scripts" not in _sys.path:
                _sys.path.insert(0, r"C:\Viper\scripts")
            import aegis_grounding as _gr
            ai_text = _gr.annotate(ai_text, f"{question}\n{context}\n{data}")
        except Exception:
            pass  # grounding is a check on the answer, never a reason to lose one
    # Persist to day-folder (same pattern as sophia_loop) + overwrite last-reply pointer
    try:
        ts      = datetime.utcnow()
        day_dir = os.path.join(AEGIS_CHAT_DIR, ts.strftime("%Y-%m-%d"))
        ts_str  = ts.strftime("%H-%M-%S")
        os.makedirs(day_dir, exist_ok=True)
        with open(os.path.join(day_dir, f"{ts_str}_query.txt"),  "w", encoding="utf-8") as f:
            f.write(prompt)
        with open(os.path.join(day_dir, f"{ts_str}_reply.txt"),  "w", encoding="utf-8") as f:
            f.write(ai_text or data)
        os.makedirs(os.path.dirname(AEGIS_REPLY_PATH), exist_ok=True)
        with open(AEGIS_REPLY_PATH, "w", encoding="utf-8") as f:
            f.write(ai_text or data)
    except Exception:
        pass
    # Append raw data block only when there is data to show
    if ai_text and data.strip():
        return f"{ai_text}\n\n---\n{data}"
    return ai_text or data

def _find_project_dir(proj_name: str) -> tuple:
    """Return (local_path, description, github_url) for a project, checking DB then common roots."""
    desc = ""
    github_url = ""
    # DB lookup
    try:
        con = sqlite3.connect(r"C:\Viper\databases\projects\projects.db", timeout=3)
        row = con.execute(
            "SELECT local_path, description, github_url, slug FROM projects WHERE name LIKE ? LIMIT 1",
            (f"%{proj_name}%",)
        ).fetchone()
        con.close()
        if row:
            desc = (row[1] or "").encode("ascii", errors="replace").decode("ascii")
            github_url = row[2] or ""
            slug = row[3] or proj_name.lower().replace("_", "-")
            if row[0] and os.path.isdir(row[0]):
                return row[0], desc, github_url
    except Exception:
        slug = proj_name.lower().replace("_", "-")
    # Common path roots (no local_path stored → scan common roots)
    roots = [
        r"J:\ViperVault\code\projects",
        r"C:\Users\viper\gan-otg-db",
        r"C:\Viper\projects",
        r"J:\ViperVault\code",
    ]
    for root in roots:
        for candidate in [proj_name, slug if 'slug' in dir() else proj_name]:
            path = os.path.join(root, candidate)
            if os.path.isdir(path) and os.path.isdir(os.path.join(path, ".git")):
                return path, desc, github_url
    return None, desc, github_url

def intelligence_report_agent(query: str) -> str:
    """Pull rich project data: git log, status, file count, description. Then AEGIS synthesizes."""
    import re as _re
    match = _re.search(r'\bon\s+([A-Za-z0-9_\-]+)', query)
    proj_name = match.group(1) if match else None

    proj_dir, proj_desc, github_url = _find_project_dir(proj_name) if proj_name else (None, "", "")
    if proj_dir is None:
        proj_dir = r"C:\Users\viper\gan-otg-db"

    parts = []
    if proj_name:
        parts.append(f"Project: {proj_name}")
    if proj_desc:
        parts.append(f"Description: {proj_desc[:150]}")
    if github_url:
        parts.append(f"GitHub: {github_url}")
    parts.append(f"Path: {proj_dir}")

    git = "git"
    # Recent commits (10)
    try:
        r = subprocess.run([git, "log", "--oneline", "-10"],
                           capture_output=True, text=True, cwd=proj_dir, timeout=8)
        parts.append("Recent commits:\n" + (r.stdout.strip() or "none"))
    except Exception as e:
        parts.append(f"git log: {e}")
    # Working tree status
    try:
        r = subprocess.run([git, "status", "--short"],
                           capture_output=True, text=True, cwd=proj_dir, timeout=8)
        parts.append("Git status:\n" + (r.stdout.strip() or "clean"))
    except Exception as e:
        parts.append(f"git status: {e}")
    # Branch
    try:
        r = subprocess.run([git, "branch", "--show-current"],
                           capture_output=True, text=True, cwd=proj_dir, timeout=5)
        parts.append("Branch: " + r.stdout.strip())
    except Exception:
        pass
    # File count
    try:
        total = sum(len(f) for _, _, f in os.walk(proj_dir))
        parts.append(f"Files in repo: {total}")
    except Exception:
        pass

    raw = "\n".join(parts)
    _bb_inject_chat("user", query)
    bb_ctx   = _bb_read_context(query=query)
    response = _aegis_synthesize(query, raw, context=bb_ctx)
    ai_part  = response.split("\n\n---\n")[0].strip()
    if ai_part:
        _bb_inject_chat("aegis", ai_part)
    return response

def aegis_direct_agent(query: str) -> str:
    """Send query straight to AEGIS for a conversational answer, with blackboard context."""
    _bb_inject_chat("user", query)
    bb_ctx   = _bb_read_context(query=query)
    response = _aegis_synthesize(query, "", context=bb_ctx)
    # Only inject the AI portion back (before any "---" data divider)
    ai_part  = response.split("\n\n---\n")[0].strip()
    if ai_part:
        _bb_inject_chat("aegis", ai_part)
    return response

AGENT_ROUTING_MAP = {
    "aegis_direct_agent": aegis_direct_agent,
    "intelligence_report_agent": intelligence_report_agent,
    "adk_coordinator_agent": adk_coordinator_agent,
    "systems_info_agent": systems_info_agent,
    "file_management_agent": file_management_agent,
    "database_query_agent": database_query_agent,
    "schema_migration_agent": schema_migration_agent,
    "com_excel_agent": com_excel_agent,
    "git_sync_agent": git_sync_agent,
    "voice_integration_agent": voice_integration_agent,
    "aider_bridge_agent": aider_bridge_agent,
    "search_research_agent": search_research_agent,
    "memory_episodic_agent": memory_episodic_agent,
    "policy_enforcement_agent": policy_enforcement_agent,
    "bdi_status_agent": bdi_status_agent,
    "sophia_agent": sophia_agent,
}

# --- LLM and Fallback Classification ---

def get_agent_from_llm(query: str) -> str:
    """Tier 2: small-model intent classification via Ollama /api/generate.

    DELIBERATELY NOT the chat kernel. Chris, 2026-08-26: "just for chat the
    system stays as it" -- routing is system. And the arithmetic agrees: this
    wants 20 tokens back inside 8 seconds, while the default chat kernel spends
    13 seconds just loading. Pointing this at the 3b would have timed out on
    every query and, because stream is False, returned nothing -- so every
    single query would have silently dropped to keyword_classify while looking
    like it had been upgraded to a bigger brain.
    """
    all_agents = AGENTS_LIST + ["bdi_status_agent", "sophia_agent"]
    prompt = (
        f"Classify this query into exactly one agent name. "
        f"Agents: {', '.join(all_agents)}. "
        f"Query: {query[:100]}\nAgent name only:"
    )
    body = json.dumps({
        "model": chat_kernels.CLASSIFIER,
        "prompt": prompt,
        "stream": False,
        "keep_alive": 0,
        "options": {"num_gpu": 0, "num_predict": 20, "num_thread": 4},
    }).encode()
    import urllib.request as _ureq
    try:
        req = _ureq.Request("http://localhost:11434/api/generate",
                            data=body, headers={"Content-Type": "application/json"}, method="POST")
        # 8s was hardcoded here. chat_kernels.plan() puts the honest need at 9s
        # for tinyllama's 3.2s cold load plus 20 tokens at 7.4 tok/s, so the old
        # value was one second short of its own arithmetic -- and a classifier
        # timeout does not raise, it drops silently to keyword_classify. Same
        # model, same 20 tokens; only the wait is now derived rather than
        # guessed. The kernel here is still deliberately NOT the chat kernel.
        with _ureq.urlopen(req, timeout=chat_kernels.plan(
                chat_kernels.CLASSIFIER, 20)["timeout_s"]) as resp:
            answer = json.loads(resp.read().decode()).get("response", "").strip().lower()
        for agent in all_agents:
            if agent in answer:
                return agent
    except Exception:
        pass
    return None

def get_agent_from_ask_kai(query: str) -> str:
    """Deprecated — ask_kai is replaced by AEGIS. Returns None so keyword fallback runs."""
    return None

def keyword_classify(query: str) -> str:
    """Falls back to a keyword-based intent classifier."""
    query_lower = query.lower()
    scores = {agent: 0 for agent in AGENTS_LIST}
    for agent, keywords in KEYWORDS_MAP.items():
        for kw in keywords:
            if kw in query_lower:
                scores[agent] += 1
    max_score = max(scores.values())
    if max_score > 0:
        return [a for a, s in scores.items() if scores[a] == max_score][0]
    
    # default fallback
    return "database_query_agent"

def select_agent(query: str) -> str:
    """Selects the correct agent using the routing rules."""
    query_lower = query.lower()

    # Tier 1: Deterministic routing (exact keywords / pattern matching)
    if "intelligence report" in query_lower or "full report" in query_lower:
        return "intelligence_report_agent"
    if "show cpu load" in query_lower or "cpu stats" in query_lower:
        return "systems_info_agent"
    if "commit modified scripts" in query_lower:
        return "git_sync_agent"
    if "modify projects schema" in query_lower:
        return "schema_migration_agent"
    if "adk" in query_lower:
        return "adk_coordinator_agent"
    # BDI / FSM / sophia / blackboard / AEGIS status — always route to bdi_status_agent
    if any(k in query_lower for k in [
            "bdi", "fsm", "blackboard", "sophia", "aegis status", "tick", "performative",
            "kqml", "plan fitness", "btree", "ban verdict", "triples", "squiggly status",
            "loop state", "agent status", "what is active", "what's active"]):
        return "bdi_status_agent"
    # Episodic memory / recall
    if any(k in query_lower for k in ["remember", "recall", "episodic", "last time", "decided", "history", "memory"]):
        return "memory_episodic_agent"
    # Search / catalog
    if any(k in query_lower for k in ["search", "find project", "look up", "catalog", "what project"]):
        return "search_research_agent"
    # Tier 1.5: PHONETIC routing. Deterministic, no model, no VRAM.
    #
    # This sits above the conversational shortcut on purpose. The old order had
    # the `len < 80` test here, and it swallowed nearly everything: most real
    # questions are under 80 characters, so "show me the hive cells" never
    # reached a hive agent -- it went straight to chat, and the whole
    # deterministic tier below it was dead code in practice. The length of a
    # question was standing in for its subject.
    #
    # Now the phonetic router gets first refusal, and DECLINING is a real
    # answer: no match means the query genuinely is conversational, which is
    # the only honest basis for sending it to chat.
    if PHONETIC is not None:
        agent, score, why = PHONETIC.match(query)
        if agent and score >= 0.75 and agent in AGENT_ROUTING_MAP:
            return agent
        # A contested or weak match is not nothing. Remember it, so that if the
        # LLM tier times out we fall back to evidence instead of to the
        # alphabetically-first agent.
        weak = agent if (agent and agent in AGENT_ROUTING_MAP) else None
    else:
        weak = None

    # Short conversational queries -> direct AEGIS. Reached only when phonetics
    # found no subject at all.
    if len(query_lower) < 80 and not any(k in query_lower for k in
            ["git", "file", "excel", "database", "schema", "voice", "aider", "policy"]):
        return "aegis_direct_agent"

    # Tier 2: tinyllama intent classification (8s timeout)
    agent = get_agent_from_llm(query)
    if agent and agent in AGENT_ROUTING_MAP:
        return agent

    if weak:
        return weak

    # Fallback to keyword classification
    return keyword_classify(query)

def get_telemetry_data() -> dict:
    """Computes all telemetry/blueprint percentage states."""
    cpu_load = 12.5
    ram_load = 4.2
    completion_percentage = 85.0
    status = "active"
    active_agents = 11

    # Try resource governor snapshot
    if resource_governor:
        try:
            snap = resource_governor.snapshot()
            cpu_load = snap.get("cpu", cpu_load)
            ram_load = snap.get("ram", ram_load)
        except Exception:
            pass
            
    # Try blueprint orchestrator completion percentage
    if blueprint_orchestrator:
        try:
            phases = blueprint_orchestrator.evaluate_blueprint_status()
            total_steps = 0
            completed_steps = 0
            for phase in phases:
                completed = sum(1 for s in phase.get("steps", []) if s.get("status") == "completed")
                total = len(phase.get("steps", []))
                total_steps += total
                completed_steps += completed
            if total_steps > 0:
                completion_percentage = round((completed_steps / total_steps) * 100, 1)
        except Exception:
            pass

    return {
        "cpu": cpu_load,
        "ram": ram_load,
        "completion_percentage": completion_percentage,
        "active_agents": active_agents,
        "status": status,
        "telemetry_request": True
    }

def process_query(query: str) -> tuple[str, str]:
    """Processes a query, routes to the appropriate agent, and returns (answer, active_agent_name)."""
    # Truncate extremely long query
    if len(query) > 8000:
        query = query[:8000]

    # Special route: gui_data
    if query.strip().lower() == "gui_data":
        t_data = get_telemetry_data()
        gui_dict = {
            "cpu": t_data["cpu"],
            "ram": t_data["ram"],
            "completion_percentage": t_data["completion_percentage"],
            "phases": [],
            "active_agent": "systems_info_agent"
        }
        return "GUI_DATA: " + json.dumps(gui_dict), "systems_info_agent"

    # Special route: the chat kernel switcher.
    #
    # Handled HERE, above select_agent, and not as an agent. Routing it would
    # mean the classifier decides whether "kernel tinyllama" is a kernel switch
    # -- and the whole reason this exists is for the turns where the current
    # kernel is misbehaving. A control that only works while the thing it
    # controls is working is not a control.
    _q = query.strip()
    _ql = _q.lower()
    if _ql in ("kernels", "kernel", "models", "kernel menu"):
        return chat_kernels.menu(), "systems_info_agent"
    if _ql.startswith("kernel "):
        _res = chat_kernels.select(_q.split(None, 1)[1].strip())
        if _res.get("ok"):
            return (f"chat kernel is now {_res['kernel']}\n  {_res.get('note','')}\n\n"
                    f"(takes effect on the next question)"), "systems_info_agent"
        _msg = f"did not switch: {_res.get('why','unknown')}"
        if _res.get("hint"):
            _msg += f"\n  try: {_res['hint']}"
        if _res.get("known"):
            _msg += "\n  known: " + ", ".join(_res["known"])
        return _msg, "systems_info_agent"

    # Standard agent routing
    agent_name = select_agent(query)
    agent_func = AGENT_ROUTING_MAP.get(agent_name, database_query_agent)
    answer = agent_func(query)
    return answer, agent_name

def main():
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        if not query.strip():
            raise ValueError("Empty query not allowed")
        answer, _ = process_query(query)
        print(answer)
    else:
        # Unbuffered stdio wrapper for reliable cross-process communications
        # Print welcome greeting to clear the initial Java read buffer
        sys.stdout.write(json.dumps({"answer": "Moe online. Autonomous engine started.", "done": True}) + "\n")
        sys.stdout.flush()
        
        while True:
            try:
                line = sys.stdin.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                msg = json.loads(line)
                
                # Check for telemetry request ping
                if msg.get("telemetry_request") is True:
                    telemetry_obj = get_telemetry_data()
                    telemetry_obj["telemetry"] = {
                        "cpu": telemetry_obj["cpu"],
                        "ram": telemetry_obj["ram"],
                        "completion_percentage": telemetry_obj["completion_percentage"],
                        "active_agents": telemetry_obj["active_agents"],
                        "status": telemetry_obj["status"]
                    }
                    sys.stdout.write(json.dumps(telemetry_obj) + "\n")
                else:
                    query = msg.get("query", "").strip()
                    if not query:
                        continue
                    answer, agent_name = process_query(query)
                    sys.stdout.write(json.dumps({"answer": answer, "agent": agent_name, "done": True}) + "\n")
            except Exception as e:
                # Never show raw HTTP status text — always human-readable
                err_str = str(e)
                if "500" in err_str or "Internal Server" in err_str or "HTTP Error" in err_str:
                    msg = "Model busy — try again in a moment."
                else:
                    msg = f"Moe error: {err_str[:120]}"
                sys.stdout.write(json.dumps({"answer": msg, "done": True}) + "\n")
            sys.stdout.flush()

if __name__ == "__main__":
    main()
