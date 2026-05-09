import argparse
import hashlib
import json
import os
import platform
import shutil
import socket
import sqlite3
import ctypes
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\Users\viper\VIPER_JAVA_RISC")
HOME = Path(r"C:\Users\viper")
DB_PATH = HOME / "gemini_bridge.db"
REPORT_DIR = ROOT / "global_agent_reports"

SAFE_ENV_KEYS = {
    "COMPUTERNAME",
    "USERNAME",
    "USERDOMAIN",
    "OS",
    "PROCESSOR_ARCHITECTURE",
    "NUMBER_OF_PROCESSORS",
    "PYTHONPATH",
    "JAVA_HOME",
    "PATH",
}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def now_id():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def connect_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def migrate():
    with connect_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS GLOBAL_AGENT_REGISTRY (
                agent_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                agent_type TEXT NOT NULL,
                endpoint TEXT,
                acl_address TEXT NOT NULL,
                capabilities_json TEXT NOT NULL,
                materials_json TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS GLOBAL_ACL_MESSAGES (
                message_id TEXT PRIMARY KEY,
                sender TEXT NOT NULL,
                receiver TEXT NOT NULL,
                performative TEXT NOT NULL,
                content TEXT NOT NULL,
                content_sha256 TEXT NOT NULL,
                route TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS GLOBAL_TODO_QUEUE (
                todo_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                details TEXT NOT NULL,
                priority INTEGER NOT NULL DEFAULT 2,
                status TEXT NOT NULL DEFAULT 'open',
                assigned_agent TEXT,
                proof_required INTEGER NOT NULL DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS GAME_DATA (
                game_id TEXT PRIMARY KEY,
                data_type TEXT NOT NULL,
                payload_sha256 TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                source_agent TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS GLOBAL_CHANGE_BROADCASTS (
                change_id TEXT PRIMARY KEY,
                sender TEXT NOT NULL,
                scope TEXT NOT NULL,
                acl_message_id TEXT NOT NULL,
                change_sha256 TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending_approval',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                approved_at DATETIME
            );

            CREATE TABLE IF NOT EXISTS PROOF_OF_EXECUTION (
                proof_id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                action TEXT NOT NULL,
                input_sha256 TEXT NOT NULL,
                output_sha256 TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS PROOF_OF_NETWORK (
                proof_id TEXT PRIMARY KEY,
                sender TEXT NOT NULL,
                receiver TEXT NOT NULL,
                acl_message_id TEXT NOT NULL,
                transport TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS NETWORK_SECURITY_EVENTS (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                severity INTEGER NOT NULL,
                heuristic_score REAL NOT NULL,
                details_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'observed',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS KERNEL_EVOLUTION_PROPOSALS (
                proposal_id TEXT PRIMARY KEY,
                kernel_id TEXT NOT NULL,
                hypothesis TEXT NOT NULL,
                variable_changed TEXT NOT NULL,
                expected_gain TEXT NOT NULL,
                risk_level INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending_user_approval',
                proposal_json TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS AUTO_ADVANCEMENT_POLICY (
                policy_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                min_success_rate REAL NOT NULL,
                min_speed_gain_pct REAL NOT NULL,
                min_resource_drop_pct REAL NOT NULL,
                allowed_scope TEXT NOT NULL,
                denied_scope TEXT NOT NULL,
                policy_json TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS AUTO_ADVANCEMENT_DECISIONS (
                decision_id TEXT PRIMARY KEY,
                proposal_id TEXT NOT NULL,
                success_rate REAL NOT NULL,
                speed_gain_pct REAL NOT NULL,
                resource_drop_pct REAL NOT NULL,
                decision TEXT NOT NULL,
                reason TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS AGENT_HEARTBEATS (
                heartbeat_id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                status TEXT NOT NULL,
                endpoint TEXT,
                cpu_cores INTEGER NOT NULL,
                ram_total_mb INTEGER NOT NULL,
                ram_available_mb INTEGER NOT NULL,
                disk_free_mb INTEGER NOT NULL,
                load_json TEXT NOT NULL,
                capabilities_json TEXT NOT NULL,
                resource_sha256 TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS AGENT_INSTALL_RULES (
                rule_id TEXT PRIMARY KEY,
                system_name TEXT NOT NULL,
                min_cpu_cores INTEGER NOT NULL,
                min_ram_available_mb INTEGER NOT NULL,
                min_disk_free_mb INTEGER NOT NULL,
                required_tools_json TEXT NOT NULL,
                install_scope TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS AGENT_INSTALL_DECISIONS (
                decision_id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                system_name TEXT NOT NULL,
                decision TEXT NOT NULL,
                reason TEXT NOT NULL,
                heartbeat_id TEXT,
                evidence_json TEXT NOT NULL,
                evidence_sha256 TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_acl_receiver_status ON GLOBAL_ACL_MESSAGES(receiver, status);
            CREATE INDEX IF NOT EXISTS idx_todo_status_priority ON GLOBAL_TODO_QUEUE(status, priority);
            CREATE INDEX IF NOT EXISTS idx_game_data_type ON GAME_DATA(data_type);
            CREATE INDEX IF NOT EXISTS idx_security_severity ON NETWORK_SECURITY_EVENTS(severity);
            CREATE INDEX IF NOT EXISTS idx_auto_advancement_decision ON AUTO_ADVANCEMENT_DECISIONS(decision);
            CREATE INDEX IF NOT EXISTS idx_agent_heartbeats_agent ON AGENT_HEARTBEATS(agent_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_agent_install_system ON AGENT_INSTALL_DECISIONS(system_name, decision);
            """
        )


def safe_env_snapshot():
    env = {}
    for key in SAFE_ENV_KEYS:
        value = os.environ.get(key)
        if value is None:
            continue
        if key == "PATH":
            parts = value.split(os.pathsep)
            env[key] = {"entry_count": len(parts), "sha256": sha256_text(value)}
        else:
            env[key] = value
    return env


def memory_status_mb():
    if platform.system().lower() == "windows":
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MEMORYSTATUSEX()
        status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
        return int(status.ullTotalPhys / (1024 * 1024)), int(status.ullAvailPhys / (1024 * 1024))
    return 0, 0


def resource_snapshot(required_tools=None):
    required_tools = required_tools or []
    total_mb, available_mb = memory_status_mb()
    disk = shutil.disk_usage(str(ROOT))
    tools = {}
    for name in sorted(set(required_tools + ["git", "java", "python", "node", "rustc", "cargo"])):
        found = bool(shutil.which(name))
        if name == "python":
            found = found or bool(sys.executable and Path(sys.executable).exists())
        tools[name] = found
    snapshot = {
        "host": socket.gethostname(),
        "platform": platform.platform(),
        "cpu_cores": os.cpu_count() or 1,
        "ram_total_mb": total_mb,
        "ram_available_mb": available_mb,
        "disk_free_mb": int(disk.free / (1024 * 1024)),
        "tools": tools,
    }
    snapshot["resource_sha256"] = sha256_text(json.dumps(snapshot, sort_keys=True))
    return snapshot


def quick_look(agent_id="local_viper_control"):
    migrate()
    snapshot = {
        "agent_id": agent_id,
        "timestamp": now_iso(),
        "host": socket.gethostname(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cwd": str(ROOT),
        "safe_env": safe_env_snapshot(),
        "resources": resource_snapshot(),
        "ports": {
            "gui": "http://127.0.0.1:8080",
            "house_cpp": "http://127.0.0.1:11435/api/generate",
            "logic_shipper": "http://127.0.0.1:18081",
        },
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_hash = sha256_text(json.dumps(snapshot, sort_keys=True))
    path = REPORT_DIR / f"QUICK_LOOK_{now_id()}_{report_hash[:12]}.json"
    path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    with connect_db() as conn:
        conn.execute(
            """
            INSERT INTO GAME_DATA (
                game_id, data_type, payload_sha256, payload_json, source_agent, status
            )
            VALUES (?, ?, ?, ?, ?, 'active')
            """,
            (
                f"GAME_QUICK_LOOK_{now_id()}_{report_hash[:10]}",
                "agent_quick_look",
                report_hash,
                json.dumps({"path": str(path), "summary": snapshot}, sort_keys=True),
                agent_id,
            ),
        )

        auto_policy = {
            "rule": "auto_advance_only_when_extremely_certain_and_measurably_better",
            "min_success_rate": 0.9999,
            "speed_gate": "speed_gain_pct >= 10.0",
            "resource_gate": "resource_drop_pct >= 10.0",
            "gate_logic": "success_rate >= 0.9999 AND (speed_gain_pct >= 10 OR resource_drop_pct >= 10)",
            "allowed_scope": [
                "sidecar configs",
                "routing thresholds",
                "hash metadata queues",
                "non-visual performance knobs",
                "generated reports and indexes",
            ],
            "denied_scope": [
                "GUI visual changes",
                "raw model weight mutation",
                "security/auth bypass",
                "destructive filesystem changes",
                "unapproved raw data exfiltration",
            ],
            "rollback_required": True,
            "poe_pon_required": True,
        }
        conn.execute(
            """
            INSERT INTO AUTO_ADVANCEMENT_POLICY (
                policy_id, name, min_success_rate, min_speed_gain_pct,
                min_resource_drop_pct, allowed_scope, denied_scope,
                policy_json, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')
            ON CONFLICT(policy_id) DO UPDATE SET
                min_success_rate=excluded.min_success_rate,
                min_speed_gain_pct=excluded.min_speed_gain_pct,
                min_resource_drop_pct=excluded.min_resource_drop_pct,
                allowed_scope=excluded.allowed_scope,
                denied_scope=excluded.denied_scope,
                policy_json=excluded.policy_json,
                status='active',
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                "auto_advance_9999_speed_resource_gate",
                "99.99 Success With 10 Percent Gain Auto-Advance Gate",
                0.9999,
                10.0,
                10.0,
                json.dumps(auto_policy["allowed_scope"]),
                json.dumps(auto_policy["denied_scope"]),
                json.dumps(auto_policy, indent=2),
            ),
        )
    return snapshot, path


def register_agent(agent_id, display_name, agent_type, endpoint=None):
    migrate()
    capabilities = {
        "performatives": ["tell", "request", "query-if", "inform", "propose", "failure"],
        "actions": [
            "quick-look",
            "broadcast-capabilities",
            "receive-global-todo",
            "submit-proof-of-execution",
            "submit-proof-of-network",
            "propose-kernel-evolution",
        ],
        "mutation_policy": "approval_required",
    }
    materials = {
        "made_of": {
            "runtime": "Python/Java/GGUF/SQLite sidecar control plane",
            "memory": "hash ledger + local SQLite + browser localStorage",
            "communication": "ACL/KQML performatives over ledger/tunnel",
        }
    }
    with connect_db() as conn:
        conn.execute(
            """
            INSERT INTO GLOBAL_AGENT_REGISTRY (
                agent_id, display_name, agent_type, endpoint, acl_address,
                capabilities_json, materials_json, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'active')
            ON CONFLICT(agent_id) DO UPDATE SET
                display_name=excluded.display_name,
                agent_type=excluded.agent_type,
                endpoint=excluded.endpoint,
                capabilities_json=excluded.capabilities_json,
                materials_json=excluded.materials_json,
                status='active',
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                agent_id,
                display_name,
                agent_type,
                endpoint,
                f"acl://{agent_id}",
                json.dumps(capabilities, indent=2),
                json.dumps(materials, indent=2),
            ),
        )
    return {"agent_id": agent_id, "capabilities": capabilities, "materials": materials}


def heartbeat(agent_id, endpoint=None, status_value="alive", required_tools=None):
    migrate()
    required_tools = required_tools or []
    resources = resource_snapshot(required_tools)
    capabilities = {
        "performatives": ["tell", "request", "query-if", "inform", "propose", "failure", "heartbeat"],
        "resource_policy": "install_only_if_resources_available",
        "tools": resources["tools"],
    }
    heartbeat_id = f"HEARTBEAT_{now_id()}_{sha256_text(agent_id + resources['resource_sha256'])[:12]}"
    with connect_db() as conn:
        conn.execute(
            """
            INSERT INTO AGENT_HEARTBEATS (
                heartbeat_id, agent_id, status, endpoint, cpu_cores,
                ram_total_mb, ram_available_mb, disk_free_mb, load_json,
                capabilities_json, resource_sha256
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                heartbeat_id,
                agent_id,
                status_value,
                endpoint,
                resources["cpu_cores"],
                resources["ram_total_mb"],
                resources["ram_available_mb"],
                resources["disk_free_mb"],
                json.dumps({"host": resources["host"], "platform": resources["platform"]}, sort_keys=True),
                json.dumps(capabilities, sort_keys=True),
                resources["resource_sha256"],
            ),
        )
        conn.execute(
            """
            UPDATE GLOBAL_AGENT_REGISTRY
            SET endpoint=COALESCE(?, endpoint), status='active', updated_at=CURRENT_TIMESTAMP
            WHERE agent_id=?
            """,
            (endpoint, agent_id),
        )
    return {"heartbeat_id": heartbeat_id, "agent_id": agent_id, "resources": resources, "capabilities": capabilities}


def seed_install_rules():
    migrate()
    rules = [
        {
            "rule_id": "install_rule_tiny_sidecar",
            "system_name": "tiny_sidecar",
            "min_cpu_cores": 1,
            "min_ram_available_mb": 512,
            "min_disk_free_mb": 256,
            "required_tools": ["python"],
            "install_scope": "small heartbeat/lens/router scripts",
        },
        {
            "rule_id": "install_rule_java_agent",
            "system_name": "java_agent",
            "min_cpu_cores": 2,
            "min_ram_available_mb": 2048,
            "min_disk_free_mb": 1024,
            "required_tools": ["java"],
            "install_scope": "Java backend services and local CLI helpers",
        },
        {
            "rule_id": "install_rule_rust_builder",
            "system_name": "rust_builder",
            "min_cpu_cores": 2,
            "min_ram_available_mb": 2048,
            "min_disk_free_mb": 2048,
            "required_tools": ["rustc", "cargo"],
            "install_scope": "Rust memory/tools builds",
        },
        {
            "rule_id": "install_rule_heavy_model_node",
            "system_name": "heavy_model_node",
            "min_cpu_cores": 4,
            "min_ram_available_mb": 8192,
            "min_disk_free_mb": 8192,
            "required_tools": ["python"],
            "install_scope": "local GGUF/llama-cpp model serving",
        },
    ]
    with connect_db() as conn:
        for rule in rules:
            conn.execute(
                """
                INSERT INTO AGENT_INSTALL_RULES (
                    rule_id, system_name, min_cpu_cores, min_ram_available_mb,
                    min_disk_free_mb, required_tools_json, install_scope, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'active')
                ON CONFLICT(rule_id) DO UPDATE SET
                    system_name=excluded.system_name,
                    min_cpu_cores=excluded.min_cpu_cores,
                    min_ram_available_mb=excluded.min_ram_available_mb,
                    min_disk_free_mb=excluded.min_disk_free_mb,
                    required_tools_json=excluded.required_tools_json,
                    install_scope=excluded.install_scope,
                    status='active',
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    rule["rule_id"],
                    rule["system_name"],
                    rule["min_cpu_cores"],
                    rule["min_ram_available_mb"],
                    rule["min_disk_free_mb"],
                    json.dumps(rule["required_tools"]),
                    rule["install_scope"],
                ),
            )
    return {"rules_seeded": [rule["rule_id"] for rule in rules]}


def latest_heartbeat(agent_id):
    with connect_db() as conn:
        row = conn.execute(
            """
            SELECT heartbeat_id, cpu_cores, ram_available_mb, disk_free_mb, capabilities_json
            FROM AGENT_HEARTBEATS
            WHERE agent_id=?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (agent_id,),
        ).fetchone()
    if not row:
        return None
    capabilities = json.loads(row[4])
    return {
        "heartbeat_id": row[0],
        "cpu_cores": row[1],
        "ram_available_mb": row[2],
        "disk_free_mb": row[3],
        "tools": capabilities.get("tools", {}),
    }


def evaluate_install(agent_id, system_name):
    migrate()
    seed_install_rules()
    hb = latest_heartbeat(agent_id)
    if not hb:
        hb = heartbeat(agent_id)["resources"]
        hb = latest_heartbeat(agent_id)
    with connect_db() as conn:
        rule = conn.execute(
            """
            SELECT rule_id, min_cpu_cores, min_ram_available_mb, min_disk_free_mb, required_tools_json
            FROM AGENT_INSTALL_RULES
            WHERE system_name=? AND status='active'
            LIMIT 1
            """,
            (system_name,),
        ).fetchone()
        if not rule:
            decision = "deny"
            reason = f"No active install rule exists for {system_name}."
            required_tools = []
        else:
            _, min_cpu, min_ram, min_disk, required_tools_json = rule
            required_tools = json.loads(required_tools_json)
            missing_tools = [tool for tool in required_tools if not hb["tools"].get(tool)]
            failures = []
            if hb["cpu_cores"] < min_cpu:
                failures.append(f"cpu_cores {hb['cpu_cores']} < {min_cpu}")
            if hb["ram_available_mb"] < min_ram:
                failures.append(f"ram_available_mb {hb['ram_available_mb']} < {min_ram}")
            if hb["disk_free_mb"] < min_disk:
                failures.append(f"disk_free_mb {hb['disk_free_mb']} < {min_disk}")
            if missing_tools:
                failures.append("missing tools: " + ", ".join(missing_tools))
            decision = "allowed" if not failures else "defer"
            reason = "Resources and required tools are available." if not failures else "; ".join(failures)
        evidence = {
            "agent_id": agent_id,
            "system_name": system_name,
            "heartbeat": hb,
            "required_tools": required_tools,
        }
        evidence_hash = sha256_text(json.dumps(evidence, sort_keys=True))
        decision_id = f"INSTALL_DECISION_{now_id()}_{sha256_text(agent_id + system_name + decision)[:10]}"
        conn.execute(
            """
            INSERT INTO AGENT_INSTALL_DECISIONS (
                decision_id, agent_id, system_name, decision, reason,
                heartbeat_id, evidence_json, evidence_sha256
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                decision_id,
                agent_id,
                system_name,
                decision,
                reason,
                hb.get("heartbeat_id"),
                json.dumps(evidence, sort_keys=True),
                evidence_hash,
            ),
        )
    return {
        "decision_id": decision_id,
        "agent_id": agent_id,
        "system_name": system_name,
        "decision": decision,
        "reason": reason,
        "evidence_sha256": evidence_hash,
    }


def acl_message(sender, receiver, performative, content, route="ledger"):
    migrate()
    content_hash = sha256_text(content)
    message_id = f"ACL_{now_id()}_{content_hash[:12]}"
    with connect_db() as conn:
        conn.execute(
            """
            INSERT INTO GLOBAL_ACL_MESSAGES (
                message_id, sender, receiver, performative, content,
                content_sha256, route, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'queued')
            """,
            (message_id, sender, receiver, performative, content, content_hash, route),
        )
    return {
        "message_id": message_id,
        "acl": f"({performative} :sender {sender} :receiver {receiver} :content {content})",
        "content_sha256": content_hash,
    }


def add_todo(title, details, priority=2, assigned_agent=None):
    migrate()
    todo_hash = sha256_text(title + details + str(priority))
    todo_id = f"TODO_{now_id()}_{todo_hash[:10]}"
    with connect_db() as conn:
        conn.execute(
            """
            INSERT INTO GLOBAL_TODO_QUEUE (
                todo_id, title, details, priority, assigned_agent
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (todo_id, title, details, priority, assigned_agent),
        )
    return {"todo_id": todo_id, "title": title, "priority": priority}


def seed_kernel_evolution_proposal():
    migrate()
    proposal = {
        "kernel_id": "house_cpp_gemma_2_2b_q8",
        "hypothesis": "Kernel speed and usefulness improve if routing/top-code recall happens before model generation and max_tokens stays compact.",
        "variable_changed": "Pre-generation context selection only; no model weights changed.",
        "expected_gain": "Lower latency, less prompt bulk, better agentic action classification.",
        "risk_level": 2,
        "requirements": [
            "Benchmark before/after on fixed prompts.",
            "One variable per experiment.",
            "No raw model file mutation.",
            "Auto-advance allowed only through AUTO_ADVANCEMENT_POLICY gate.",
            "Otherwise user approval is required.",
        ],
    }
    proposal_hash = sha256_text(json.dumps(proposal, sort_keys=True))
    proposal_id = f"KERNEL_PROP_{now_id()}_{proposal_hash[:12]}"
    with connect_db() as conn:
        conn.execute(
            """
            INSERT INTO KERNEL_EVOLUTION_PROPOSALS (
                proposal_id, kernel_id, hypothesis, variable_changed,
                expected_gain, risk_level, proposal_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                proposal_id,
                proposal["kernel_id"],
                proposal["hypothesis"],
                proposal["variable_changed"],
                proposal["expected_gain"],
                proposal["risk_level"],
                json.dumps(proposal, indent=2),
            ),
        )
    return {"proposal_id": proposal_id, "proposal": proposal}


def evaluate_auto_advance(proposal_id, success_rate, speed_gain_pct, resource_drop_pct):
    migrate()
    with connect_db() as conn:
        policy = conn.execute(
            """
            SELECT min_success_rate, min_speed_gain_pct, min_resource_drop_pct
            FROM AUTO_ADVANCEMENT_POLICY
            WHERE policy_id='auto_advance_9999_speed_resource_gate' AND status='active'
            """
        ).fetchone()
        if not policy:
            seed_defaults()
            policy = conn.execute(
                """
                SELECT min_success_rate, min_speed_gain_pct, min_resource_drop_pct
                FROM AUTO_ADVANCEMENT_POLICY
                WHERE policy_id='auto_advance_9999_speed_resource_gate'
                """
            ).fetchone()
        min_success, min_speed, min_resource = policy
        allowed = success_rate >= min_success and (
            speed_gain_pct >= min_speed or resource_drop_pct >= min_resource
        )
        decision = "auto_advance_allowed" if allowed else "proposal_only"
        reason = (
            "Passed 99.99% success gate and speed/resource improvement gate."
            if allowed
            else "Did not pass the 99.99% success plus 10% speed/resource gate."
        )
        decision_id = f"AUTO_DECISION_{now_id()}_{sha256_text(proposal_id + decision)[:10]}"
        conn.execute(
            """
            INSERT INTO AUTO_ADVANCEMENT_DECISIONS (
                decision_id, proposal_id, success_rate, speed_gain_pct,
                resource_drop_pct, decision, reason
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                decision_id,
                proposal_id,
                success_rate,
                speed_gain_pct,
                resource_drop_pct,
                decision,
                reason,
            ),
        )
    return {
        "decision_id": decision_id,
        "proposal_id": proposal_id,
        "decision": decision,
        "reason": reason,
        "success_rate": success_rate,
        "speed_gain_pct": speed_gain_pct,
        "resource_drop_pct": resource_drop_pct,
    }


def seed_local_network():
    local = register_agent("local_viper_control", "Local VIPER Control Plane", "control_plane", "http://127.0.0.1:8080")
    register_agent("karoo_gpt_sidecar", "Karoo GPT Sidecar", "optimizer", None)
    register_agent("loihi_sparse_sidecar", "Loihi Sparse Spike Sidecar", "neuromorphic_sim", None)
    register_agent("sha256_ledger_shipper", "SHA-256 Ledger Shipper", "ledger", "http://127.0.0.1:18081")
    message = acl_message(
        "local_viper_control",
        "all",
        "tell",
        "(broadcast-capabilities :policy approval-required :communication acl-kqml :payload hashes-first)",
        "local",
    )
    todo = add_todo(
        "Prepare cloud CLI pair registration",
        "When each website URL is provided, register the cloud CLI pair, run quick-look, request capabilities, and require POE/PON for actions.",
        1,
    )
    proposal = seed_kernel_evolution_proposal()
    install_rules = seed_install_rules()
    hb = heartbeat("local_viper_control", "http://127.0.0.1:8080")
    look, path = quick_look("local_viper_control")
    return {
        "registered": ["local_viper_control", "karoo_gpt_sidecar", "loihi_sparse_sidecar", "sha256_ledger_shipper"],
        "broadcast": message,
        "todo": todo,
        "kernel_proposal": proposal,
        "install_rules": install_rules,
        "heartbeat": hb["heartbeat_id"],
        "quick_look_path": str(path),
    }


def status():
    migrate()
    with connect_db() as conn:
        counts = {}
        for table in [
            "GLOBAL_AGENT_REGISTRY",
            "GLOBAL_ACL_MESSAGES",
            "GLOBAL_TODO_QUEUE",
            "GAME_DATA",
            "GLOBAL_CHANGE_BROADCASTS",
            "PROOF_OF_EXECUTION",
            "PROOF_OF_NETWORK",
            "NETWORK_SECURITY_EVENTS",
            "KERNEL_EVOLUTION_PROPOSALS",
            "AUTO_ADVANCEMENT_POLICY",
            "AUTO_ADVANCEMENT_DECISIONS",
            "AGENT_HEARTBEATS",
            "AGENT_INSTALL_RULES",
            "AGENT_INSTALL_DECISIONS",
        ]:
            counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    return counts


def main():
    parser = argparse.ArgumentParser(description="VIPER global ACL/KQML agent network control plane.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("migrate")
    sub.add_parser("seed-local")
    ql = sub.add_parser("quick-look")
    ql.add_argument("--agent-id", default="local_viper_control")
    reg = sub.add_parser("register-agent")
    reg.add_argument("agent_id")
    reg.add_argument("display_name")
    reg.add_argument("agent_type")
    reg.add_argument("--endpoint", default=None)
    msg = sub.add_parser("acl")
    msg.add_argument("sender")
    msg.add_argument("receiver")
    msg.add_argument("performative")
    msg.add_argument("content")
    td = sub.add_parser("todo")
    td.add_argument("title")
    td.add_argument("details")
    td.add_argument("--priority", type=int, default=2)
    sub.add_parser("kernel-proposal")
    adv = sub.add_parser("auto-advance-check")
    adv.add_argument("proposal_id")
    adv.add_argument("--success-rate", type=float, required=True)
    adv.add_argument("--speed-gain-pct", type=float, default=0.0)
    adv.add_argument("--resource-drop-pct", type=float, default=0.0)
    hb = sub.add_parser("heartbeat")
    hb.add_argument("--agent-id", default="local_viper_control")
    hb.add_argument("--endpoint", default=None)
    hb.add_argument("--required-tools", default="")
    sub.add_parser("seed-install-rules")
    inst = sub.add_parser("install-check")
    inst.add_argument("agent_id")
    inst.add_argument("system_name")
    sub.add_parser("status")
    args = parser.parse_args()

    if args.command == "migrate":
        migrate()
        print("GLOBAL_AGENT_NETWORK_TABLES_READY")
    elif args.command == "seed-local":
        print(json.dumps(seed_local_network(), indent=2))
    elif args.command == "quick-look":
        look, path = quick_look(args.agent_id)
        print(json.dumps({"path": str(path), "quick_look": look}, indent=2))
    elif args.command == "register-agent":
        print(json.dumps(register_agent(args.agent_id, args.display_name, args.agent_type, args.endpoint), indent=2))
    elif args.command == "acl":
        print(json.dumps(acl_message(args.sender, args.receiver, args.performative, args.content), indent=2))
    elif args.command == "todo":
        print(json.dumps(add_todo(args.title, args.details, args.priority), indent=2))
    elif args.command == "kernel-proposal":
        print(json.dumps(seed_kernel_evolution_proposal(), indent=2))
    elif args.command == "auto-advance-check":
        print(json.dumps(evaluate_auto_advance(
            args.proposal_id,
            args.success_rate,
            args.speed_gain_pct,
            args.resource_drop_pct,
        ), indent=2))
    elif args.command == "heartbeat":
        required_tools = [tool.strip() for tool in args.required_tools.split(",") if tool.strip()]
        print(json.dumps(heartbeat(args.agent_id, args.endpoint, required_tools=required_tools), indent=2))
    elif args.command == "seed-install-rules":
        print(json.dumps(seed_install_rules(), indent=2))
    elif args.command == "install-check":
        print(json.dumps(evaluate_install(args.agent_id, args.system_name), indent=2))
    elif args.command == "status":
        print(json.dumps(status(), indent=2))


if __name__ == "__main__":
    main()
