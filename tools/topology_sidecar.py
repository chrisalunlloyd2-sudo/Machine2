import argparse
import ast
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\Users\viper\VIPER_JAVA_RISC")
HOME = Path(r"C:\Users\viper")
DB_PATH = HOME / "gemini_bridge.db"
CHECKPOINT_DIR = ROOT / "topology_checkpoints"
CANDIDATE_DIR = ROOT / "topology_candidates"
ENV_MAP_DIR = ROOT / "topology_environment_maps"
APPROVAL_DIR = ROOT / "topology_approval_queue"
RETENTION_KEEP = 18
LOGIC_SHIPPER_PORT = 18081

LOCKED_GUI_FILES = [
    ROOT / "public" / "index.html",
    HOME / "KWEB" / "index.html",
]

SUBSYSTEM_FILES = {
    "GUI_LOCKED": [ROOT / "public" / "index.html", HOME / "KWEB" / "index.html"],
    "JAVA_BACKEND": [ROOT / "src" / "com" / "viper" / "risc" / "RiscServer.java"],
    "RISC_BRIDGE": [HOME / "risc_bridge_server.py"],
    "HOUSE_INFERENCE": [HOME / "house_inference_engine.py"],
    "TRIPLET_LOOP": [HOME / "infinite_triplet_loop.py"],
    "LOGIC_CRAWLER": [HOME / "logic_crawler.py"],
    "LOGIC_TABLES": [ROOT / "LOGIC_TABLE.md", ROOT / "LOIBI_LOGIC_TABLE.md"],
}


def now_id():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha256_file(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_text(path):
    return path.read_text(encoding="utf-8", errors="replace")


def connect_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def migrate():
    with connect_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS TOPO_SUBSYSTEMS (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                boundary TEXT NOT NULL,
                mode TEXT NOT NULL,
                manifest_json TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS TOPO_CHUNKS (
                id TEXT PRIMARY KEY,
                subsystem_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                source_path TEXT NOT NULL,
                start_line INTEGER NOT NULL,
                end_line INTEGER NOT NULL,
                content_sha256 TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS TOPO_EXPERIMENTS (
                id TEXT PRIMARY KEY,
                chunk_id TEXT NOT NULL,
                hypothesis TEXT NOT NULL,
                variable_changed TEXT NOT NULL,
                status TEXT NOT NULL,
                checkpoint_id TEXT,
                confidence REAL NOT NULL DEFAULT 0.0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                completed_at DATETIME
            );

            CREATE TABLE IF NOT EXISTS TOPO_CANDIDATES (
                id TEXT PRIMARY KEY,
                experiment_id TEXT NOT NULL,
                chunk_id TEXT NOT NULL,
                candidate_path TEXT NOT NULL,
                candidate_sha256 TEXT NOT NULL,
                comparison_count INTEGER NOT NULL DEFAULT 0,
                confidence REAL NOT NULL DEFAULT 0.0,
                action TEXT NOT NULL DEFAULT 'suggest_only',
                report TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS TOPO_RESULTS (
                id TEXT PRIMARY KEY,
                experiment_id TEXT NOT NULL,
                candidate_id TEXT,
                test_name TEXT NOT NULL,
                status TEXT NOT NULL,
                output TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS TOPO_REFERENCE_ADAPTERS (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                source_url TEXT NOT NULL,
                adapter_kind TEXT NOT NULL,
                mode TEXT NOT NULL,
                status TEXT NOT NULL,
                contract_json TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS TOPO_PORTS (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                port INTEGER NOT NULL,
                protocol TEXT NOT NULL,
                purpose TEXT NOT NULL,
                mode TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS LOGIC_BLOCKCHAIN_QUEUE (
                id TEXT PRIMARY KEY,
                payload_sha256 TEXT NOT NULL,
                prev_hash TEXT NOT NULL,
                chain_hash TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                destination_url TEXT,
                status TEXT NOT NULL DEFAULT 'queued',
                attempts INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                shipped_at DATETIME
            );

            CREATE TABLE IF NOT EXISTS LOGIC_BLOCKCHAIN_DESTINATIONS (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                base_url TEXT NOT NULL,
                uplink_url TEXT NOT NULL,
                ledger_url TEXT NOT NULL,
                protocol TEXT NOT NULL,
                mode TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS TOPO_ENVIRONMENT_MAPS (
                id TEXT PRIMARY KEY,
                map_sha256 TEXT NOT NULL,
                map_path TEXT NOT NULL,
                subsystem_count INTEGER NOT NULL,
                file_count INTEGER NOT NULL,
                chunk_count INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS TOPO_APPROVAL_REPORTS (
                id TEXT PRIMARY KEY,
                subsystem_id TEXT NOT NULL,
                report_path TEXT NOT NULL,
                report_sha256 TEXT NOT NULL,
                priority INTEGER NOT NULL DEFAULT 2,
                confidence REAL NOT NULL DEFAULT 0.0,
                status TEXT NOT NULL DEFAULT 'pending_user_approval',
                summary TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS TOPO_DISLIKE_REPAIR_QUEUE (
                id TEXT PRIMARY KEY,
                rag_id INTEGER NOT NULL,
                message_sha256 TEXT NOT NULL,
                feedback_type TEXT NOT NULL,
                repair_status TEXT NOT NULL DEFAULT 'pending_codex_review',
                approval_report_id TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                resolved_at DATETIME
            );

            CREATE INDEX IF NOT EXISTS idx_topo_chunks_subsystem ON TOPO_CHUNKS(subsystem_id);
            CREATE INDEX IF NOT EXISTS idx_topo_candidates_chunk ON TOPO_CANDIDATES(chunk_id);
            CREATE INDEX IF NOT EXISTS idx_topo_results_experiment ON TOPO_RESULTS(experiment_id);
            CREATE INDEX IF NOT EXISTS idx_logic_blockchain_queue_status ON LOGIC_BLOCKCHAIN_QUEUE(status);
            CREATE INDEX IF NOT EXISTS idx_topo_approval_status ON TOPO_APPROVAL_REPORTS(status);
            CREATE INDEX IF NOT EXISTS idx_topo_dislike_repair_status ON TOPO_DISLIKE_REPAIR_QUEUE(repair_status);
            """
        )

        for subsystem_id, files in SUBSYSTEM_FILES.items():
            existing = [str(path) for path in files if path.exists()]
            mode = "locked" if subsystem_id == "GUI_LOCKED" else "sidecar_controlled"
            boundary = (
                "Read-only GUI assets. Do not edit without explicit user approval."
                if subsystem_id == "GUI_LOCKED"
                else "Isolated subsystem tracked by topology sidecar."
            )
            manifest = {
                "files": existing,
                "hashes": {str(path): sha256_file(path) for path in files if path.exists()},
            }
            conn.execute(
                """
                INSERT INTO TOPO_SUBSYSTEMS (id, name, boundary, mode, manifest_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    boundary=excluded.boundary,
                    mode=excluded.mode,
                    manifest_json=excluded.manifest_json,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (subsystem_id, subsystem_id, boundary, mode, json.dumps(manifest, indent=2)),
            )

        conn.execute(
            """
            INSERT INTO TOPO_PORTS (id, name, port, protocol, purpose, mode, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                port=excluded.port,
                protocol=excluded.protocol,
                purpose=excluded.purpose,
                mode=excluded.mode,
                status=excluded.status,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                "PORT_LOGIC_BLOCKCHAIN_SHIPPER",
                "Logic Blockchain Shipper",
                LOGIC_SHIPPER_PORT,
                "http/json",
                "Low-latency logic-only queue for cloud blockchain logic DB sync.",
                "sidecar_no_gui",
                "registered",
            ),
        )


def seed_reference_adapters():
    migrate()
    adapters = [
        {
            "id": "ADAPTER_RAGFLOW",
            "name": "RAGFlow",
            "source_url": "https://github.com/infiniflow/ragflow",
            "adapter_kind": "rag_import_export",
            "mode": "metadata_only_v1",
            "status": "registered",
            "contract": {
                "purpose": "Import/export boundary for external RAG results.",
                "rule": "Do not replace SQLite manifold or live Java/GUI stack.",
                "inputs": ["documents", "chunks", "retrieval_metadata"],
                "outputs": ["TOPO_REFERENCE_ADAPTERS metadata", "future TOPO_CANDIDATES evidence"],
            },
        },
        {
            "id": "ADAPTER_WEBCRAWLER",
            "name": "WebCrawler",
            "source_url": "https://github.com/strings1/WebCrawler",
            "adapter_kind": "crawler_normalizer",
            "mode": "metadata_only_v1",
            "status": "registered",
            "contract": {
                "purpose": "Normalize crawl/search findings into comparison evidence.",
                "rule": "Crawl results are evidence only; no direct code mutation.",
                "inputs": ["url", "page_text", "snippet"],
                "outputs": ["logic source rows", "candidate comparison references"],
            },
        },
        {
            "id": "ADAPTER_GITHUB_GENETIC_ALGORITHM_TOPIC",
            "name": "GitHub Genetic Algorithm Topic",
            "source_url": "https://github.com/topics/genetic-algorithm",
            "adapter_kind": "reference_sampler",
            "mode": "metadata_only_v1",
            "status": "registered",
            "contract": {
                "purpose": "Sample similar implementations for 10-way comparison.",
                "rule": "Only store hashes, snippets, and analysis after review; never vendor code blindly.",
                "inputs": ["repository_url", "file_path", "snippet_hash"],
                "outputs": ["comparison_count", "confidence evidence"],
            },
        },
    ]
    with connect_db() as conn:
        for adapter in adapters:
            conn.execute(
                """
                INSERT INTO TOPO_REFERENCE_ADAPTERS (
                    id, name, source_url, adapter_kind, mode, status, contract_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    source_url=excluded.source_url,
                    adapter_kind=excluded.adapter_kind,
                    mode=excluded.mode,
                    status=excluded.status,
                    contract_json=excluded.contract_json,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    adapter["id"],
                    adapter["name"],
                    adapter["source_url"],
                    adapter["adapter_kind"],
                    adapter["mode"],
                    adapter["status"],
                    json.dumps(adapter["contract"], indent=2),
                ),
            )
    return len(adapters)


def latest_chain_hash(conn):
    row = conn.execute(
        """
        SELECT chain_hash FROM LOGIC_BLOCKCHAIN_QUEUE
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """
    ).fetchone()
    return row[0] if row else "GENESIS"


def build_logic_payload(limit=32):
    with connect_db() as conn:
        chunks = conn.execute(
            """
            SELECT id, subsystem_id, symbol, source_path, start_line, end_line, content_sha256, status
            FROM TOPO_CHUNKS
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        candidates = conn.execute(
            """
            SELECT id, experiment_id, chunk_id, candidate_sha256, comparison_count, confidence, action, created_at
            FROM TOPO_CANDIDATES
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        success_logic = conn.execute(
            """
            SELECT id, type, label, description, timestamp
            FROM TRIPLET_MANIFOLD
            WHERE lower(type) LIKE '%success%'
               OR lower(label) LIKE '%success%'
               OR lower(description) LIKE '%success%'
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        liked_feedback = conn.execute(
            """
            SELECT id, message, feedback_type, timestamp
            FROM RAG_MANIFOLD
            WHERE lower(feedback_type) IN ('like', 'liked', 'success')
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        approval_reports = conn.execute(
            """
            SELECT id, subsystem_id, report_sha256, priority, confidence, status, summary, created_at
            FROM TOPO_APPROVAL_REPORTS
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        dislike_repairs = conn.execute(
            """
            SELECT id, rag_id, message_sha256, feedback_type, repair_status, approval_report_id, created_at
            FROM TOPO_DISLIKE_REPAIR_QUEUE
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        environment_maps = conn.execute(
            """
            SELECT id, map_sha256, subsystem_count, file_count, chunk_count, created_at
            FROM TOPO_ENVIRONMENT_MAPS
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return {
        "schema": "VIPER_LOGIC_BLOCKCHAIN_V1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "policy": {
            "logic_only": True,
            "gui_locked": True,
            "promotion": "manual_approval_required",
            "one_variable_per_test": True,
        },
        "chunks": [
            {
                "id": row[0],
                "subsystem_id": row[1],
                "symbol": row[2],
                "source_path": row[3],
                "start_line": row[4],
                "end_line": row[5],
                "content_sha256": row[6],
                "status": row[7],
            }
            for row in chunks
        ],
        "candidates": [
            {
                "id": row[0],
                "experiment_id": row[1],
                "chunk_id": row[2],
                "candidate_sha256": row[3],
                "comparison_count": row[4],
                "confidence": row[5],
                "action": row[6],
                "created_at": row[7],
            }
            for row in candidates
        ],
        "success_logic": [
            {
                "id": row[0],
                "type": row[1],
                "label": row[2],
                "description_sha256": sha256_text(row[3] or ""),
                "logic_sha256": sha256_text("|".join([str(row[0]), str(row[1]), str(row[2]), str(row[3])])),
                "timestamp": row[4],
            }
            for row in success_logic
        ],
        "liked_feedback": [
            {
                "id": row[0],
                "message_sha256": sha256_text(row[1] or ""),
                "feedback_type": row[2],
                "timestamp": row[3],
            }
            for row in liked_feedback
        ],
        "approval_reports": [
            {
                "id": row[0],
                "subsystem_id": row[1],
                "report_sha256": row[2],
                "priority": row[3],
                "confidence": row[4],
                "status": row[5],
                "summary_sha256": sha256_text(row[6] or ""),
                "created_at": row[7],
            }
            for row in approval_reports
        ],
        "dislike_repairs": [
            {
                "id": row[0],
                "rag_id": row[1],
                "message_sha256": row[2],
                "feedback_type": row[3],
                "repair_status": row[4],
                "approval_report_id": row[5],
                "created_at": row[6],
            }
            for row in dislike_repairs
        ],
        "environment_maps": [
            {
                "id": row[0],
                "map_sha256": row[1],
                "subsystem_count": row[2],
                "file_count": row[3],
                "chunk_count": row[4],
                "created_at": row[5],
            }
            for row in environment_maps
        ],
    }


def queue_logic_payload(destination_url=None, limit=32):
    migrate()
    if destination_url is None:
        with connect_db() as conn:
            row = conn.execute(
                """
                SELECT uplink_url FROM LOGIC_BLOCKCHAIN_DESTINATIONS
                WHERE status LIKE 'ready%'
                ORDER BY updated_at DESC
                LIMIT 1
                """
            ).fetchone()
            if row:
                destination_url = row[0]
    payload = build_logic_payload(limit)
    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload_hash = sha256_text(payload_json)
    queued_id = f"LOGIC_BLOCK_{now_id()}_{payload_hash[:12]}"
    with connect_db() as conn:
        prev_hash = latest_chain_hash(conn)
        chain_hash = sha256_text(f"{prev_hash}:{payload_hash}")
        conn.execute(
            """
            INSERT INTO LOGIC_BLOCKCHAIN_QUEUE (
                id, payload_sha256, prev_hash, chain_hash, payload_json, destination_url, status
            )
            VALUES (?, ?, ?, ?, ?, ?, 'queued')
            """,
            (queued_id, payload_hash, prev_hash, chain_hash, payload_json, destination_url),
        )
    return {
        "id": queued_id,
        "payload_sha256": payload_hash,
        "prev_hash": prev_hash,
        "chain_hash": chain_hash,
        "destination_url": destination_url,
    }


def configure_cloud_destination(base_url):
    migrate()
    normalized = base_url.rstrip("/")
    destination = {
        "id": "DEST_CLOUDFLARE_SHA256_LOGIC_DB",
        "name": "Cloudflare SHA-256 Logic DB",
        "base_url": normalized,
        "uplink_url": f"{normalized}/api/uplink",
        "ledger_url": f"{normalized}/api/ledger",
        "protocol": "acl_kqml_plaintext",
        "mode": "prepared_hold",
        "status": "ready_not_auto_shipping",
    }
    with connect_db() as conn:
        conn.execute(
            """
            INSERT INTO LOGIC_BLOCKCHAIN_DESTINATIONS (
                id, name, base_url, uplink_url, ledger_url, protocol, mode, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                base_url=excluded.base_url,
                uplink_url=excluded.uplink_url,
                ledger_url=excluded.ledger_url,
                protocol=excluded.protocol,
                mode=excluded.mode,
                status=excluded.status,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                destination["id"],
                destination["name"],
                destination["base_url"],
                destination["uplink_url"],
                destination["ledger_url"],
                destination["protocol"],
                destination["mode"],
                destination["status"],
            ),
        )
    return destination


def checkpoint(label):
    migrate()
    safe_label = re.sub(r"[^A-Za-z0-9_.-]+", "_", label.strip() or "checkpoint")
    checkpoint_id = f"{now_id()}_{safe_label}"
    target = CHECKPOINT_DIR / checkpoint_id
    target.mkdir(parents=True, exist_ok=False)

    db_snapshot = target / "gemini_bridge.db"
    with sqlite3.connect(DB_PATH) as src, sqlite3.connect(db_snapshot) as dst:
        src.backup(dst)

    copied = {}
    for subsystem_id, files in SUBSYSTEM_FILES.items():
        for path in files:
            if not path.exists():
                continue
            rel = path.relative_to(ROOT) if str(path).startswith(str(ROOT)) else Path("HOME") / path.name
            dest = target / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
            copied[str(path)] = {
                "checkpoint_path": str(dest),
                "sha256": sha256_file(path),
                "subsystem": subsystem_id,
            }

    manifest = {
        "checkpoint_id": checkpoint_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "db_path": str(DB_PATH),
        "db_sha256": sha256_file(db_snapshot),
        "locked_gui_hashes": {str(path): sha256_file(path) for path in LOCKED_GUI_FILES if path.exists()},
        "copied_files": copied,
        "policy": {
            "gui": "locked",
            "karoo": "suggest_only",
            "promotion": "manual_approval_required",
            "experiment_rule": "one_variable_per_test",
        },
    }
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    with connect_db() as conn:
        conn.execute(
            """
            INSERT INTO TOPO_RESULTS (id, experiment_id, candidate_id, test_name, status, output)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                f"RESULT_{checkpoint_id}",
                "CHECKPOINT",
                None,
                "checkpoint_capture",
                "pass",
                json.dumps({"checkpoint_id": checkpoint_id, "path": str(target)}),
            ),
        )

    return checkpoint_id, target


def extract_chunks_from_python(path, subsystem_id):
    text = read_text(path)
    lines = text.splitlines()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []

    chunks = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start = getattr(node, "lineno", 1)
            end = getattr(node, "end_lineno", start)
            content = "\n".join(lines[start - 1 : end])
            symbol = getattr(node, "name", "anonymous")
            chunks.append((subsystem_id, symbol, path, start, end, content))
    return chunks


def extract_chunks_from_java(path, subsystem_id):
    text = read_text(path)
    lines = text.splitlines()
    chunks = []
    pattern = re.compile(r"^\s*(?:public|private|protected|static|final|\s)+\s*[\w<>\[\]]+\s+(\w+)\s*\([^;]*\)\s*(?:throws [^{]+)?\{")
    for index, line in enumerate(lines, start=1):
        match = pattern.match(line)
        if not match:
            continue
        depth = 0
        end = index
        for cursor in range(index, len(lines) + 1):
            depth += lines[cursor - 1].count("{")
            depth -= lines[cursor - 1].count("}")
            if depth <= 0 and cursor > index:
                end = cursor
                break
        content = "\n".join(lines[index - 1 : end])
        chunks.append((subsystem_id, match.group(1), path, index, end, content))
    return chunks


def refresh_chunks():
    migrate()
    all_chunks = []
    for subsystem_id, files in SUBSYSTEM_FILES.items():
        if subsystem_id == "GUI_LOCKED":
            continue
        for path in files:
            if not path.exists():
                continue
            if path.suffix == ".py":
                all_chunks.extend(extract_chunks_from_python(path, subsystem_id))
            elif path.suffix == ".java":
                all_chunks.extend(extract_chunks_from_java(path, subsystem_id))

    with connect_db() as conn:
        for subsystem_id, symbol, path, start, end, content in all_chunks:
            content_hash = sha256_text(content)
            chunk_id = f"CHUNK_{subsystem_id}_{symbol}_{content_hash[:12]}"
            conn.execute(
                """
                INSERT INTO TOPO_CHUNKS (
                    id, subsystem_id, symbol, source_path, start_line, end_line,
                    content_sha256, status, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?)
                ON CONFLICT(id) DO UPDATE SET
                    start_line=excluded.start_line,
                    end_line=excluded.end_line,
                    content_sha256=excluded.content_sha256,
                    status='active',
                    metadata_json=excluded.metadata_json,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    chunk_id,
                    subsystem_id,
                    symbol,
                    str(path),
                    start,
                    end,
                    content_hash,
                    json.dumps({"line_count": end - start + 1}),
                ),
            )
    return len(all_chunks)


def choose_candidate_chunk():
    with connect_db() as conn:
        row = conn.execute(
            """
            SELECT id, subsystem_id, symbol, source_path, start_line, end_line, content_sha256
            FROM TOPO_CHUNKS
            WHERE subsystem_id IN ('RISC_BRIDGE', 'TRIPLET_LOOP', 'HOUSE_INFERENCE')
            ORDER BY updated_at DESC, id ASC
            LIMIT 1
            """
        ).fetchone()
    return row


def file_metrics(path):
    text = read_text(path)
    lines = text.splitlines()
    metrics = {
        "path": str(path),
        "sha256": sha256_text(text),
        "bytes": path.stat().st_size,
        "line_count": len(lines),
        "todo_count": len(re.findall(r"\b(?:TODO|FIXME|HACK)\b", text, flags=re.IGNORECASE)),
        "broad_except_count": len(re.findall(r"except\s*:\s*pass|except\s+Exception\s+as\s+\w+", text)),
        "hardcoded_localhost_count": text.count("localhost") + text.count("127.0.0.1"),
    }
    if path.suffix == ".py":
        try:
            tree = ast.parse(text)
            metrics["function_count"] = sum(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) for n in ast.walk(tree))
            metrics["class_count"] = sum(isinstance(n, ast.ClassDef) for n in ast.walk(tree))
            imports = set()
            used_names = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.asname or alias.name.split(".")[0])
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        imports.add(alias.asname or alias.name)
                elif isinstance(node, ast.Name):
                    used_names.add(node.id)
            metrics["imports"] = sorted(imports)
            metrics["potential_missing_imports"] = sorted(name for name in ["subprocess", "requests", "sqlite3"] if name in used_names and name not in imports)
        except SyntaxError as exc:
            metrics["syntax_error"] = str(exc)
    return metrics


def build_environment_map():
    migrate()
    refresh_chunks()
    ENV_MAP_DIR.mkdir(parents=True, exist_ok=True)
    map_id = f"ENV_MAP_{now_id()}"
    files = []
    for subsystem_id, subsystem_files in SUBSYSTEM_FILES.items():
        for path in subsystem_files:
            if path.exists():
                item = file_metrics(path)
                item["subsystem_id"] = subsystem_id
                item["locked"] = subsystem_id == "GUI_LOCKED"
                files.append(item)

    with connect_db() as conn:
        chunk_count = conn.execute("SELECT COUNT(*) FROM TOPO_CHUNKS").fetchone()[0]
        recent_dislikes = conn.execute(
            """
            SELECT id, message, feedback_type, timestamp
            FROM RAG_MANIFOLD
            WHERE lower(feedback_type) LIKE '%dislike%'
            ORDER BY timestamp DESC
            LIMIT 12
            """
        ).fetchall()

    env_map = {
        "id": map_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "policy": {
            "gui_locked": True,
            "system_edits_require_approval": True,
            "karoo_mode": "topological_compare_and_submit_only",
            "genetic_rule": "one_changed_variable_per_test",
        },
        "subsystems": sorted(SUBSYSTEM_FILES.keys()),
        "files": files,
        "chunk_count": chunk_count,
        "recent_dislike_hashes": [
            {
                "rag_id": row[0],
                "message_sha256": sha256_text(row[1] or ""),
                "feedback_type": row[2],
                "timestamp": row[3],
            }
            for row in recent_dislikes
        ],
    }
    map_json = json.dumps(env_map, indent=2, sort_keys=True)
    map_hash = sha256_text(map_json)
    map_path = ENV_MAP_DIR / f"{map_id}_{map_hash[:12]}.json"
    map_path.write_text(map_json, encoding="utf-8")
    with connect_db() as conn:
        conn.execute(
            """
            INSERT INTO TOPO_ENVIRONMENT_MAPS (
                id, map_sha256, map_path, subsystem_count, file_count, chunk_count
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (map_id, map_hash, str(map_path), len(SUBSYSTEM_FILES), len(files), chunk_count),
        )
    return env_map, map_path, map_hash


def static_findings_from_map(env_map):
    findings = []
    for item in env_map["files"]:
        subsystem_id = item["subsystem_id"]
        path = item["path"]
        for missing in item.get("potential_missing_imports", []):
            findings.append(
                {
                    "subsystem_id": subsystem_id,
                    "priority": 1,
                    "confidence": 0.94,
                    "title": f"Potential missing import: {missing}",
                    "summary": f"{Path(path).name} references `{missing}` but does not import it. Submit a one-line import patch for approval.",
                    "one_variable": f"Add `import {missing}` only.",
                    "source_path": path,
                }
            )
        if item.get("broad_except_count", 0) > 2 and subsystem_id != "GUI_LOCKED":
            findings.append(
                {
                    "subsystem_id": subsystem_id,
                    "priority": 2,
                    "confidence": 0.78,
                    "title": "Broad exception handling reduces learning signal",
                    "summary": f"{Path(path).name} has {item['broad_except_count']} broad exception handlers. Propose logging one failure path first so Karoo can learn why a subsystem fails.",
                    "one_variable": "Replace one silent broad exception with logged exception detail.",
                    "source_path": path,
                }
            )
    return findings


def create_approval_report(finding, env_map_id):
    APPROVAL_DIR.mkdir(parents=True, exist_ok=True)
    report_id = f"APPROVAL_{now_id()}_{sha256_text(finding['title'] + finding['source_path'])[:10]}"
    report = {
        "id": report_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending_user_approval",
        "environment_map_id": env_map_id,
        "subsystem_id": finding["subsystem_id"],
        "priority": finding["priority"],
        "confidence": finding["confidence"],
        "title": finding["title"],
        "summary": finding["summary"],
        "source_path": finding["source_path"],
        "genetic_advancement_policy": {
            "suggest_only": True,
            "one_variable": finding["one_variable"],
            "must_pass_end_to_end": True,
            "requires_user_approval": True,
        },
    }
    report_json = json.dumps(report, indent=2, sort_keys=True)
    report_hash = sha256_text(report_json)
    report_path = APPROVAL_DIR / f"{report_id}_{report_hash[:12]}.json"
    report_path.write_text(report_json, encoding="utf-8")
    with connect_db() as conn:
        conn.execute(
            """
            INSERT INTO TOPO_APPROVAL_REPORTS (
                id, subsystem_id, report_path, report_sha256, priority, confidence, status, summary
            )
            VALUES (?, ?, ?, ?, ?, ?, 'pending_user_approval', ?)
            """,
            (
                report_id,
                finding["subsystem_id"],
                str(report_path),
                report_hash,
                finding["priority"],
                finding["confidence"],
                finding["summary"],
            ),
        )
    return report_id, report_path


def run_karoo_approval_cycle(label):
    env_map, map_path, map_hash = build_environment_map()
    findings = static_findings_from_map(env_map)
    created = []
    for finding in findings[:6]:
        # Avoid flooding duplicate pending reports for the same summary.
        with connect_db() as conn:
            exists = conn.execute(
                """
                SELECT id FROM TOPO_APPROVAL_REPORTS
                WHERE status='pending_user_approval' AND summary=?
                LIMIT 1
                """,
                (finding["summary"],),
            ).fetchone()
        if exists:
            continue
        report_id, report_path = create_approval_report(finding, env_map["id"])
        created.append({"id": report_id, "path": str(report_path), "summary": finding["summary"]})
    return {
        "label": label,
        "environment_map": str(map_path),
        "map_sha256": map_hash,
        "findings_seen": len(findings),
        "approval_reports_created": created,
    }


def monitor_dislikes():
    migrate()
    APPROVAL_DIR.mkdir(parents=True, exist_ok=True)
    created = []
    with connect_db() as conn:
        rows = conn.execute(
            """
            SELECT id, message, feedback_type, timestamp
            FROM RAG_MANIFOLD
            WHERE lower(feedback_type) LIKE '%dislike%'
            ORDER BY timestamp DESC
            LIMIT 50
            """
        ).fetchall()
        existing_rag_ids = {
            row[0]
            for row in conn.execute("SELECT rag_id FROM TOPO_DISLIKE_REPAIR_QUEUE").fetchall()
        }
    for rag_id, message, feedback_type, timestamp in rows:
        if rag_id in existing_rag_ids:
            continue
        message_hash = sha256_text(message or "")
        repair_id = f"DISLIKE_REPAIR_{rag_id}_{message_hash[:10]}"
        summary = (
            "Disliked reply detected. Karoo should check whether the prior response missed the requested action, "
            "then submit a concise Codex repair plan and log the fix outcome."
        )
        finding = {
            "subsystem_id": "REPLY_QUALITY",
            "priority": 1,
            "confidence": 0.88,
            "title": f"Dislike repair request {rag_id}",
            "summary": summary,
            "one_variable": "Repair only the disliked reply behavior or missing action; do not alter GUI/backend.",
            "source_path": "RAG_MANIFOLD",
        }
        report_id, report_path = create_approval_report(finding, f"RAG_DISLIKE_{rag_id}")
        with connect_db() as conn:
            conn.execute(
                """
                INSERT INTO TOPO_DISLIKE_REPAIR_QUEUE (
                    id, rag_id, message_sha256, feedback_type, repair_status, approval_report_id
                )
                VALUES (?, ?, ?, ?, 'pending_codex_review', ?)
                """,
                (repair_id, rag_id, message_hash, feedback_type, report_id),
            )
        created.append({"repair_id": repair_id, "rag_id": rag_id, "approval_report_id": report_id, "report_path": str(report_path)})
    return created


def run_suggest_cycle(label):
    checkpoint_id, checkpoint_path = checkpoint(label)
    chunk_count = refresh_chunks()
    row = choose_candidate_chunk()
    if not row:
        raise RuntimeError("No AI subsystem chunks available for a suggest cycle.")

    chunk_id, subsystem_id, symbol, source_path, start, end, content_hash = row
    source = Path(source_path)
    lines = read_text(source).splitlines()
    content = "\n".join(lines[start - 1 : end])

    experiment_id = f"EXP_{now_id()}_{sha256_text(chunk_id)[:10]}"
    candidate_id = f"CAND_{now_id()}_{sha256_text(content)[:10]}"
    cycle_dir = CANDIDATE_DIR / experiment_id
    cycle_dir.mkdir(parents=True, exist_ok=False)

    report = {
        "mode": "suggest_only",
        "checkpoint_id": checkpoint_id,
        "chunk_id": chunk_id,
        "subsystem_id": subsystem_id,
        "symbol": symbol,
        "source_path": source_path,
        "start_line": start,
        "end_line": end,
        "comparison_count": 0,
        "confidence": 0.0,
        "recommendation": "No code mutation performed. Candidate cycle captured baseline chunk for future one-variable tests.",
        "next_step": "Attach comparator outputs from project-local snippets or approved external references before proposing a patch.",
    }

    candidate_path = cycle_dir / f"{chunk_id}.baseline.txt"
    candidate_path.write_text(content, encoding="utf-8")
    report_path = cycle_dir / "report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    with connect_db() as conn:
        conn.execute(
            """
            INSERT INTO TOPO_EXPERIMENTS (
                id, chunk_id, hypothesis, variable_changed, status, checkpoint_id, confidence
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                experiment_id,
                chunk_id,
                "Establish isolated baseline before proposing a one-variable improvement.",
                "none_baseline_capture",
                "suggest_only_baseline",
                checkpoint_id,
                0.0,
            ),
        )
        conn.execute(
            """
            INSERT INTO TOPO_CANDIDATES (
                id, experiment_id, chunk_id, candidate_path, candidate_sha256,
                comparison_count, confidence, action, report
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                candidate_id,
                experiment_id,
                chunk_id,
                str(candidate_path),
                sha256_file(candidate_path),
                0,
                0.0,
                "suggest_only",
                json.dumps(report, indent=2),
            ),
        )
        conn.execute(
            """
            INSERT INTO TOPO_RESULTS (id, experiment_id, candidate_id, test_name, status, output)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                f"RESULT_{candidate_id}",
                experiment_id,
                candidate_id,
                "baseline_capture",
                "pass",
                f"Captured {chunk_count} chunks; no source files changed.",
            ),
        )

    return experiment_id, cycle_dir, report


def prune_retention(keep=RETENTION_KEEP):
    removed = []
    for base in [CHECKPOINT_DIR, CANDIDATE_DIR]:
        if not base.exists():
            continue
        entries = sorted([item for item in base.iterdir() if item.is_dir()], key=lambda item: item.name, reverse=True)
        for old in entries[keep:]:
            shutil.rmtree(old)
            removed.append(str(old))
    return removed


def status():
    migrate()
    with connect_db() as conn:
        counts = {}
        for table in [
            "TOPO_SUBSYSTEMS",
            "TOPO_CHUNKS",
            "TOPO_EXPERIMENTS",
            "TOPO_CANDIDATES",
            "TOPO_RESULTS",
            "TOPO_REFERENCE_ADAPTERS",
            "TOPO_PORTS",
            "LOGIC_BLOCKCHAIN_QUEUE",
            "LOGIC_BLOCKCHAIN_DESTINATIONS",
            "TOPO_ENVIRONMENT_MAPS",
            "TOPO_APPROVAL_REPORTS",
            "TOPO_DISLIKE_REPAIR_QUEUE",
        ]:
            counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    gui_hashes = {str(path): sha256_file(path) for path in LOCKED_GUI_FILES if path.exists()}
    web_status = "unknown"
    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "try { (Invoke-WebRequest -Uri 'http://127.0.0.1:8080/' -UseBasicParsing -TimeoutSec 5).StatusCode } catch { 'ERR' }",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        web_status = result.stdout.strip()
    except Exception as exc:
        web_status = f"ERR: {exc}"

    return {"tables": counts, "locked_gui_hashes": gui_hashes, "local_web_status": web_status}


def main():
    parser = argparse.ArgumentParser(description="VIPER topology sidecar checkpoint and suggest-only evolution tool.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("migrate")
    cp = sub.add_parser("checkpoint")
    cp.add_argument("--label", default="manual_checkpoint")
    sub.add_parser("refresh-chunks")
    sub.add_parser("seed-adapters")
    sub.add_parser("environment-map")
    ka = sub.add_parser("karoo-approval-cycle")
    ka.add_argument("--label", default="karoo_approval_cycle")
    sub.add_parser("monitor-dislikes")
    qb = sub.add_parser("queue-logic-block")
    qb.add_argument("--destination-url", default=None)
    qb.add_argument("--limit", type=int, default=32)
    cd = sub.add_parser("configure-cloud-destination")
    cd.add_argument("base_url")
    sc = sub.add_parser("suggest-cycle")
    sc.add_argument("--label", default="suggest_cycle")
    pr = sub.add_parser("prune")
    pr.add_argument("--keep", type=int, default=RETENTION_KEEP)
    sub.add_parser("status")
    args = parser.parse_args()

    if args.command == "migrate":
        migrate()
        print("TOPOLOGY_TABLES_READY")
    elif args.command == "checkpoint":
        checkpoint_id, path = checkpoint(args.label)
        print(json.dumps({"checkpoint_id": checkpoint_id, "path": str(path)}, indent=2))
    elif args.command == "refresh-chunks":
        count = refresh_chunks()
        print(json.dumps({"chunks_refreshed": count}, indent=2))
    elif args.command == "seed-adapters":
        count = seed_reference_adapters()
        print(json.dumps({"adapters_seeded": count}, indent=2))
    elif args.command == "environment-map":
        env_map, path, map_hash = build_environment_map()
        print(json.dumps({"path": str(path), "map_sha256": map_hash, "file_count": len(env_map["files"]), "chunk_count": env_map["chunk_count"]}, indent=2))
    elif args.command == "karoo-approval-cycle":
        result = run_karoo_approval_cycle(args.label)
        print(json.dumps(result, indent=2))
    elif args.command == "monitor-dislikes":
        created = monitor_dislikes()
        print(json.dumps({"repairs_created": created}, indent=2))
    elif args.command == "queue-logic-block":
        block = queue_logic_payload(args.destination_url, args.limit)
        print(json.dumps(block, indent=2))
    elif args.command == "configure-cloud-destination":
        destination = configure_cloud_destination(args.base_url)
        print(json.dumps(destination, indent=2))
    elif args.command == "suggest-cycle":
        experiment_id, path, report = run_suggest_cycle(args.label)
        print(json.dumps({"experiment_id": experiment_id, "path": str(path), "report": report}, indent=2))
    elif args.command == "prune":
        removed = prune_retention(args.keep)
        print(json.dumps({"removed": removed, "keep": args.keep}, indent=2))
    elif args.command == "status":
        print(json.dumps(status(), indent=2))


if __name__ == "__main__":
    main()
