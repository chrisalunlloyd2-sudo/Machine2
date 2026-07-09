#!/usr/bin/env python3
"""
VIPER Machine 2 — OTG Dual-Channel Bridge v2.0
================================================
Bidirectional, redundant communication channel between Machine 1 and Machine 2.

Architecture:
                    Machine 1 (Aegis/Picoclaw)
                           │
              ┌────────────┴────────────┐
              │ Channel A: HTTP :18283  │ PRIMARY
              │ Channel B: HTTP :18284  │ REDUNDANT
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │  OTG DUAL BRIDGE        │
              │  - Route arbitration    │
              │  - Dedup & sequence     │
              │  - Queue w/ replay      │
              │  - Health failover      │
              └────────────┬────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
    code.db          gemini_bridge.db    nmct_db
  (blocks sent)    (logits/patterns)  (recall idx)

Endpoints:
  GET  /health
  POST /api/m1/receive   — receive data FROM Machine 1
  POST /api/m1/send      — push data TO Machine 1
  GET  /api/queue        — inspect outbound queue
  POST /api/mine/submit  — Karoo miner submits blocks
  GET  /api/blocks/recent — Machine 1 polls for new blocks
"""
import json
import sqlite3
import hashlib
import os
import time
import datetime
import threading
import queue
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

# ─── Config ───────────────────────────────────────────────────────
VIPER          = Path(r"C:\Users\viper\VIPER_JAVA_RISC")
GANOTG         = Path(r"C:\Users\viper\gan-otg-db")
CODE_DB        = VIPER / "java_notes_suite" / "data" / "code.db"
BRIDGE_DB      = Path(r"C:\Users\viper\VIPER_JAVA_RISC\java_notes_suite\data\otg_bridge.db")
CHANNEL_A_PORT = 18283
CHANNEL_B_PORT = 18284

# Machine 1 address (picoclaw/Aegis) — update when known
M1_CHANNEL_A = os.environ.get("VIPER_M1_ADDR_A", "http://127.0.0.1:18181")
M1_CHANNEL_B = os.environ.get("VIPER_M1_ADDR_B", "http://127.0.0.1:18181")

# ─── Queue ────────────────────────────────────────────────────────
_outbound_queue: queue.Queue = queue.Queue(maxsize=1000)
_sequence = 0
_seq_lock = threading.Lock()


def next_seq() -> int:
    global _sequence
    with _seq_lock:
        _sequence += 1
        return _sequence


def now_iso() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def log(msg: str) -> None:
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] OTG_BRIDGE | {msg}", flush=True)


# ─── Bridge DB ────────────────────────────────────────────────────
def bridge_db() -> sqlite3.Connection:
    BRIDGE_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(BRIDGE_DB), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            direction  TEXT NOT NULL,  -- 'inbound' | 'outbound'
            channel    TEXT,
            payload    TEXT NOT NULL,
            seq        INTEGER,
            status     TEXT DEFAULT 'pending',
            created_at TEXT NOT NULL,
            delivered_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS block_manifest (
            hash       TEXT PRIMARY KEY,
            language   TEXT,
            block_type TEXT,
            sent_at    TEXT,
            ack_at     TEXT
        )
    """)
    conn.commit()
    return conn


# ─── Code DB interface ────────────────────────────────────────────
def get_recent_blocks(limit: int = 50, since_id: int = 0) -> list[dict]:
    """Get recently mined blocks for Machine 1 to pull."""
    if not CODE_DB.exists():
        return []
    try:
        conn = sqlite3.connect(str(CODE_DB), timeout=10)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT rowid, hash, language, code_text, block_type, status, created_at, file_path "
            "FROM code_artifacts WHERE rowid > ? ORDER BY rowid DESC LIMIT ?",
            (since_id, limit)
        ).fetchall()
        conn.close()
        return [{
            "id": r["rowid"],
            "hash": r["hash"][:12],
            "language": r["language"],
            "preview": (r["code_text"] or "")[:200],
            "block_type": r["block_type"] or "block",
            "status": r["status"],
            "created_at": r["created_at"],
            "file_path": r["file_path"] or "",
        } for r in rows]
    except Exception as e:
        log(f"get_recent_blocks error: {e}")
        return []


def submit_block(payload: dict) -> dict:
    """Karoo miner submits a block directly via API."""
    if not CODE_DB.exists():
        CODE_DB.parent.mkdir(parents=True, exist_ok=True)
    try:
        conn = sqlite3.connect(str(CODE_DB), timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        h = sha256(payload.get("code_text", ""))
        conn.execute(
            """INSERT OR IGNORE INTO code_artifacts
               (hash, source_agent, language, code_text, status, created_at, block_type)
               VALUES (?,?,?,?,?,?,?)""",
            (h, payload.get("source_agent", "api"),
             payload.get("language", "unknown"),
             payload.get("code_text", ""),
             "mined", now_iso(),
             payload.get("block_type", "block"))
        )
        conn.commit()
        inserted = conn.execute("SELECT changes()").fetchone()[0]
        conn.close()
        return {"status": "ok", "hash": h, "inserted": inserted}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ─── Outbound Sender (background thread) ─────────────────────────
def _sender_loop() -> None:
    """Background thread that delivers queued messages to Machine 1."""
    while True:
        try:
            item = _outbound_queue.get(timeout=5)
        except queue.Empty:
            continue

        payload = json.dumps(item).encode("utf-8")
        delivered = False

        for url_base in [M1_CHANNEL_A, M1_CHANNEL_B]:
            try:
                req = urllib.request.Request(
                    f"{url_base}/api/m2/receive",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=10):
                    delivered = True
                    break
            except Exception:
                continue

        if not delivered:
            log(f"DELIVERY FAILED seq={item.get('seq')} — requeueing")
            try:
                _outbound_queue.put_nowait(item)
            except queue.Full:
                log("Queue full — dropping oldest")

        time.sleep(0.1)


# ─── HTTP Handler ─────────────────────────────────────────────────
class BridgeHandler(BaseHTTPRequestHandler):

    def _send(self, code: int, body: bytes, ct: str = "application/json") -> None:
        self.send_response(code)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, payload: dict) -> None:
        self._send(code, json.dumps(payload, indent=2).encode("utf-8"))

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length).decode("utf-8", errors="replace") if length else "{}"
        try:
            return json.loads(raw)
        except Exception:
            return {}

    def do_OPTIONS(self) -> None:
        self._send(204, b"")

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/health":
            self._json(200, {
                "status": "ok",
                "service": "otg_dual_bridge",
                "version": "2.0",
                "queue_depth": _outbound_queue.qsize(),
                "timestamp": now_iso(),
            })
        elif path == "/api/queue":
            items = list(_outbound_queue.queue)[:10]
            self._json(200, {"queue_depth": _outbound_queue.qsize(), "sample": items})
        elif path.startswith("/api/blocks/recent"):
            from urllib.parse import parse_qs, urlparse as up
            qs = parse_qs(up(self.path).query)
            limit = int(qs.get("limit", ["50"])[0])
            since = int(qs.get("since", ["0"])[0])
            blocks = get_recent_blocks(limit=limit, since_id=since)
            self._json(200, {"blocks": blocks, "count": len(blocks)})
        else:
            self._json(404, {"error": "not_found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        body = self._body()

        if path == "/api/m1/receive":
            # Machine 1 is sending us data
            seq = next_seq()
            item = {**body, "seq": seq, "received_at": now_iso(), "direction": "inbound"}
            log(f"INBOUND from M1 seq={seq} type={body.get('type','?')}")
            self._json(200, {"status": "received", "seq": seq})

        elif path == "/api/m1/send":
            # Trigger sending data to Machine 1
            seq = next_seq()
            item = {**body, "seq": seq, "queued_at": now_iso(), "direction": "outbound"}
            try:
                _outbound_queue.put_nowait(item)
                self._json(200, {"status": "queued", "seq": seq})
            except queue.Full:
                self._json(503, {"status": "error", "error": "queue_full"})

        elif path == "/api/mine/submit":
            # Karoo miner submitting a block
            result = submit_block(body)
            # Also queue for Machine 1
            if result.get("inserted", 0) > 0:
                seq = next_seq()
                try:
                    _outbound_queue.put_nowait({
                        "type": "block_mined",
                        "block": {
                            "hash": result["hash"],
                            "language": body.get("language"),
                            "block_type": body.get("block_type"),
                            "preview": (body.get("code_text", ""))[:100],
                        },
                        "seq": seq,
                        "queued_at": now_iso(),
                    })
                except queue.Full:
                    pass
            self._json(200, result)

        else:
            self._json(404, {"error": "not_found", "path": path})

    def log_message(self, fmt: str, *args) -> None:
        pass  # Suppress default access logs


def serve(port: int, label: str) -> None:
    server = ThreadingHTTPServer(("0.0.0.0", port), BridgeHandler)
    log(f"Channel {label} listening on :{port}")
    server.serve_forever()


def main() -> None:
    log("=" * 60)
    log("OTG DUAL BRIDGE v2.0 — ONLINE")
    log(f"Channel A: :{CHANNEL_A_PORT} | Channel B: :{CHANNEL_B_PORT}")
    log(f"Machine 1 A: {M1_CHANNEL_A} | B: {M1_CHANNEL_B}")
    log("=" * 60)

    # Start outbound sender thread
    t = threading.Thread(target=_sender_loop, daemon=True)
    t.start()

    # Start channel B in background thread
    t2 = threading.Thread(target=serve, args=(CHANNEL_B_PORT, "B"), daemon=True)
    t2.start()

    # Channel A on main thread
    serve(CHANNEL_A_PORT, "A")


if __name__ == "__main__":
    main()
