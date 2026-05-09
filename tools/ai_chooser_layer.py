import argparse
import hashlib
import json
import sqlite3
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


HOME = Path(r"C:\Users\viper")
DB_PATH = HOME / "gemini_bridge.db"
ROOT = HOME / "VIPER_JAVA_RISC"
TOOLS_DIR = ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
HOUSE_URL = "http://127.0.0.1:11435/api/generate"

try:
    from tiny_model_runtime import tiny_generate

    HAS_TINY_RUNTIME = True
except Exception as tiny_import_error:
    HAS_TINY_RUNTIME = False
    TINY_IMPORT_ERROR = str(tiny_import_error)


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def connect_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    conn.row_factory = sqlite3.Row
    return conn


def migrate(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS AI_CHOOSER_REVIEWS (
            review_id TEXT PRIMARY KEY,
            ask_sha256 TEXT NOT NULL,
            lens_id TEXT NOT NULL,
            template_id TEXT,
            route TEXT NOT NULL,
            draft_lens_sha256 TEXT NOT NULL,
            reviewed_lens_sha256 TEXT,
            review_status TEXT NOT NULL DEFAULT 'queued',
            review_json TEXT NOT NULL DEFAULT '{}',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            reviewed_at DATETIME
        );

        CREATE TABLE IF NOT EXISTS AI_CHOOSER_ACTIVE_LENSES (
            active_id TEXT PRIMARY KEY,
            review_id TEXT NOT NULL,
            lens_id TEXT NOT NULL,
            route TEXT NOT NULL,
            reviewed_lens_text TEXT NOT NULL,
            reviewed_lens_sha256 TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_ai_chooser_reviews_status ON AI_CHOOSER_REVIEWS(review_status);
        CREATE INDEX IF NOT EXISTS idx_ai_chooser_active_route ON AI_CHOOSER_ACTIVE_LENSES(route, status);
        """
    )


def house_generate(prompt, system, route="planning", timeout=35):
    payload = json.dumps({
        "prompt": prompt,
        "system": system,
        "route": route,
        "max_tokens": 512,
        "temperature": 0.2,
        "top_p": 0.85,
        "repeat_penalty": 1.08,
    }).encode("utf-8")
    req = urllib.request.Request(
        HOUSE_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            data = json.loads(res.read().decode("utf-8"))
            return data.get("response", "").strip(), data.get("meta", {})
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        return "", {"error": str(e)}


def deterministic_rewrite(route, draft_lens):
    lines = []
    keep_markers = (
        "VIPER FABRIC LENS",
        "route:",
        "token_limit:",
        "template_sha256:",
        "BUILD ROUTE:",
        "PLANNING ROUTE:",
        "CHAT ROUTE:",
        "SUCCESSFUL CODE / LEDGER HOOKS:",
        "OUTPUT RULES:",
    )
    for line in draft_lens.splitlines():
        if any(marker in line for marker in keep_markers):
            lines.append(line)
        elif line.startswith("C") and " sha=" in line:
            lines.append(line[:260])
        elif line.startswith("- "):
            lines.append(line)
    if not lines:
        lines = draft_lens.splitlines()[:40]
    header = [
        "AI CHOOSER REVIEWED FABRIC LENS",
        f"route: {route}",
        "chooser_contract: reduce noise, preserve safety, prefer successful code, clarify topology.",
        "retrieval_contract: query DB first, then successful-code ledger, then research/webcrawl only for missing facts.",
        "research_contract: summarize to claims + source hash + applicability + risk before model use.",
        "visible_reasoning: concise rationale only; no hidden chain-of-thought.",
        "",
        "RETRIEVAL ORDER:",
        "1. USER_TOPOLOGY_PROFILE and recent CHAT_MEMORY summary.",
        "2. TRIPLET_MANIFOLD, RAG_MANIFOLD, TOPO_CHUNKS, TOPO_APPROVAL_REPORTS.",
        "3. For build: CODE_BLOCKCHAIN_DB, BLOCKCHAIN_LEDGER, shipped LOGIC_BLOCKCHAIN_QUEUE, TOPO_CANDIDATES.",
        "4. WEBCRAWL_RESEARCH_REQUESTS only when local DB does not answer the missing fact.",
        "",
    ]
    return "\n".join(header + lines[:80])


def qwen_rewrite(route, draft_lens, real_data):
    if not HAS_TINY_RUNTIME:
        return "", {"error": globals().get("TINY_IMPORT_ERROR", "tiny runtime unavailable")}
    system = (
        "You are VIPER's real Qwen chooser. Rewrite the draft Fabric lens into "
        "one active point-form operating lens. Use real DB data. Keep <=100 words. "
        "Include purpose, fabric layer, retrieval, action/response instruction, and safety gate."
    )
    prompt = (
        f"Route: {route}\n"
        f"Real data:\n{json.dumps(real_data, ensure_ascii=True, indent=2)[:5000]}\n\n"
        f"Draft lens:\n{draft_lens[:5000]}\n\n"
        "Return only the active lens bullets."
    )
    result = tiny_generate("chooser", system, prompt, max_tokens=180, temperature=0.12)
    if result["ok"]:
        return result["text"].strip(), result["meta"]
    return "", result["meta"]


def review_one(conn):
    migrate(conn)
    row = conn.execute(
        """
        SELECT r.review_id, r.ask_sha256, r.lens_id, r.template_id, r.route,
               r.draft_lens_sha256, f.lens_text, f.sources_json
        FROM AI_CHOOSER_REVIEWS r
        JOIN FABRIC_LENSES f ON f.lens_id = r.lens_id
        WHERE r.review_status = 'queued'
        ORDER BY r.created_at ASC
        LIMIT 1
        """
    ).fetchone()
    if not row:
        return None

    draft_lens = row["lens_text"]
    real_data = build_real_data_bundle(conn, row)
    system = (
        "You are VIPER's local AI chooser. Rewrite the Fabric lens into a cleaner "
        "topological operating prompt. Keep route, safety gates, successful-code "
        "preference, DB retrieval, research/webcrawl noise reduction, and approval "
        "gates. The reviewed lens must say: DB retrieval first, successful-code "
        "retrieval for build, research only for missing facts, and reduce research "
        "to claims + source hash + applicability + risk. Be concise."
    )
    prompt = (
        "Rewrite this draft Fabric lens using the REAL RETRIEVED DATA bundle. "
        "Return only the reviewed lens text.\n\n"
        "[REAL_RETRIEVED_DATA]\n"
        + json.dumps(real_data, ensure_ascii=True, indent=2)[:5000]
        + "\n\n[DRAFT_FABRIC_LENS]\n"
        + draft_lens[:6000]
    )
    ai_text, meta = qwen_rewrite(row["route"], draft_lens, real_data)
    chooser_mode = "qwen2_5"
    if not ai_text:
        ai_text, meta = house_generate(prompt, system, route=row["route"], timeout=40)
        chooser_mode = "house_fallback"
    if not ai_text or ai_text.startswith("[HOUSE_ERROR]"):
        reviewed = deterministic_rewrite(row["route"], draft_lens)
        status = "reviewed_deterministic_fallback"
    else:
        reviewed = ai_text
        status = "reviewed_by_real_qwen" if chooser_mode == "qwen2_5" else "reviewed_by_local_ai"

    reviewed_sha = sha256_text(reviewed)
    review_json = {
        "status": status,
        "house_meta": meta,
        "chooser_mode": chooser_mode,
        "draft_sha256": row["draft_lens_sha256"],
        "reviewed_sha256": reviewed_sha,
        "real_data_sha256": sha256_text(json.dumps(real_data, ensure_ascii=True, sort_keys=True)),
        "rules": [
            "preserve route",
            "preserve safety gates",
            "reduce noise",
            "prefer successful code/ledger",
            "keep webcrawl summarized",
        ],
    }
    conn.execute(
        """
        UPDATE AI_CHOOSER_REVIEWS
        SET reviewed_lens_sha256 = ?, review_status = ?, review_json = ?, reviewed_at = CURRENT_TIMESTAMP
        WHERE review_id = ?
        """,
        (reviewed_sha, status, json.dumps(review_json, ensure_ascii=True, sort_keys=True), row["review_id"]),
    )
    conn.execute(
        """
        INSERT INTO AI_CHOOSER_ACTIVE_LENSES (
            active_id, review_id, lens_id, route, reviewed_lens_text, reviewed_lens_sha256
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            "ACTIVE_CHOOSER_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + reviewed_sha[:10],
            row["review_id"],
            row["lens_id"],
            row["route"],
            reviewed,
            reviewed_sha,
        ),
    )
    return {
        "review_id": row["review_id"],
        "lens_id": row["lens_id"],
        "route": row["route"],
        "status": status,
        "reviewed_lens_sha256": reviewed_sha,
        "preview": reviewed[:500],
    }


def rows_as_dicts(rows):
    return [dict(row) for row in rows]


def safe_json_loads(text, fallback):
    try:
        return json.loads(text or "")
    except Exception:
        return fallback


def build_real_data_bundle(conn, review_row):
    sources = safe_json_loads(review_row["sources_json"], {})
    profile = conn.execute(
        """
        SELECT chat_count, condensed_context, preferences_json, active_goals_json,
               predictive_terms_json, profile_sha256, updated_at
        FROM USER_TOPOLOGY_PROFILE
        WHERE profile_id = 'VIPER_USER_TOPOLOGY_V1'
        """
    ).fetchone()
    benchmarks = conn.execute(
        """
        SELECT component, operation, route, duration_ms, status, details_json, created_at
        FROM BENCHMARK_EVENTS
        ORDER BY created_at DESC
        LIMIT 5
        """
    ).fetchall()
    research = conn.execute(
        """
        SELECT request_id, route, query_json, noise_policy_json, status, created_at
        FROM WEBCRAWL_RESEARCH_REQUESTS
        WHERE ask_sha256 = ?
        ORDER BY created_at DESC
        LIMIT 3
        """,
        (review_row["ask_sha256"],),
    ).fetchall()
    active_code = conn.execute(
        """
        SELECT code_block_id, source_queue_id, payload_sha256, chain_hash, storage_role, pushed_at
        FROM CODE_BLOCKCHAIN_DB
        ORDER BY pushed_at DESC
        LIMIT 5
        """
    ).fetchall()
    topo_candidates = conn.execute(
        """
        SELECT id, chunk_id, candidate_sha256, comparison_count, confidence, action, created_at
        FROM TOPO_CANDIDATES
        ORDER BY created_at DESC
        LIMIT 5
        """
    ).fetchall()

    return {
        "review_id": review_row["review_id"],
        "lens_id": review_row["lens_id"],
        "route": review_row["route"],
        "sources_json": sources,
        "user_topology": dict(profile) if profile else None,
        "recent_benchmarks": rows_as_dicts(benchmarks),
        "research_requests": rows_as_dicts(research),
        "recent_code_blocks": rows_as_dicts(active_code),
        "recent_topo_candidates": rows_as_dicts(topo_candidates),
    }


def process(limit=1):
    reviewed = []
    with connect_db() as conn:
        migrate(conn)
        for _ in range(limit):
            item = review_one(conn)
            if not item:
                break
            reviewed.append(item)
        conn.commit()
    return reviewed


def main():
    parser = argparse.ArgumentParser(description="Local AI chooser layer for VIPER Fabric lenses.")
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    reviewed = process(args.limit)
    if args.json:
        print(json.dumps({"reviewed": reviewed}, ensure_ascii=True, indent=2))
    else:
        print(f"AI_CHOOSER reviewed={len(reviewed)}")


if __name__ == "__main__":
    main()
