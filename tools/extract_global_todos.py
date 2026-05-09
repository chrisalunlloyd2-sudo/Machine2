from __future__ import annotations

import json
import random
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\Users\viper\VIPER_JAVA_RISC")
HOME = Path(r"C:\Users\viper")
DB_PATH = HOME / "gemini_bridge.db"
TODO_RE = re.compile(r"(?i)\b(todo|to do|need to|needs to|should|can you|make sure|next step|goal:|we have to|please)\b.{0,260}")


SEED_TODOS = [
    "Ping agents and establish resource/offload connections using heartbeat and ACL.",
    "Build Java notes/dev/script suite and keep it merge-only, append-only, and phone-hostable.",
    "Extract TODOs from local chats, handoffs, logs, and agent memory into GLOBAL_TODO_QUEUE.",
    "Solidify Karoo GPT as the app-development prompt-to-code suite with verifier approval.",
    "Keep Loihi sparse sidecar learning-shaped, evidence-logged, and proposal-only until real learning rules are proven.",
    "On agent announce, run heartbeat, quick-look, resource-fit install check, and capability broadcast.",
    "Optimize each agent for its environment: speed, stability, tools, and safe addons.",
    "Round-robin agent discussion should remove stale slow parts and propose simplifications.",
    "Daily webcrawl round: each agent proposes ten agentic upgrades, then route for editing and user approval.",
    "Phones should be treated as quick DB lend/memory nodes before heavy compute nodes.",
    "Laptops should focus on research, networking, verification, and routing.",
]


def now_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
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
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_todo_status_priority ON GLOBAL_TODO_QUEUE(status, priority)")


def read_sources() -> list[tuple[str, str]]:
    sources: list[tuple[str, str]] = []
    for path in [
        HOME / "HANDOFF_CODEX.txt",
        ROOT / "README.md",
        ROOT / "PROJECT_SNAPSHOT_ASCII.md",
        ROOT / "system_log.txt",
        ROOT / "topology_sidecar_loop.log",
    ]:
        if path.exists():
            try:
                sources.append((str(path), path.read_text(encoding="utf-8", errors="replace")[-120000:]))
            except OSError:
                pass
    try:
        with connect() as conn:
            for table, columns in [
                ("CHAT_MEMORY", "user_message || ' ' || ai_response"),
                ("RAG_MANIFOLD", "message || ' ' || feedback_type"),
                ("GLOBAL_ACL_MESSAGES", "content"),
                ("TOPO_APPROVAL_REPORTS", "summary || ' ' || details_json"),
            ]:
                try:
                    rows = conn.execute(f"SELECT {columns} FROM {table} ORDER BY rowid DESC LIMIT 200").fetchall()
                    sources.append((f"db:{table}", "\n".join(str(row[0]) for row in rows if row and row[0])))
                except sqlite3.Error:
                    continue
    except sqlite3.Error:
        pass
    return sources


def extract_candidates() -> list[dict[str, str]]:
    items = [{"title": seed, "source": "current_thread_seed"} for seed in SEED_TODOS]
    for source, text in read_sources():
        for match in TODO_RE.finditer(text):
            title = re.sub(r"\s+", " ", match.group(0)).strip(" -:*#\t\r\n")
            if 18 <= len(title) <= 220:
                items.append({"title": title, "source": source})
    dedup: dict[str, dict[str, str]] = {}
    for item in items:
        lowered = item["title"].lower()
        if lowered in {"please and thank you! like", "please and thank you! dislike"}:
            continue
        if len(lowered.split()) < 5 and item["source"] != "current_thread_seed":
            continue
        key = re.sub(r"[^a-z0-9]+", " ", item["title"].lower()).strip()[:140]
        if key and key not in dedup:
            dedup[key] = item
    result = list(dedup.values())
    random.Random(now_id()).shuffle(result)
    return result[:80]


def insert_todos(items: list[dict[str, str]]) -> dict[str, object]:
    agents = ["local_viper_control", "karoo_gpt_sidecar", "sha256_ledger_shipper", "loihi_sparse_sidecar"]
    inserted = []
    skipped = 0
    with connect() as conn:
        migrate(conn)
        existing_titles = {
            row[0].lower()
            for row in conn.execute("SELECT title FROM GLOBAL_TODO_QUEUE").fetchall()
        }
        for index, item in enumerate(items, start=1):
            title = item["title"][:180]
            if title.lower() in existing_titles:
                skipped += 1
                continue
            todo_id = f"TODO_EXTRACT_{now_id()}_{index:03d}"
            assigned = agents[(index - 1) % len(agents)]
            details = json.dumps({"source": item["source"], "random_pick_order": index}, sort_keys=True)
            conn.execute(
                """
                INSERT INTO GLOBAL_TODO_QUEUE (
                    todo_id, title, details, priority, assigned_agent
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (todo_id, title, details, 2, assigned),
            )
            inserted.append({"todo_id": todo_id, "title": title, "assigned_agent": assigned})
        conn.commit()
    return {"inserted_count": len(inserted), "skipped_existing": skipped, "inserted": inserted[:25]}


def main() -> int:
    print(json.dumps(insert_todos(extract_candidates()), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
