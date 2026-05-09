import argparse
import hashlib
import json
import re
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\Users\viper\VIPER_JAVA_RISC")
HOME = Path(r"C:\Users\viper")
DB_PATH = HOME / "gemini_bridge.db"
SHIPPER_LOG = ROOT / "logic_blockchain_shipper.log"
REPORT_DIR = ROOT / "security_reports"

KNOWN_LOCAL = {"127.0.0.1", "0.0.0.0", "::1", "[::]"}
INTERESTING_PATHS = {
    "/api/ask": "unknown_agent_api_probe",
    "/.well-known/agent.json": "agent_discovery_probe",
}


def now_id():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def connect_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def migrate(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS NETWORK_SECURITY_EVENTS (
            event_id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            severity INTEGER NOT NULL,
            heuristic_score REAL NOT NULL,
            details_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'observed',
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

        CREATE TABLE IF NOT EXISTS SECURITY_SENTINEL_SEEN (
            fingerprint TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            details_json TEXT NOT NULL,
            first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
            seen_count INTEGER NOT NULL DEFAULT 1
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

        CREATE INDEX IF NOT EXISTS idx_security_severity ON NETWORK_SECURITY_EVENTS(severity);
        CREATE INDEX IF NOT EXISTS idx_todo_status_priority ON GLOBAL_TODO_QUEUE(status, priority);
        """
    )


def insert_once(conn, event_type, severity, heuristic_score, details):
    payload = json.dumps(details, ensure_ascii=True, sort_keys=True)
    fingerprint_basis = {
        "event_type": event_type,
        "ip": details.get("ip"),
        "method": details.get("method"),
        "path": str(details.get("path") or "").split("?")[0],
        "status": details.get("status"),
        "local_port": details.get("local_port"),
        "remote_address": details.get("remote_address"),
        "remote_port": details.get("remote_port"),
        "source": details.get("source"),
    }
    fingerprint = sha256_text(json.dumps(fingerprint_basis, ensure_ascii=True, sort_keys=True))
    row = conn.execute(
        "SELECT seen_count FROM SECURITY_SENTINEL_SEEN WHERE fingerprint = ?",
        (fingerprint,),
    ).fetchone()
    if row:
        conn.execute(
            """
            UPDATE SECURITY_SENTINEL_SEEN
            SET seen_count = seen_count + 1, last_seen = CURRENT_TIMESTAMP
            WHERE fingerprint = ?
            """,
            (fingerprint,),
        )
        return False, fingerprint

    event_id = f"SEC_{now_id()}_{fingerprint[:12]}"
    todo_id = f"TODO_SECURITY_{now_id()}_{fingerprint[:12]}"
    acl_id = f"ACL_SECURITY_{now_id()}_{fingerprint[:12]}"
    conn.execute(
        """
        INSERT INTO SECURITY_SENTINEL_SEEN (
            fingerprint, event_type, details_json
        )
        VALUES (?, ?, ?)
        """,
        (fingerprint, event_type, payload),
    )
    conn.execute(
        """
        INSERT INTO NETWORK_SECURITY_EVENTS (
            event_id, event_type, severity, heuristic_score, details_json, status
        )
        VALUES (?, ?, ?, ?, ?, 'observed_round_robin_requested')
        """,
        (event_id, event_type, severity, heuristic_score, payload),
    )
    conn.execute(
        """
        INSERT INTO GLOBAL_TODO_QUEUE (
            todo_id, title, details, priority, status, assigned_agent, proof_required
        )
        VALUES (?, ?, ?, ?, 'open', 'round_robin_security', 1)
        """,
        (
            todo_id,
            f"Investigate security event: {event_type}",
            payload,
            max(1, min(3, severity)),
        ),
    )
    conn.execute(
        """
        INSERT INTO GLOBAL_ACL_MESSAGES (
            message_id, sender, receiver, performative, content,
            content_sha256, route, status
        )
        VALUES (?, 'security_sentinel', 'round_robin_security', 'request', ?, ?, 'security_investigate', 'open')
        """,
        (
            acl_id,
            json.dumps({
                "action": "investigate",
                "event_id": event_id,
                "todo_id": todo_id,
                "event_type": event_type,
                "details": details,
                "rules": [
                    "observe first",
                    "do not block",
                    "do not mutate firewall",
                    "return proof and recommendation",
                ],
            }, ensure_ascii=True, sort_keys=True),
            sha256_text(payload),
        ),
    )
    return True, fingerprint


def parse_shipper_log(limit_lines):
    events = []
    if not SHIPPER_LOG.exists():
        return events
    lines = SHIPPER_LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-limit_lines:]
    pattern = re.compile(r"\[(?P<ts>[^\]]+)\]\s+(?P<ip>\S+)\s+\"(?P<method>\S+)\s+(?P<path>\S+)\s+HTTP/[^\"]+\"\s+(?P<status>\d+)")
    for line in lines:
        match = pattern.search(line)
        if not match:
            continue
        item = match.groupdict()
        path = item["path"].split("?")[0]
        status = int(item["status"])
        if path in INTERESTING_PATHS:
            events.append({
                "event_type": INTERESTING_PATHS[path],
                "severity": 2,
                "heuristic_score": 0.72,
                "details": {
                    "source": "logic_blockchain_shipper.log",
                    "timestamp": item["ts"],
                    "ip": item["ip"],
                    "method": item["method"],
                    "path": item["path"],
                    "status": status,
                    "interpretation": "new agent/network surface probe",
                },
            })
        elif status == 404 and path.startswith("/logic/block/"):
            events.append({
                "event_type": "unknown_logic_block_lookup",
                "severity": 2,
                "heuristic_score": 0.64,
                "details": {
                    "source": "logic_blockchain_shipper.log",
                    "timestamp": item["ts"],
                    "ip": item["ip"],
                    "method": item["method"],
                    "path": item["path"],
                    "status": status,
                    "interpretation": "agent attempted to fetch a block id that is not exposed",
                },
            })
        elif status >= 400 and path not in {"/"}:
            events.append({
                "event_type": "http_error_surface",
                "severity": 3,
                "heuristic_score": 0.45,
                "details": {
                    "source": "logic_blockchain_shipper.log",
                    "timestamp": item["ts"],
                    "ip": item["ip"],
                    "method": item["method"],
                    "path": item["path"],
                    "status": status,
                },
            })
    return events


def snapshot_connections():
    events = []
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-NetTCPConnection | Select-Object LocalAddress,LocalPort,RemoteAddress,RemotePort,State,OwningProcess | ConvertTo-Json -Compress"],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return events
        data = json.loads(proc.stdout)
        if isinstance(data, dict):
            data = [data]
        for conn in data:
            remote = str(conn.get("RemoteAddress") or "")
            state = str(conn.get("State") or "")
            local_port = int(conn.get("LocalPort") or 0)
            if not remote or remote in KNOWN_LOCAL or remote.startswith("0.0.0.0"):
                continue
            if state not in {"Established", "SynReceived"}:
                continue
            if local_port not in {8080, 18081, 11435, 18181}:
                continue
            events.append({
                "event_type": "new_tcp_peer_on_viper_port",
                "severity": 2,
                "heuristic_score": 0.67,
                "details": {
                    "source": "Get-NetTCPConnection",
                    "local_port": local_port,
                    "remote_address": remote,
                    "remote_port": conn.get("RemotePort"),
                    "state": state,
                    "owning_process": conn.get("OwningProcess"),
                    "interpretation": "non-local peer connected to watched VIPER service port",
                },
            })
    except Exception as e:
        events.append({
            "event_type": "security_sentinel_scan_error",
            "severity": 3,
            "heuristic_score": 0.25,
            "details": {"error": str(e), "source": "Get-NetTCPConnection"},
        })
    return events


def run_scan(limit_lines=500):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    events = parse_shipper_log(limit_lines) + snapshot_connections()
    inserted = []
    repeated = 0
    with connect_db() as conn:
        migrate(conn)
        for event in events:
            fresh, fingerprint = insert_once(
                conn,
                event["event_type"],
                event["severity"],
                event["heuristic_score"],
                event["details"],
            )
            if fresh:
                inserted.append({"fingerprint": fingerprint, **event})
            else:
                repeated += 1
        conn.commit()
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "events_seen": len(events),
        "new_events": len(inserted),
        "repeated_events": repeated,
        "inserted": inserted,
    }
    report_path = REPORT_DIR / f"security_scan_{now_id()}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")
    return report_path, report


def main():
    parser = argparse.ArgumentParser(description="Passive VIPER network security sentinel.")
    parser.add_argument("--limit-lines", type=int, default=500)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    path, report = run_scan(args.limit_lines)
    report["report_path"] = str(path)
    if args.json:
        print(json.dumps(report, ensure_ascii=True, indent=2))
    else:
        print(f"SECURITY_SENTINEL new={report['new_events']} repeated={report['repeated_events']} report={path}")


if __name__ == "__main__":
    main()
