import argparse
import hashlib
import importlib.util
import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\Users\viper\VIPER_JAVA_RISC")
HOME = Path(r"C:\Users\viper")
DB_PATH = HOME / "gemini_bridge.db"
REPORT_DIR = ROOT / "loihi_spike_reports"
CUBE_SIZE = 100


def now_id():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def connect_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def hex_coord(hex_hash):
    x = int(hex_hash[0:4], 16) % CUBE_SIZE
    y_raw = int(hex_hash[4:8], 16) % CUBE_SIZE
    z = int(hex_hash[8:12], 16) % CUBE_SIZE
    polarity = 1 if y_raw >= 50 else -1
    amplitude = abs(y_raw - 50) / 50.0
    return x, y_raw, z, polarity, round(amplitude, 4)


def migrate():
    with connect_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS LOIHI_TOPO_CODES (
                code_id TEXT PRIMARY KEY,
                source_table TEXT NOT NULL,
                source_id TEXT NOT NULL,
                code_type TEXT NOT NULL,
                label TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                x INTEGER NOT NULL,
                y INTEGER NOT NULL,
                z INTEGER NOT NULL,
                polarity INTEGER NOT NULL,
                base_amplitude REAL NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS LOIHI_LINKS (
                link_id TEXT PRIMARY KEY,
                from_code_id TEXT NOT NULL,
                to_code_id TEXT NOT NULL,
                weight REAL NOT NULL,
                relation_type TEXT NOT NULL,
                confidence REAL NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS LOIHI_SPIKE_EXPERIMENTS (
                experiment_id TEXT PRIMARY KEY,
                input_hash TEXT NOT NULL,
                steps INTEGER NOT NULL,
                seed_count INTEGER NOT NULL,
                output_hash TEXT NOT NULL,
                report_path TEXT NOT NULL,
                summary TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS LOIHI_SPIKE_EVENTS (
                event_id TEXT PRIMARY KEY,
                experiment_id TEXT NOT NULL,
                step INTEGER NOT NULL,
                code_id TEXT NOT NULL,
                amplitude REAL NOT NULL,
                polarity INTEGER NOT NULL,
                packet_hash TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS LOIHI_BACKEND_MANIFESTS (
                manifest_id TEXT PRIMARY KEY,
                experiment_id TEXT,
                requested_backend TEXT NOT NULL,
                selected_backend TEXT NOT NULL,
                lava_available INTEGER NOT NULL,
                loihi_hardware_available INTEGER NOT NULL DEFAULT 0,
                manifest_sha256 TEXT NOT NULL,
                manifest_json TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_loihi_codes_type ON LOIHI_TOPO_CODES(code_type);
            CREATE INDEX IF NOT EXISTS idx_loihi_links_from ON LOIHI_LINKS(from_code_id);
            CREATE INDEX IF NOT EXISTS idx_loihi_events_experiment ON LOIHI_SPIKE_EVENTS(experiment_id);
            CREATE INDEX IF NOT EXISTS idx_loihi_backend_experiment ON LOIHI_BACKEND_MANIFESTS(experiment_id);
            """
        )


def lava_available():
    return importlib.util.find_spec("lava") is not None


def lava_backend_manifest(requested_backend, selected_backend, experiment_id=None, graph_spec=None, reason=None, conn=None):
    manifest = {
        "schema": "VIPER_LOIHI_BACKEND_MANIFEST_V1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "experiment_id": experiment_id,
        "requested_backend": requested_backend,
        "selected_backend": selected_backend,
        "lava_available": lava_available(),
        "loihi_hardware_available": False,
        "reason": reason,
        "backend_contract": {
            "top_code_source": "LOIHI_TOPO_CODES",
            "edge_source": "LOIHI_LINKS",
            "input_encoding": "seed code amplitudes from NLP/top-code prompt match",
            "runtime_default": "sparse_python_cpu",
            "lava_target": {
                "processes": ["lava.proc.dense.Dense", "lava.proc.lif.LIF"],
                "run_condition": "RunSteps(num_steps=steps)",
                "cpu_run_config": "Loihi1SimCfg or compatible CPU ProcessModel",
                "hardware_run_config": "Loihi2HwCfg when Intel Loihi extension/hardware access exists",
            },
        },
        "graph_spec": graph_spec or {},
        "policy": {
            "learning_only": True,
            "no_code_mutation": True,
            "approval_required_for_any_patch": True,
        },
    }
    manifest_json = json.dumps(manifest, indent=2, sort_keys=True)
    manifest_hash = sha256_text(manifest_json)
    manifest_id = f"LBE_{now_id()}_{manifest_hash[:12]}"
    def insert(target_conn):
        target_conn.execute(
                """
                INSERT INTO LOIHI_BACKEND_MANIFESTS (
                    manifest_id, experiment_id, requested_backend, selected_backend,
                    lava_available, loihi_hardware_available, manifest_sha256, manifest_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    manifest_id,
                    experiment_id,
                    requested_backend,
                    selected_backend,
                    1 if manifest["lava_available"] else 0,
                    0,
                    manifest_hash,
                    manifest_json,
                ),
            )
    if conn is None:
        with connect_db() as own_conn:
            insert(own_conn)
    else:
        insert(conn)
    return manifest_id, manifest


def upsert_code(conn, source_table, source_id, code_type, label, body, metadata=None):
    digest = sha256_text("|".join([source_table, str(source_id), code_type, label, body or ""]))
    x, y, z, polarity, amplitude = hex_coord(digest)
    code_id = f"LCODE_{digest[:16]}"
    conn.execute(
        """
        INSERT OR IGNORE INTO LOIHI_TOPO_CODES (
            code_id, source_table, source_id, code_type, label, sha256,
            x, y, z, polarity, base_amplitude, metadata_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            code_id,
            source_table,
            str(source_id),
            code_type,
            label[:180],
            digest,
            x,
            y,
            z,
            polarity,
            amplitude,
            json.dumps(metadata or {}, sort_keys=True),
        ),
    )
    return code_id


def seed_codes(limit=80):
    migrate()
    created = 0
    with connect_db() as conn:
        rows = conn.execute(
            """
            SELECT id, subsystem_id, symbol, source_path, content_sha256
            FROM TOPO_CHUNKS
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        for row in rows:
            upsert_code(
                conn,
                "TOPO_CHUNKS",
                row[0],
                f"chunk:{row[1]}",
                row[2],
                "|".join(map(str, row)),
                {"source_path": row[3]},
            )
            created += 1

        rows = conn.execute(
            """
            SELECT id, type, label, description
            FROM TRIPLET_MANIFOLD
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        for row in rows:
            upsert_code(conn, "TRIPLET_MANIFOLD", row[0], f"logic:{row[1]}", row[2] or row[0], row[3] or "")
            created += 1

        rows = conn.execute(
            """
            SELECT id, message, feedback_type
            FROM RAG_MANIFOLD
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        for row in rows:
            code_type = "reward:like" if str(row[2]).lower() == "like" else "reward:dislike"
            upsert_code(conn, "RAG_MANIFOLD", row[0], code_type, row[2] or "feedback", row[1] or "")
            created += 1
    return created


def code_distance(a, b):
    dx = min(abs(a["x"] - b["x"]), CUBE_SIZE - abs(a["x"] - b["x"]))
    dy = abs(a["y"] - b["y"])
    dz = min(abs(a["z"] - b["z"]), CUBE_SIZE - abs(a["z"] - b["z"]))
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def rebuild_links(max_neighbors=5, max_distance=38.0):
    migrate()
    with connect_db() as conn:
        rows = conn.execute(
            """
            SELECT code_id, code_type, x, y, z, polarity, base_amplitude
            FROM LOIHI_TOPO_CODES
            """
        ).fetchall()
        codes = [
            {
                "id": row[0],
                "type": row[1],
                "x": row[2],
                "y": row[3],
                "z": row[4],
                "polarity": row[5],
                "amp": row[6],
            }
            for row in rows
        ]
        made = 0
        for code in codes:
            neighbors = []
            for other in codes:
                if other["id"] == code["id"]:
                    continue
                dist = code_distance(code, other)
                if dist <= max_distance:
                    neighbors.append((dist, other))
            neighbors.sort(key=lambda item: item[0])
            for dist, other in neighbors[:max_neighbors]:
                same_family = code["type"].split(":")[0] == other["type"].split(":")[0]
                polarity_factor = 1.0 if code["polarity"] == other["polarity"] else -0.72
                family_factor = 1.2 if same_family else 0.85
                weight = round((1.0 - (dist / max_distance)) * polarity_factor * family_factor, 5)
                if abs(weight) < 0.05:
                    continue
                relation = "near_same_family" if same_family else "near_cross_family"
                link_id = f"LLINK_{sha256_text(code['id'] + other['id'] + relation)[:18]}"
                conn.execute(
                    """
                    INSERT OR IGNORE INTO LOIHI_LINKS (
                        link_id, from_code_id, to_code_id, weight, relation_type, confidence
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (link_id, code["id"], other["id"], weight, relation, round(abs(weight), 4)),
                )
                made += 1
    return made


def choose_seed_codes(conn, prompt, limit):
    words = [word.lower() for word in prompt.split() if len(word) > 2]
    rows = conn.execute(
        """
        SELECT code_id, code_type, label, x, y, z, polarity, base_amplitude, sha256
        FROM LOIHI_TOPO_CODES
        """
    ).fetchall()
    scored = []
    for row in rows:
        haystack = f"{row[1]} {row[2]}".lower()
        lexical = sum(1 for word in words if word in haystack)
        hash_bias = int(row[8][0:4], 16) / 65535.0
        reward_bias = 0.35 if "like" in row[1] or "success" in row[1] else 0.0
        score = lexical * 1.25 + reward_bias + hash_bias * 0.1 + row[7]
        scored.append((score, row))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [row for _, row in scored[:limit]]


def build_lava_graph_spec(conn, seed_rows, max_nodes=64):
    seed_ids = [row[0] for row in seed_rows]
    rows = conn.execute(
        """
        SELECT code_id, code_type, label, x, y, z, polarity, base_amplitude
        FROM LOIHI_TOPO_CODES
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (max_nodes,),
    ).fetchall()
    code_ids = []
    seen = set()
    for row in seed_rows + rows:
        if row[0] not in seen:
            code_ids.append(row[0])
            seen.add(row[0])
    code_ids = code_ids[:max_nodes]
    index = {code_id: i for i, code_id in enumerate(code_ids)}
    links = conn.execute(
        """
        SELECT from_code_id, to_code_id, weight, relation_type
        FROM LOIHI_LINKS
        WHERE from_code_id IN ({})
        """.format(",".join("?" for _ in code_ids)),
        code_ids,
    ).fetchall() if code_ids else []
    weights = []
    for from_code_id, to_code_id, weight, relation in links:
        if from_code_id in index and to_code_id in index:
            weights.append(
                {
                    "from": index[from_code_id],
                    "to": index[to_code_id],
                    "weight": weight,
                    "relation": relation,
                }
            )
    seed_vector = [0.0 for _ in code_ids]
    for row in seed_rows:
        if row[0] in index:
            seed_vector[index[row[0]]] = row[7]
    return {
        "lava_compatible": True,
        "node_count": len(code_ids),
        "edge_count": len(weights),
        "code_index": [{"index": idx, "code_id": code_id} for code_id, idx in index.items()],
        "seed_vector": seed_vector,
        "weights_sparse_triplets": weights,
        "suggested_lava_process_graph": {
            "input": "seed_vector as spike/current source",
            "connection": "Dense(weights=dense_matrix_from_sparse_triplets)",
            "reservoir": "LIF(shape=(node_count,), du=..., dv=..., vth=...)",
            "monitor": "Monitor LIF.s_out or membrane voltage over RunSteps",
        },
    }


def select_backend(requested_backend):
    has_lava = lava_available()
    if requested_backend == "sparse-python":
        return "sparse_python_cpu", "requested sparse Python backend"
    if requested_backend == "lava":
        if has_lava:
            return "lava_export_ready", "Lava is importable; graph spec is emitted for Lava Process execution"
        return "sparse_python_cpu", "Lava requested but not installed; falling back without faking Lava execution"
    if requested_backend == "auto" and has_lava:
        return "lava_export_ready", "Lava detected; graph spec is emitted while sparse Python remains the verified runtime"
    return "sparse_python_cpu", "Lava not installed; verified sparse Python runtime selected"


def run_experiment(prompt, steps=6, seed_limit=12, backend="auto"):
    migrate()
    seed_codes()
    rebuild_links()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    experiment_id = f"LOIHI_EXP_{now_id()}_{sha256_text(prompt)[:10]}"
    input_hash = sha256_text(prompt)
    with connect_db() as conn:
        seed_rows = choose_seed_codes(conn, prompt, seed_limit)
        activations = {}
        for row in seed_rows:
            code_id, code_type, label, x, y, z, polarity, base_amp, digest = row
            activations[code_id] = max(0.2, min(1.0, base_amp + 0.25))

        selected_backend, backend_reason = select_backend(backend)
        lava_spec = build_lava_graph_spec(conn, seed_rows)

        event_rows = []
        for step in range(steps):
            next_activations = {}
            for code_id, amp in activations.items():
                row = conn.execute("SELECT polarity FROM LOIHI_TOPO_CODES WHERE code_id=?", (code_id,)).fetchone()
                polarity = row[0] if row else 1
                packet_hash = sha256_text(f"{experiment_id}:{step}:{code_id}:{amp:.6f}:{polarity}")
                event_id = f"LEVENT_{packet_hash[:18]}"
                event_rows.append((event_id, experiment_id, step, code_id, round(amp, 6), polarity, packet_hash))
                links = conn.execute(
                    """
                    SELECT to_code_id, weight FROM LOIHI_LINKS
                    WHERE from_code_id=?
                    """,
                    (code_id,),
                ).fetchall()
                for to_code_id, weight in links:
                    propagated = amp * weight * 0.62
                    if abs(propagated) < 0.03:
                        continue
                    next_activations[to_code_id] = next_activations.get(to_code_id, 0.0) + propagated
            activations = {
                code_id: max(-1.0, min(1.0, amp * 0.88))
                for code_id, amp in sorted(next_activations.items(), key=lambda item: abs(item[1]), reverse=True)[:48]
            }
            max_abs = max([abs(amp) for amp in activations.values()] or [1.0])
            if max_abs > 0.82:
                scale = 0.82 / max_abs
                activations = {code_id: amp * scale for code_id, amp in activations.items()}

        conn.executemany(
            """
            INSERT OR IGNORE INTO LOIHI_SPIKE_EVENTS (
                event_id, experiment_id, step, code_id, amplitude, polarity, packet_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            event_rows,
        )
        final_rows = []
        for code_id, amp in sorted(activations.items(), key=lambda item: abs(item[1]), reverse=True)[:16]:
            row = conn.execute(
                """
                SELECT code_type, label, source_table, source_id, x, y, z, polarity
                FROM LOIHI_TOPO_CODES
                WHERE code_id=?
                """,
                (code_id,),
            ).fetchone()
            if row:
                final_rows.append(
                    {
                        "code_id": code_id,
                        "amplitude": round(amp, 6),
                        "code_type": row[0],
                        "label": row[1],
                        "source_table": row[2],
                        "source_id": row[3],
                        "coord": [row[4], row[5], row[6]],
                        "polarity": row[7],
                    }
                )

        output_hash = sha256_text(json.dumps(final_rows, sort_keys=True))
        summary = summarize_output(final_rows)
        backend_manifest_id, backend_manifest = lava_backend_manifest(
            backend,
            selected_backend,
            experiment_id=experiment_id,
            graph_spec=lava_spec,
            reason=backend_reason,
            conn=conn,
        )
        report = {
            "experiment_id": experiment_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "mode": "loihi_style_sparse_cube_simulation",
            "backend": {
                "requested": backend,
                "selected": selected_backend,
                "reason": backend_reason,
                "manifest_id": backend_manifest_id,
                "lava_available": backend_manifest["lava_available"],
                "loihi_hardware_available": backend_manifest["loihi_hardware_available"],
            },
            "cube": {"x": CUBE_SIZE, "y": CUBE_SIZE, "z": CUBE_SIZE},
            "input_hash": input_hash,
            "prompt": prompt,
            "steps": steps,
            "seed_count": len(seed_rows),
            "event_count": len(event_rows),
            "output_hash": output_hash,
            "summary": summary,
            "top_outputs": final_rows,
            "policy": {
                "learning_only": True,
                "no_code_mutation": True,
                "requires_user_approval_for_any_patch": True,
            },
        }
        report_path = REPORT_DIR / f"{experiment_id}_{output_hash[:12]}.json"
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        conn.execute(
            """
            INSERT INTO LOIHI_SPIKE_EXPERIMENTS (
                experiment_id, input_hash, steps, seed_count, output_hash, report_path, summary
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (experiment_id, input_hash, steps, len(seed_rows), output_hash, str(report_path), summary),
        )
    return report


def summarize_output(rows):
    if not rows:
        return "No stable spike output survived propagation."
    positive = [row for row in rows if row["amplitude"] > 0]
    negative = [row for row in rows if row["amplitude"] < 0]
    strongest = rows[0]
    return (
        f"Strongest output `{strongest['label']}` from {strongest['source_table']} "
        f"at {strongest['coord']} amp={strongest['amplitude']}; "
        f"{len(positive)} positive and {len(negative)} negative surviving activations."
    )


def status():
    migrate()
    with connect_db() as conn:
        counts = {}
        for table in ["LOIHI_TOPO_CODES", "LOIHI_LINKS", "LOIHI_SPIKE_EXPERIMENTS", "LOIHI_SPIKE_EVENTS", "LOIHI_BACKEND_MANIFESTS"]:
            counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        latest = conn.execute(
            """
            SELECT experiment_id, summary, report_path, created_at
            FROM LOIHI_SPIKE_EXPERIMENTS
            ORDER BY created_at DESC
            LIMIT 3
            """
        ).fetchall()
    return {"counts": counts, "lava_available": lava_available(), "latest": latest}


def main():
    parser = argparse.ArgumentParser(description="Sparse Loihi-style topological spike sidecar.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("migrate")
    seed = sub.add_parser("seed")
    seed.add_argument("--limit", type=int, default=80)
    links = sub.add_parser("rebuild-links")
    links.add_argument("--max-neighbors", type=int, default=5)
    links.add_argument("--max-distance", type=float, default=38.0)
    exp = sub.add_parser("experiment")
    exp.add_argument("--prompt", required=True)
    exp.add_argument("--steps", type=int, default=6)
    exp.add_argument("--seed-limit", type=int, default=12)
    exp.add_argument("--backend", choices=["auto", "sparse-python", "lava"], default="auto")
    sub.add_parser("status")
    args = parser.parse_args()

    if args.command == "migrate":
        migrate()
        print("LOIHI_SPIKE_TABLES_READY")
    elif args.command == "seed":
        print(json.dumps({"seed_inputs_seen": seed_codes(args.limit)}, indent=2))
    elif args.command == "rebuild-links":
        print(json.dumps({"links_seen": rebuild_links(args.max_neighbors, args.max_distance)}, indent=2))
    elif args.command == "experiment":
        print(json.dumps(run_experiment(args.prompt, args.steps, args.seed_limit, args.backend), indent=2))
    elif args.command == "status":
        print(json.dumps(status(), indent=2))


if __name__ == "__main__":
    main()
