import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\Users\viper\VIPER_JAVA_RISC")
HOME = Path(r"C:\Users\viper")
DB_PATH = HOME / "gemini_bridge.db"
REPORT_DIR = ROOT / "ledger_sync_readiness"


def connect_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def migrate():
    with connect_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS SHA256_LEDGER_REPLICAS (
                replica_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                base_url TEXT,
                uplink_url TEXT,
                ledger_url TEXT,
                role TEXT NOT NULL,
                trust_mode TEXT NOT NULL,
                sync_mode TEXT NOT NULL,
                status TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS SHA256_SYNC_CONTRACTS (
                contract_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                schema_name TEXT NOT NULL,
                payload_scope TEXT NOT NULL,
                transport TEXT NOT NULL,
                auth_policy TEXT NOT NULL,
                mutation_policy TEXT NOT NULL,
                contract_json TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS AGENT_GLOBAL_ACCESS_POLICIES (
                policy_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                route TEXT NOT NULL,
                allowed_performatives TEXT NOT NULL,
                denied_actions TEXT NOT NULL,
                approval_required INTEGER NOT NULL DEFAULT 1,
                policy_json TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS COMPUTE_RESOURCE_REGISTRY (
                resource_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                endpoint TEXT,
                capabilities_json TEXT NOT NULL,
                trust_mode TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS LEDGER_SYNC_READINESS_REPORTS (
                report_id TEXT PRIMARY KEY,
                report_path TEXT NOT NULL,
                readiness_status TEXT NOT NULL,
                summary TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """
        )


def seed_defaults():
    migrate()
    with connect_db() as conn:
        conn.execute(
            """
            INSERT INTO SHA256_LEDGER_REPLICAS (
                replica_id, name, base_url, uplink_url, ledger_url, role,
                trust_mode, sync_mode, status, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(replica_id) DO UPDATE SET
                base_url=excluded.base_url,
                uplink_url=excluded.uplink_url,
                ledger_url=excluded.ledger_url,
                role=excluded.role,
                trust_mode=excluded.trust_mode,
                sync_mode=excluded.sync_mode,
                status=excluded.status,
                notes=excluded.notes,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                "cloudflare_sha256_logic_db",
                "Cloudflare SHA-256 Logic DB",
                "https://perfume-had-prevent-take.trycloudflare.com",
                "https://perfume-had-prevent-take.trycloudflare.com/api/uplink",
                "https://perfume-had-prevent-take.trycloudflare.com/api/ledger",
                "cloud_hot_replica",
                "zero_trust_hash_only",
                "queued_push_then_reconcile",
                "configured",
                "Existing uplink target. Current hostname may rotate with Cloudflare tunnel.",
            ),
        )

        contract = {
            "schema": "VIPER_GLOBAL_LEDGER_SYNC_V1",
            "payloads": [
                "LOGIC_BLOCKCHAIN_QUEUE payload hashes",
                "TOPO_CHUNKS code hashes",
                "TOPO_APPROVAL_REPORTS proposal hashes",
                "LOIHI_TOPO_CODES and spike experiment hashes",
                "RAG liked/disliked feedback hashes",
            ],
            "rules": [
                "Hash metadata first; raw code or raw chat only by explicit approval.",
                "Remote nodes can propose work but cannot mutate local files directly.",
                "Every shipped block keeps prev_hash and chain_hash lineage.",
                "Agents read global DB through performative router contracts.",
            ],
        }
        conn.execute(
            """
            INSERT INTO SHA256_SYNC_CONTRACTS (
                contract_id, name, schema_name, payload_scope, transport,
                auth_policy, mutation_policy, contract_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(contract_id) DO UPDATE SET
                payload_scope=excluded.payload_scope,
                transport=excluded.transport,
                auth_policy=excluded.auth_policy,
                mutation_policy=excluded.mutation_policy,
                contract_json=excluded.contract_json,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                "global_hash_metadata_contract",
                "Global Hash Metadata Contract",
                "VIPER_GLOBAL_LEDGER_SYNC_V1",
                "logic/code/topology/spike hashes plus approval reports",
                "ACL-KQML over HTTP; future TCP bridge allowed",
                "zero-trust hash lineage; endpoint auth to be added per replica",
                "approval_required_for_local_mutation",
                json.dumps(contract, indent=2),
            ),
        )

        policy = {
            "route": "performative_router_first",
            "chat": "rolling recursive response lane",
            "performative": "Karoo/Codex approval lane",
            "both": "split talk and action; action stays approval gated",
            "resource_coordination": "registered compute can bid/propose, not self-apply",
        }
        conn.execute(
            """
            INSERT INTO AGENT_GLOBAL_ACCESS_POLICIES (
                policy_id, name, route, allowed_performatives, denied_actions,
                approval_required, policy_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(policy_id) DO UPDATE SET
                route=excluded.route,
                allowed_performatives=excluded.allowed_performatives,
                denied_actions=excluded.denied_actions,
                approval_required=excluded.approval_required,
                policy_json=excluded.policy_json,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                "global_agent_access_v1",
                "Global Agent Access V1",
                "PERFORMATIVE_ROUTE_LOG",
                json.dumps(["tell", "request", "query-if", "inform", "propose", "agree", "failure"]),
                json.dumps(["direct_local_file_mutation", "unapproved_code_execution", "raw_secret_export"]),
                1,
                json.dumps(policy, indent=2),
            ),
        )

        conn.execute(
            """
            INSERT INTO COMPUTE_RESOURCE_REGISTRY (
                resource_id, name, resource_type, endpoint, capabilities_json,
                trust_mode, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(resource_id) DO UPDATE SET
                endpoint=excluded.endpoint,
                capabilities_json=excluded.capabilities_json,
                trust_mode=excluded.trust_mode,
                status=excluded.status,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                "local_viper_stack",
                "Local VIPER Stack",
                "local_control_plane",
                "http://127.0.0.1:8080",
                json.dumps(
                    {
                        "services": ["gui", "risc_bridge", "house_inference", "karoo_sidecar", "loihi_sparse_sim"],
                        "role": "source_of_truth_and_approval_gate",
                    },
                    indent=2,
                ),
                "trusted_local",
                "configured",
            ),
        )


def collect_counts(conn):
    tables = [
        "LOGIC_BLOCKCHAIN_QUEUE",
        "TOPO_CHUNKS",
        "TOPO_APPROVAL_REPORTS",
        "PERFORMATIVE_ROUTE_LOG",
        "LOIHI_TOPO_CODES",
        "LOIHI_SPIKE_EXPERIMENTS",
        "SHA256_LEDGER_REPLICAS",
        "SHA256_SYNC_CONTRACTS",
        "AGENT_GLOBAL_ACCESS_POLICIES",
        "COMPUTE_RESOURCE_REGISTRY",
    ]
    counts = {}
    for table in tables:
        try:
            counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        except sqlite3.OperationalError:
            counts[table] = "missing"
    return counts


def make_report():
    seed_defaults()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_id = "READINESS_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    with connect_db() as conn:
        counts = collect_counts(conn)
        queue_status = conn.execute(
            "SELECT status, COUNT(*) FROM LOGIC_BLOCKCHAIN_QUEUE GROUP BY status ORDER BY status"
        ).fetchall()
        replicas = conn.execute(
            "SELECT replica_id, role, trust_mode, sync_mode, status, base_url FROM SHA256_LEDGER_REPLICAS ORDER BY replica_id"
        ).fetchall()
        policies = conn.execute(
            "SELECT policy_id, route, approval_required FROM AGENT_GLOBAL_ACCESS_POLICIES ORDER BY policy_id"
        ).fetchall()

    missing = [table for table, count in counts.items() if count == "missing"]
    readiness_status = "ready_for_endpoint_resync" if not missing else "needs_schema_repair"
    summary = (
        "Global ledger sync base is ready for hash-metadata redundancy and agent access contracts."
        if not missing
        else "Some required tables are missing; run migration before resync."
    )
    report = {
        "report_id": report_id,
        "created_at": now_iso(),
        "readiness_status": readiness_status,
        "summary": summary,
        "counts": counts,
        "queue_status": queue_status,
        "replicas": replicas,
        "agent_access_policies": policies,
        "next_endpoint_fields_needed": [
            "stable non-local base_url",
            "uplink_url for hash block POST",
            "ledger_url for reconciliation",
            "auth token or signed challenge format, if desired",
            "raw payload policy: hashes only by default",
        ],
    }
    report_path = REPORT_DIR / f"{report_id}.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    with connect_db() as conn:
        conn.execute(
            """
            INSERT INTO LEDGER_SYNC_READINESS_REPORTS (
                report_id, report_path, readiness_status, summary
            )
            VALUES (?, ?, ?, ?)
            """,
            (report_id, str(report_path), readiness_status, summary),
        )
    return report


def main():
    parser = argparse.ArgumentParser(description="Prepare VIPER SHA-256 ledger redundancy and global agent access contracts.")
    parser.add_argument("command", choices=["migrate", "seed", "report"])
    args = parser.parse_args()
    if args.command == "migrate":
        migrate()
        print("LEDGER_SYNC_TABLES_READY")
    elif args.command == "seed":
        seed_defaults()
        print("LEDGER_SYNC_DEFAULTS_SEEDED")
    elif args.command == "report":
        print(json.dumps(make_report(), indent=2))


if __name__ == "__main__":
    main()
