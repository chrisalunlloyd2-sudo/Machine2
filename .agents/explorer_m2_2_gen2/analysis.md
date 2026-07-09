# M2: R1 Desktop MoE Implementer Strategy Report

This report outlines the implementation strategy for Milestone M2: R1 (`desktop_moe_orchestrator.py`) on Machine 2. It defines the structure and location of all databases, details how compliance with SOP-000, SOP-001, SOP-002, and SOP-003 is checked, and provides concrete architectural designs for the `schema_migration_agent`, `policy_enforcement_agent`, and `database_query_agent`.

---

## 1. Database Architecture: Locations and Schemas

Viper operates a multi-database architecture backed by SQLite. Below is the comprehensive catalog of databases, their file system locations, and primary tables:

| Database | File System Path | Primary Tables | Purpose / Schema Summary |
|---|---|---|---|
| **Projects** | `C:\Viper\databases\projects\projects.db` | `projects`, `projects_fts`, `project_milestones`, `project_token_tree`, `files` | Tracks active projects, metadata, directories, milestones, and file conventions. |
| **Code** | `C:\Viper\databases\code\code.db` | `code_artifacts`, `code_fts_semantic`, `code_fts_literal`, `code_token_tree`, `code_merges` | Stores SHA-256 deduplicated code blocks with BM25 dual search (semantic & literal). |
| **Research** | `C:\Viper\databases\research\research.db` | `research_entries`, `research_fts`, `whitepapers` | Stores crawled articles, category papers, and abstract indices. |
| **NMCT Catalog** | `C:\Users\viper\gan-otg-db\nmct_code.db` | `snippets`, `telemetry`, `database_catalog`, `policies_and_sops`, `information_trees` | Caches high-fitness snippets, registers other database coordinates, and holds policy logs. |
| **Prompts** | `C:\Viper\databases\prompts\prompts.db` | `prompts`, `prompt_fts` | System and user template registry for LLM invocation. |
| **Telemetry** | `C:\Viper\databases\telemetry\telemetry.db` | `system_metrics`, `agent_events`, `quota_usage`, `depin_ledger`, `resource_governor` | Monitors CPU/RAM telemetry, tracks agent usage costs, and logs DePIN communication chains. |
| **Tools** | `C:\Viper\databases\tools\tools.db` | `tools`, `tools_fts`, `tool_deps`, `tool_benchmarks` | Stores tool registry coordinates, installation commands, and stability stats. |
| **Graph** | `C:\Viper\databases\graph\graph.db` | `entities`, `entity_fts`, `edges`, `graph_snapshots` | Maps dependencies and interactions between code modules, files, and projects. |
| **Agents** | `C:\Viper\databases\agents\agents.db` | `agent_store`, `agent_store_fts` | Dedicated storage partition for individual agents using a standard key/value/meta WAL client. |

---

## 2. Programmatic SOP Enforcement & DePIN Gate Leashing

The `policy_enforcement_agent` checks system and codebase state for compliance prior to key events:

### A. SOP-000: Never Delete Codebases
*   **Rule**: No file deletion, destructive git overrides, database truncations, or table drops.
*   **Check Method**:
    1.  **Code Check**: Execute `git status` and `git diff --summary`. Inspect output for deletions (e.g., lines starting with `delete mode`).
    2.  **Lexical Inspection**: Prior to writing any code, verify that existing code blocks are not removed.
    3.  **Database Check**: (See `schema_migration_agent` below).

### B. SOP-001: Resource Clamping Policy
*   **Rule**: Background models and mathematical processes must restrict core execution to exactly 1 CPU core to keep the Xeon responsive.
*   **Check Method**:
    1.  Verify that running processes load the environment returned by `resource_governor.one_core_env()`.
    2.  Check code files for the imports of `resource_governor` or `cpu_governor`.
    3.  Monitor the process affinity at runtime:
        ```python
        import psutil
        p = psutil.Process(pid)
        if len(p.cpu_affinity()) > 1:
            p.cpu_affinity([0]) # Clamp to Core 0 immediately
        ```

### C. SOP-002: OTG Handshake Protocol
*   **Rule**: Inter-node transactions write and verify coordinating keys in `K:\` before responding to requests.
*   **Check Method**:
    1.  Verify `K:\m1_heartbeat.json` and `K:\m2_heartbeat.json` contain valid, non-stale ISO-8601 timestamps (delta < 30 seconds).
    2.  Verify `K:\handshake.json` has matching coordination tokens.
    3.  Verify the out-of-sandbox remote listener on port `18182` anunciates via `K:\remote_kai_handshake.json`.

### D. SOP-003: Viper GitHub OAuth Device Flow
*   **Rule**: Authenticate using the interactive device flow (`github-auth-device.py`), write credentials using `gh auth login`, and log events.
*   **Check Method**:
    1.  Run `gh auth status` via `subprocess.run` to confirm authenticated identity and token validity.
    2.  Query `telemetry.db` table `agent_events` where `agent_id = 'github-auth'` and check for non-expired session tokens.
    3.  Scan files for hardcoded personal access tokens or keys.

### E. DePIN Gate Leashing
*   **Rule**: Wire `depin_gate.gate(sender, receiver, content)` in front of agent communication. If `can_chat()` indicates CPU > 80% or RAM > 90%, block/defer the message. Record and chain-link hash outputs in `depin_ledger`.
*   **Check Method**:
    1.  Call `depin_gate.verify_chain()` to trace the hash links in `depin_ledger`. If the chain is broken, report an integrity alert.
    2.  Assert that `sender` and `receiver` communication endpoints have gate checks active.

---

## 3. Specialist Agent Architectures

Below are the recommended Python structures for the three target agents to be implemented:

### A. `schema_migration_agent`
Manages DDL/DML modifications safely.

```python
import sqlite3
import os
import re
import shutil
from datetime import datetime

class SchemaMigrationAgent:
    def __init__(self):
        self.backup_dir = r"C:\Viper\backups\databases"
        self.never_delete_rules_path = r"C:\Users\viper\gan-otg-db\viper-scripts\SOP_NEVER_DELETE.md"
        
    def _validate_sql_safety(self, sql_query: str) -> bool:
        # 1. Parse tokens case-insensitively
        query_upper = sql_query.upper()
        
        # 2. Ban destructive keywords
        banned = [r"\bDROP\b", r"\bDELETE\b", r"\bTRUNCATE\b"]
        for pattern in banned:
            if re.search(pattern, query_upper):
                return False
                
        # 3. Guard ALTER TABLE from dropping columns
        if "ALTER TABLE" in query_upper and "DROP" in query_upper:
            return False
            
        return True

    def _create_backup(self, db_path: str) -> str:
        os.makedirs(self.backup_dir, exist_ok=True)
        db_name = os.path.basename(db_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(self.backup_dir, f"{db_name}_backup_{timestamp}.db")
        shutil.copy2(db_path, backup_path)
        return backup_path

    def execute_migration(self, db_path: str, migration_sql: str) -> dict:
        # Pre-check query safety
        if not self._validate_sql_safety(migration_sql):
            return {
                "success": False,
                "error": "SOP-000 Violation: Destructive DDL/DML detected (DROP, DELETE, TRUNCATE are prohibited)."
            }
            
        # Create safety backup
        backup_file = self._create_backup(db_path)
        
        # Execute inside transaction
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()
        
        try:
            cursor.execute("BEGIN TRANSACTION;")
            cursor.executescript(migration_sql)
            conn.commit()
            return {
                "success": True,
                "backup_created": backup_file,
                "changes_applied": conn.total_changes
            }
        except Exception as e:
            conn.rollback()
            return {
                "success": False,
                "error": f"Migration failed. Transaction rolled back: {str(e)}",
                "backup_created": backup_file
            }
        finally:
            conn.close()
```

### B. `policy_enforcement_agent`
Monitors system activities for compliance with the 4 core SOPs.

```python
import subprocess
import os
import json
import sqlite3

class PolicyEnforcementAgent:
    def __init__(self):
        self.telemetry_db = r"C:\Viper\databases\telemetry\telemetry.db"
        self.k_drive = r"K:\\"

    def check_sop_000(self, repo_path: str) -> dict:
        # Run git status/diff to identify deleted files
        res = subprocess.run(["git", "status", "--porcelain"], cwd=repo_path, capture_output=True, text=True)
        deleted_files = [line[3:] for line in res.stdout.splitlines() if line.startswith(" D") or line.startswith("D ")]
        return {
            "compliant": len(deleted_files) == 0,
            "violations": deleted_files
        }

    def check_sop_001(self) -> dict:
        # Verify active cores limit on model server
        # Scan env or check current affinity settings
        import psutil
        violations = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmd = proc.info['cmdline'] or []
                if any("viper_llm_server" in c or "moe_server" in c for c in cmd):
                    affinity = proc.cpu_affinity()
                    if len(affinity) > 1:
                        violations.append({"pid": proc.info['pid'], "affinity": affinity})
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return {
            "compliant": len(violations) == 0,
            "violations": violations
        }

    def check_sop_002(self) -> dict:
        # Verify drive K handshakes
        hb1 = os.path.join(self.k_drive, "m1_heartbeat.json")
        hb2 = os.path.join(self.k_drive, "m2_heartbeat.json")
        hs = os.path.join(self.k_drive, "handshake.json")
        
        missing = [f for f in [hb1, hb2, hs] if not os.path.exists(f)]
        return {
            "compliant": len(missing) == 0,
            "missing_files": missing
        }

    def check_sop_003(self) -> dict:
        # Check GitHub Auth Flow CLI status
        res = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
        is_logged_in = "Logged in to github.com" in res.stderr or "Logged in to github.com" in res.stdout
        return {
            "compliant": is_logged_in,
            "detail": res.stderr.strip() or res.stdout.strip()
        }
```

### C. `database_query_agent`
A read-only specialist database access manager.

```python
import sqlite3
import os

class DatabaseQueryAgent:
    def __init__(self):
        self.db_map = {
            "projects": r"C:\Viper\databases\projects\projects.db",
            "code": r"C:\Viper\databases\code\code.db",
            "research": r"C:\Viper\databases\research\research.db",
            "nmct": r"C:\Users\viper\gan-otg-db\nmct_code.db"
        }

    def execute_read_query(self, db_key: str, select_query: str, params: tuple = ()) -> dict:
        if db_key not in self.db_map:
            return {"error": f"Database key '{db_key}' is not registered."}
            
        # 1. Enforce read-only policy at statement level
        query_upper = select_query.strip().upper()
        if not query_upper.startswith("SELECT") and not query_upper.startswith("WITH"):
            return {"error": "Write operations prohibited: Query agent is strictly read-only."}
            
        banned = ["INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", "REPLACE"]
        if any(f" {b} " in f" {query_upper} " for b in banned):
            return {"error": f"Write/destructive keyword detected. Query aborted."}

        # 2. Connect in read-only URI mode
        db_path = self.db_map[db_key]
        db_uri = f"file:{db_path}?mode=ro"
        
        try:
            conn = sqlite3.connect(db_uri, uri=True)
            cursor = conn.cursor()
            cursor.execute(select_query, params)
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()
            results = [dict(zip(columns, row)) for row in rows]
            return {"success": True, "data": results}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            conn.close()
```

---

## 4. Orchestration Integration Plan (`desktop_moe_orchestrator.py`)

To tie these three specialists into the local Mixture of Experts framework, the new `desktop_moe_orchestrator.py` should be developed with the following mechanisms:

1.  **Registry Incorporation**: Add the three specialists to the expert roster.
2.  **Intent Classification Mapping**:
    *   `schema_migration_agent` triggers: `"migration"`, `"alter table"`, `"create table"`, `"run sql scripts"`, `"database update"`.
    *   `policy_enforcement_agent` triggers: `"compliance status"`, `"sop checks"`, `"depin chain verify"`, `"handshake status"`, `"resource limit audit"`.
    *   `database_query_agent` triggers: `"select"`, `"query project database"`, `"list code snippets"`, `"lookup research files"`.
3.  **Active DePIN Gate Guard**:
    *   Wire `depin_gate.py` directly into the orchestrator execution loop.
    *   Before executing any query dispatch, compute `depin_gate.can_chat()`. If blocked, cache the request in `depin_ledger` as deferred and return a throttle delay wait code to the user or caller agent.
4.  **Single Core Process Pinning**:
    *   Apply `resource_governor.one_core_env()` thread constraints to the orchestrator shell environment on startup.
