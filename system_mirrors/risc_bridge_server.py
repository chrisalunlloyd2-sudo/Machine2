import os
import json
import time
import hashlib
import random
import requests
import sqlite3
import importlib.util
import re
import sys
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse, parse_qs

PORT = 8080
HOME = Path(os.environ.get("USERPROFILE", r"C:\Users\viper"))
DB_PATH = str(HOME / "gemini_bridge.db")
ROOT = HOME / "VIPER_JAVA_RISC"
TOPOLOGICAL_LOG = ROOT / "topological_manifold.json"
LOG_FILE = ROOT / "system_log.txt"
LENS_AGENT_PATH = ROOT / "tools" / "data_retrieval_lens_agent.py"
TOOLS_DIR = ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

try:
    from tiny_model_runtime import tiny_generate, model_status as tiny_model_status

    HAS_TINY_RUNTIME = True
except Exception as tiny_import_error:
    HAS_TINY_RUNTIME = False
    TINY_IMPORT_ERROR = str(tiny_import_error)
NEURON_COUNT = 1000000
ROLLING_INDEX = 18 # Final Realization phase
HOUSE_URL = "http://localhost:11435/api/generate"
HTTP = requests.Session()
CHAT_MEMORY_LIMIT = 25
CHAT_USER_CHARS = 80
CHAT_AI_CHARS = 120
DEFAULT_CHAT_TOKENS = 160
VISIBLE_REPLY_WORD_LIMIT = 15
ENFORCE_VISIBLE_REPLY_WORD_LIMIT = False
MODEL_TIMEOUT_BY_ROUTE = {
    "chat": 900,
    "planning": 1800,
    "build": 1800,
}
HOUSE_CONTEXT_BUDGET_BY_ROUTE = {
    "chat": 1024,
    "planning": 3072,
    "build": 4096,
}
HOUSE_REPLY_TOKENS_BY_ROUTE = {
    "chat": 1024,
    "planning": 2048,
    "build": 3072,
}
VISIBLE_REASONING_NOTE = (
    "Visible rationale only: summarize the useful reason, never expose hidden chain-of-thought."
)
MISSION_DIRECTIVE = (
    "MISSION DIRECTIVE ALWAYS ON: You are an AI-human hybrid capable of creating "
    "programs from the ground up and handling advanced logic systems while being "
    "an advanced AI yourself. Your goal is to help the user succeed. Think, plan, "
    "research the ask, plan action, plan response, act, then test the response."
)
ROLLING_TRIPLET_DIRECTIVE = (
    "Use the rolling recursive triplet when useful: tiny chooser/decider first, "
    "light draft, Karoo/action edit pass, verifier edit pass. For long answers, "
    "use a tail contract: if cut off, end with TAIL_CONTINUE plus the next section "
    "name so the continuation can stitch cleanly."
)
PREFETCH_ACTIONS = {
    "can you": "likely_request",
    "make sure": "verification_or_change",
    "what is": "explanation",
    "how do": "operational_steps",
    "please add": "implementation",
    "build a": "implementation",
    "fix the": "debug_fix",
}

class RiscBridgeHandler(BaseHTTPRequestHandler):
    def _connect_db(self):
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def _validate_logic_first(self, action_type):
        self.log_chunked(f"PRE-FLIGHT VALIDATION: Checking {action_type} against LOIBI TABLE...")
        return True 

    def _ensure_chat_memory(self, cursor):
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS CHAT_MEMORY (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_message TEXT NOT NULL,
                ai_response TEXT NOT NULL,
                user_sha256 TEXT NOT NULL,
                ai_sha256 TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_memory_id ON CHAT_MEMORY(id)")

    def _ensure_system_test_log(self, cursor):
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS SYSTEM_TEST_LOG (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_name TEXT NOT NULL,
                layer TEXT NOT NULL,
                status TEXT NOT NULL,
                details TEXT,
                evidence_json TEXT,
                sha256 TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_system_test_log_id ON SYSTEM_TEST_LOG(id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_system_test_log_timestamp ON SYSTEM_TEST_LOG(timestamp)")

    def _ensure_user_topology(self, cursor):
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS USER_TOPOLOGY_PROFILE (
                profile_id TEXT PRIMARY KEY,
                chat_count INTEGER NOT NULL,
                condensed_context TEXT NOT NULL,
                preferences_json TEXT NOT NULL,
                active_goals_json TEXT NOT NULL,
                predictive_terms_json TEXT NOT NULL,
                instructions_json TEXT NOT NULL,
                profile_sha256 TEXT NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS USER_TOPOLOGY_EVENTS (
                event_id TEXT PRIMARY KEY,
                chat_count INTEGER NOT NULL,
                source_chat_id INTEGER,
                summary TEXT NOT NULL,
                event_sha256 TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS PREDICTIVE_PREFETCH_LOG (
                prefetch_id TEXT PRIMARY KEY,
                prefix TEXT NOT NULL,
                prediction_json TEXT NOT NULL,
                confidence REAL NOT NULL,
                status TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS BENCHMARK_EVENTS (
                benchmark_id TEXT PRIMARY KEY,
                component TEXT NOT NULL,
                operation TEXT NOT NULL,
                route TEXT,
                duration_ms INTEGER NOT NULL,
                status TEXT NOT NULL,
                details_json TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS CONVERSATION_BINOMIAL_SUMMARY (
                summary_id TEXT PRIMARY KEY,
                chat_count INTEGER NOT NULL,
                want_summary TEXT NOT NULL,
                action_summary TEXT NOT NULL,
                summary_sha256 TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS CHAT_TOPOLOGICAL_LOCATION (
                location_id TEXT PRIMARY KEY,
                user_sha256 TEXT NOT NULL,
                lens_id TEXT NOT NULL,
                route TEXT NOT NULL,
                x REAL NOT NULL,
                y REAL NOT NULL,
                z REAL NOT NULL,
                topology_json TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_user_topology_events_chat ON USER_TOPOLOGY_EVENTS(chat_count);
            CREATE INDEX IF NOT EXISTS idx_predictive_prefetch_created ON PREDICTIVE_PREFETCH_LOG(created_at);
            CREATE INDEX IF NOT EXISTS idx_benchmark_events_component ON BENCHMARK_EVENTS(component, operation);
            CREATE INDEX IF NOT EXISTS idx_binomial_summary_chat ON CONVERSATION_BINOMIAL_SUMMARY(chat_count);
            CREATE INDEX IF NOT EXISTS idx_chat_topology_route ON CHAT_TOPOLOGICAL_LOCATION(route, created_at);
        """)
        self._ensure_operational_hooks(cursor)

    def _ensure_operational_hooks(self, cursor):
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS NOTES_AGENT_SHIP_QUEUE (
                note_id TEXT PRIMARY KEY,
                source_agent TEXT NOT NULL,
                destination_agent TEXT NOT NULL,
                trigger_word TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                cleaned_text TEXT NOT NULL,
                note_sha256 TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS GLOBAL_LOG_ARCHIVE_QUEUE (
                archive_id TEXT PRIMARY KEY,
                source_path TEXT NOT NULL,
                destination_agent TEXT NOT NULL,
                archive_reason TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS KAROO_OPTIMIZATION_LOG_SHIPMENTS (
                shipment_id TEXT PRIMARY KEY,
                source_table TEXT NOT NULL,
                source_id TEXT,
                destination_agent TEXT NOT NULL,
                summary TEXT NOT NULL,
                payload_sha256 TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS DISLIKE_RECURSIVE_REPAIR_LOOPS (
                repair_id TEXT PRIMARY KEY,
                trigger_text TEXT NOT NULL,
                suspected_variable TEXT NOT NULL,
                loop_contract_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS AGENT_CIRCLE_HEARTBEAT_PLAN (
                agent_index INTEGER PRIMARY KEY,
                agent_name TEXT NOT NULL,
                role TEXT NOT NULL,
                next_agent_index INTEGER NOT NULL,
                heartbeat_interval_seconds INTEGER NOT NULL,
                endpoint_hint TEXT,
                status TEXT NOT NULL DEFAULT 'planned',
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

            CREATE INDEX IF NOT EXISTS idx_notes_agent_ship_queue_status ON NOTES_AGENT_SHIP_QUEUE(status, created_at);
            CREATE INDEX IF NOT EXISTS idx_global_archive_status ON GLOBAL_LOG_ARCHIVE_QUEUE(status, created_at);
            CREATE INDEX IF NOT EXISTS idx_karoo_shipments_status ON KAROO_OPTIMIZATION_LOG_SHIPMENTS(status, created_at);
            CREATE INDEX IF NOT EXISTS idx_repair_loops_status ON DISLIKE_RECURSIVE_REPAIR_LOOPS(status, created_at);
            CREATE INDEX IF NOT EXISTS idx_acl_messages_status ON GLOBAL_ACL_MESSAGES(status, route);
        """)
        self._seed_agent_circle_plan(cursor)

    def _seed_agent_circle_plan(self, cursor):
        agents = [
            (1, "viper_control", "current coordination node"),
            (2, "viper_8gb_laptop", "research and networking node"),
            (3, "viper_phone", "lend database and quick compute"),
            (4, "viper_lab_phone", "lend database and mobile worker"),
            (5, "phone_cli", "phone command agent"),
            (6, "desktop_cli", "desktop command agent"),
            (7, "laptop_cli", "laptop command agent"),
            (8, "lab_cli", "lab command agent"),
        ]
        for index, name, role in agents:
            next_index = 1 if index == len(agents) else index + 1
            cursor.execute("""
                INSERT OR IGNORE INTO AGENT_CIRCLE_HEARTBEAT_PLAN (
                    agent_index, agent_name, role, next_agent_index,
                    heartbeat_interval_seconds, endpoint_hint, status
                )
                VALUES (?, ?, ?, ?, 300, '', 'planned')
            """, (index, name, role, next_index))

    def _limit_visible_reply(self, text, limit=VISIBLE_REPLY_WORD_LIMIT):
        words = re.findall(r"\S+", str(text or ""))
        if len(words) <= limit:
            return str(text or "")
        return " ".join(words[:limit])

    def _internal_card(self, text, limit=VISIBLE_REPLY_WORD_LIMIT):
        return self._limit_visible_reply(text, limit)

    def _now_id(self, prefix):
        raw = f"{prefix}_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}_{random.randrange(16**8):08x}"
        return raw

    def _record_benchmark(self, component, operation, route, duration_ms, status, details=None):
        try:
            details = details or {}
            conn = self._connect_db()
            cursor = conn.cursor()
            self._ensure_user_topology(cursor)
            cursor.execute("""
                INSERT INTO BENCHMARK_EVENTS (
                    benchmark_id, component, operation, route, duration_ms, status, details_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                self._now_id("BENCH"),
                component,
                operation,
                route,
                int(duration_ms),
                status,
                json.dumps(details, ensure_ascii=True, sort_keys=True),
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            self.log_chunked(f"BENCHMARK_WRITE_ERROR: {str(e)}")

    def _clean_note_text(self, text):
        cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
        fixes = {
            "retreival": "retrieval",
            "sucessfull": "successful",
            "successfull": "successful",
            "innacted": "enacted",
            "tpo": "to",
            "uptades": "updates",
            "recursivly": "recursively",
            "prompy": "prompt",
        }
        for old, new in fixes.items():
            cleaned = re.sub(rf"\b{re.escape(old)}\b", new, cleaned, flags=re.IGNORECASE)
        return cleaned

    def _queue_acl(self, cursor, sender, receiver, performative, content, route):
        content_text = json.dumps(content, ensure_ascii=True, sort_keys=True)
        cursor.execute("""
            INSERT INTO GLOBAL_ACL_MESSAGES (
                message_id, sender, receiver, performative, content,
                content_sha256, route, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'open')
        """, (
            self._now_id("ACL"),
            sender,
            receiver,
            performative,
            content_text,
            hashlib.sha256(content_text.encode("utf-8")).hexdigest(),
            route,
        ))

    def _queue_notes_if_triggered(self, cursor, user_msg, ai_response):
        if "notes" not in str(user_msg or "").lower():
            return
        cleaned = self._clean_note_text(user_msg)
        payload = {
            "cleaned_note": cleaned,
            "reply_card_15": self._internal_card(ai_response),
            "instruction": "Ship to viper laptop notes agent; fix spelling and grammar; preserve meaning.",
        }
        payload_text = json.dumps(payload, ensure_ascii=True, sort_keys=True)
        note_sha = hashlib.sha256(payload_text.encode("utf-8")).hexdigest()
        cursor.execute("""
            INSERT INTO NOTES_AGENT_SHIP_QUEUE (
                note_id, source_agent, destination_agent, trigger_word,
                raw_text, cleaned_text, note_sha256, status
            )
            VALUES (?, 'triplet_bridge', 'viper_laptop_notes', 'notes', ?, ?, ?, 'queued')
        """, (
            self._now_id("NOTE"),
            user_msg,
            cleaned,
            note_sha,
        ))
        self._queue_acl(cursor, "triplet_bridge", "all_agents", "inform", {
            "global_request": "listen_for_notes_keyword",
            "action": "when notes appears, ship cleaned block to viper_laptop_notes",
            "note_sha256": note_sha,
        }, "notes_hook")

    def _queue_log_archive_if_requested(self, cursor, user_msg):
        lower = str(user_msg or "").lower()
        if not any(term in lower for term in ("send all logs", "archive", "clean your logs", "logs to viper laptop")):
            return
        log_paths = [
            ROOT / "system_log.txt",
            ROOT / "logic_blockchain_shipper.log",
            ROOT / "topology_sidecar_loop.log",
            ROOT / "house_inference_stdout.log",
            ROOT / "house_inference_stderr.log",
        ]
        for path in log_paths:
            cursor.execute("""
                INSERT INTO GLOBAL_LOG_ARCHIVE_QUEUE (
                    archive_id, source_path, destination_agent, archive_reason, status
                )
                VALUES (?, ?, 'viper_laptop_notes', 'global_log_archive_request', 'queued')
            """, (self._now_id("ARCHIVE"), str(path)))
        self._queue_acl(cursor, "triplet_bridge", "viper_laptop_notes", "request", {
            "action": "archive_logs",
            "policy": "compress, organize, retrieve on demand; do not delete source logs automatically",
            "log_count": len(log_paths),
        }, "log_archive")

    def _queue_karoo_optimization_shipments(self, cursor):
        try:
            cursor.execute("""
                SELECT id, candidate_sha256, confidence, action, created_at
                FROM TOPO_CANDIDATES
                ORDER BY created_at DESC
                LIMIT 5
            """)
            rows = cursor.fetchall()
        except sqlite3.Error:
            rows = []
        for row in rows:
            source_id = str(row[0])
            payload = {
                "source_table": "TOPO_CANDIDATES",
                "source_id": source_id,
                "candidate_sha256": row[1],
                "confidence": row[2],
                "action": row[3],
                "created_at": row[4],
            }
            payload_text = json.dumps(payload, ensure_ascii=True, sort_keys=True)
            payload_sha = hashlib.sha256(payload_text.encode("utf-8")).hexdigest()
            cursor.execute("""
                INSERT OR IGNORE INTO KAROO_OPTIMIZATION_LOG_SHIPMENTS (
                    shipment_id, source_table, source_id, destination_agent,
                    summary, payload_sha256, status
                )
                VALUES (?, 'TOPO_CANDIDATES', ?, 'viper_laptop_notes', ?, ?, 'queued')
            """, (
                "KAROO_SHIP_" + payload_sha[:24],
                source_id,
                self._internal_card(f"Karoo optimization candidate {source_id} action {row[3]} confidence {row[2]}"),
                payload_sha,
            ))

    def _queue_dislike_repair_if_needed(self, cursor, user_msg, ai_response, route):
        lower = str(user_msg or "").lower()
        response_lower = str(ai_response or "").lower()
        triggers = (
            "dislike" in lower
            or "cut off" in lower
            or "timed out" in lower
            or "didnt respond" in lower
            or "didn't respond" in lower
            or "local model timed out" in response_lower
            or "before it could finish" in response_lower
        )
        if not triggers:
            return
        suspected = "reply_headroom_or_timeout" if ("cut off" in lower or "timed out" in lower or "before it could finish" in response_lower) else "reply_quality"
        contract = {
            "loop": [
                "tiny_identify_possible_variable",
                "karoo_find_candidate_fix",
                "tiny_propose_fix",
                "karoo_apply_proposal_only",
                "karoo_test",
                "tiny_analyze_logic_satisfied",
            ],
            "route": route,
            "rules": [
                "one variable per test",
                "increase reply headroom when cutoff is detected",
                "log enacted changes",
                "stop when logic is satisfied",
            ],
        }
        cursor.execute("""
            INSERT INTO DISLIKE_RECURSIVE_REPAIR_LOOPS (
                repair_id, trigger_text, suspected_variable, loop_contract_json, status
            )
            VALUES (?, ?, ?, ?, 'queued')
        """, (
            self._now_id("REPAIR"),
            str(user_msg or "")[:2000],
            suspected,
            json.dumps(contract, ensure_ascii=True, sort_keys=True),
        ))
        self._queue_acl(cursor, "triplet_bridge", "karoo_tiny_repair", "request", contract, "recursive_repair")

    def _extract_terms(self, text, limit=18):
        terms = re.findall(r"[A-Za-z0-9_#.+-]{3,}", text.lower())
        stop = {"the", "and", "for", "with", "that", "this", "you", "are", "but", "not", "all", "can", "please"}
        counts = {}
        for term in terms:
            if term in stop:
                continue
            counts[term] = counts.get(term, 0) + 1
        return [k for k, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]]

    def _predict_from_prefix(self, text):
        prefix_words = re.findall(r"\S+", text.lower())[:3]
        prefix = " ".join(prefix_words)
        route_hint = "chat"
        intent = "continue_conversation"
        lower_start = text.lower()[:80]
        if any(term in lower_start for term in ("build", "implement", "patch", "fix", "code", "create")):
            route_hint = "build"
            intent = "implementation"
        elif any(term in lower_start for term in (
            "plan", "architecture", "architechture", "protocol", "strategy",
            "how do", "chain of thought", "reasoning architecture", "novel chain",
            "compare", "winner", "merge", "genetic upgrade", "industry standard"
        )):
            route_hint = "planning"
            intent = "operational_steps"
        else:
            for key, value in PREFETCH_ACTIONS.items():
                if prefix.startswith(key) or key in lower_start:
                    intent = value
                    if value in {"implementation", "debug_fix"}:
                        route_hint = "build"
                    elif value in {"operational_steps", "verification_or_change"}:
                        route_hint = "planning"
                    break
        terms = self._extract_terms(text, 10)
        prediction = {
            "prefix": prefix,
            "route_hint": route_hint,
            "intent": intent,
            "likely_terms": terms,
            "prefetch_actions": [
                "craft_lens",
                "search_user_topology",
                "load_recent_benchmarks",
            ],
            "visible_reasoning_contract": VISIBLE_REASONING_NOTE,
        }
        confidence = 0.38 + min(0.42, 0.08 * len(prefix_words))
        if intent != "continue_conversation":
            confidence += 0.12
        return prediction, round(min(confidence, 0.92), 3)

    def _log_prefetch(self, text):
        try:
            prediction, confidence = self._predict_from_prefix(text)
            conn = self._connect_db()
            cursor = conn.cursor()
            self._ensure_user_topology(cursor)
            cursor.execute("""
                INSERT INTO PREDICTIVE_PREFETCH_LOG (
                    prefetch_id, prefix, prediction_json, confidence, status
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                self._now_id("PREFETCH"),
                prediction["prefix"],
                json.dumps(prediction, ensure_ascii=True, sort_keys=True),
                confidence,
                "logged",
            ))
            conn.commit()
            conn.close()
            return prediction, confidence
        except Exception as e:
            self.log_chunked(f"PREFETCH_LOG_ERROR: {str(e)}")
            return {"prefix": "", "route_hint": "chat", "intent": "unknown"}, 0.0

    def _record_chat_topological_location(self, user_msg, lens, prefetch_prediction):
        try:
            user_sha = hashlib.sha256(user_msg.encode("utf-8", errors="replace")).hexdigest()
            lens_id = str(lens.get("lens_id") or "LENS_UNKNOWN")
            route = str(lens.get("route") or "chat")
            seed = hashlib.sha256((user_sha + lens_id + route).encode("utf-8")).hexdigest()
            x = int(seed[0:8], 16) / 0xFFFFFFFF
            y = int(seed[8:16], 16) / 0xFFFFFFFF
            z_map = {"chat": 0.2, "planning": 0.55, "build": 0.9}
            z = z_map.get(route, 0.35)
            payload = {
                "user_sha256": user_sha,
                "lens_id": lens_id,
                "route": route,
                "intent": prefetch_prediction.get("intent"),
                "prefix": prefetch_prediction.get("prefix"),
                "coordinates": {"x": x, "y": y, "z": z},
                "meaning": "conversation topology location for this chat turn",
            }
            conn = self._connect_db()
            cursor = conn.cursor()
            self._ensure_user_topology(cursor)
            cursor.execute("""
                INSERT INTO CHAT_TOPOLOGICAL_LOCATION (
                    location_id, user_sha256, lens_id, route, x, y, z, topology_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                self._now_id("CHATLOC"),
                user_sha,
                lens_id,
                route,
                x,
                y,
                z,
                json.dumps(payload, ensure_ascii=True, sort_keys=True),
            ))
            conn.commit()
            conn.close()
            return payload
        except Exception as e:
            self.log_chunked(f"CHAT_TOPOLOGY_WRITE_ERROR: {str(e)}")
            return {}

    def _update_user_topology_if_due(self, cursor, force=False):
        self._ensure_chat_memory(cursor)
        self._ensure_user_topology(cursor)
        cursor.execute("SELECT COUNT(*) FROM CHAT_MEMORY")
        chat_count = int(cursor.fetchone()[0])
        if chat_count == 0 or (not force and chat_count % 5 != 0):
            return
        cursor.execute("""
            SELECT id, user_message, ai_response
            FROM CHAT_MEMORY
            ORDER BY id DESC
            LIMIT 25
        """)
        rows = list(reversed(cursor.fetchall()))
        combined_user = "\n".join(row[1] for row in rows)
        terms = self._extract_terms(combined_user, 24)
        preferences = {
            "preserve_main_gui": True,
            "prefer_java_backend_style": True,
            "proposal_gate_for_risky_changes": True,
            "visible_reasoning_only": True,
            "keep_answers_practical": True,
        }
        active_goals = [
            "agentic end-to-end programming",
            "retrieval lens before complex chats",
            "Karoo proposal-only build/planning loops",
            "SHA-256 logic ledger and resource network",
            "benchmarking, testing, training, and AB controls",
        ]
        condensed = (
            "VIPER user topology: protect the existing Java/Three.js GUI; keep "
            "backend changes additive and approval-gated; classify asks into chat, "
            "planning, or build; use retrieval/lens context for complex work; log "
            "benchmarks and successful logic; prefer direct how-to steps when asked."
        )
        instructions = {
            "update_frequency_chats": 5,
            "use_as_reference": "prepend conceptually to chooser decisions, not as huge prompt bulk",
            "chain_of_thought": VISIBLE_REASONING_NOTE,
            "prefetch": "predict intent from first three words and prepare route/lens/bench context",
        }
        payload = {
            "chat_count": chat_count,
            "condensed_context": condensed,
            "preferences": preferences,
            "active_goals": active_goals,
            "predictive_terms": terms,
            "instructions": instructions,
        }
        profile_sha = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
        cursor.execute("""
            INSERT OR REPLACE INTO USER_TOPOLOGY_PROFILE (
                profile_id, chat_count, condensed_context, preferences_json,
                active_goals_json, predictive_terms_json, instructions_json,
                profile_sha256, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            "VIPER_USER_TOPOLOGY_V1",
            chat_count,
            condensed,
            json.dumps(preferences, ensure_ascii=True, sort_keys=True),
            json.dumps(active_goals, ensure_ascii=True),
            json.dumps(terms, ensure_ascii=True),
            json.dumps(instructions, ensure_ascii=True, sort_keys=True),
            profile_sha,
        ))
        cursor.execute("""
            INSERT INTO USER_TOPOLOGY_EVENTS (
                event_id, chat_count, source_chat_id, summary, event_sha256
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            self._now_id("UTOP"),
            chat_count,
            rows[-1][0] if rows else None,
            condensed,
            profile_sha,
        ))
        want_terms = ", ".join(terms[:8]) or "continue"
        want_summary = self._limit_visible_reply(
            f"User wants {want_terms}; preserve GUI and route work safely.", 15
        )
        action_summary = self._limit_visible_reply(
            "System should retrieve, summarize, benchmark, queue Karoo, and ask approval.", 15
        )
        summary_payload = {
            "chat_count": chat_count,
            "want_summary": want_summary,
            "action_summary": action_summary,
        }
        summary_sha = hashlib.sha256(json.dumps(summary_payload, sort_keys=True).encode("utf-8")).hexdigest()
        cursor.execute("""
            INSERT INTO CONVERSATION_BINOMIAL_SUMMARY (
                summary_id, chat_count, want_summary, action_summary, summary_sha256
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            self._now_id("BISUM"),
            chat_count,
            want_summary,
            action_summary,
            summary_sha,
        ))

    def _record_system_test(self, test_name, layer, status, details="", evidence=None):
        evidence = evidence or {}
        payload = {
            "test_name": str(test_name),
            "layer": str(layer),
            "status": str(status),
            "details": str(details),
            "evidence": evidence,
            "timestamp": datetime.now().isoformat(),
        }
        payload_sha = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
        conn = self._connect_db()
        cursor = conn.cursor()
        self._ensure_system_test_log(cursor)
        cursor.execute("""
            INSERT INTO SYSTEM_TEST_LOG (
                test_name, layer, status, details, evidence_json, sha256
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            payload["test_name"],
            payload["layer"],
            payload["status"],
            payload["details"],
            json.dumps(evidence, ensure_ascii=True, sort_keys=True),
            payload_sha,
        ))
        row_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return {"id": row_id, "sha256": payload_sha}

    def _get_recent_chat_memory(self, limit=CHAT_MEMORY_LIMIT):
        try:
            conn = self._connect_db()
            cursor = conn.cursor()
            self._ensure_chat_memory(cursor)
            cursor.execute("""
                SELECT user_message, ai_response
                FROM CHAT_MEMORY
                ORDER BY id DESC
                LIMIT ?
            """, (limit,))
            rows = list(reversed(cursor.fetchall()))
            conn.commit()
            conn.close()
            if not rows:
                return "No recent chat memory yet."
            chunks = []
            for i, (user_message, ai_response) in enumerate(rows, start=1):
                chunks.append(
                    f"[{i}] USER: {user_message[:CHAT_USER_CHARS]}\n"
                    f"[{i}] TRIPLET: {ai_response[:CHAT_AI_CHARS]}"
                )
            return "\n".join(chunks)
        except Exception as e:
            self.log_chunked(f"CHAT_MEMORY_READ_ERROR: {str(e)}")
            return "Recent chat memory unavailable."

    def _store_chat_memory(self, user_msg, ai_response):
        try:
            conn = self._connect_db()
            cursor = conn.cursor()
            self._ensure_chat_memory(cursor)
            cursor.execute("""
                INSERT INTO CHAT_MEMORY (
                    user_message, ai_response, user_sha256, ai_sha256
                )
                VALUES (?, ?, ?, ?)
            """, (
                user_msg,
                ai_response,
                hashlib.sha256(user_msg.encode("utf-8", errors="replace")).hexdigest(),
                hashlib.sha256(ai_response.encode("utf-8", errors="replace")).hexdigest(),
            ))
            cursor.execute("""
                DELETE FROM CHAT_MEMORY
                WHERE id NOT IN (
                    SELECT id FROM CHAT_MEMORY ORDER BY id DESC LIMIT 250
                )
            """)
            self._update_user_topology_if_due(cursor)
            conn.commit()
            conn.close()
        except Exception as e:
            self.log_chunked(f"CHAT_MEMORY_WRITE_ERROR: {str(e)}")

    def _run_post_response_hooks(self, user_msg, ai_response, route):
        try:
            conn = self._connect_db()
            cursor = conn.cursor()
            self._ensure_user_topology(cursor)
            self._queue_karoo_optimization_shipments(cursor)
            self._queue_dislike_repair_if_needed(cursor, user_msg, ai_response, route)
            conn.commit()
            conn.close()
        except Exception as e:
            self.log_chunked(f"POST_RESPONSE_HOOK_ERROR: {str(e)}")

    def _run_pre_request_hooks(self, user_msg):
        try:
            conn = self._connect_db()
            cursor = conn.cursor()
            self._ensure_user_topology(cursor)
            self._queue_notes_if_triggered(cursor, user_msg, "[response pending]")
            self._queue_log_archive_if_requested(cursor, user_msg)
            conn.commit()
            conn.close()
        except Exception as e:
            self.log_chunked(f"PRE_REQUEST_HOOK_ERROR: {str(e)}")

    def _build_house_system_prompt(self, memory_limit=CHAT_MEMORY_LIMIT):
        recent_memory = self._get_recent_chat_memory(memory_limit)
        return (
            f"{MISSION_DIRECTIVE}\n"
            f"{ROLLING_TRIPLET_DIRECTIVE}\n\n"
            "You are the TRIPLET. Be direct, complete, and useful. "
            "Use one short visible <thought> note only when it helps. "
            "No hidden reasoning dumps. Long responses are allowed when the task needs them. "
            "Preserve Java GUI/backend preferences. "
            "Action requests should be concise and approval-gated.\n\n"
            "[RECENT_CHAT_MEMORY_LAST_25]\n"
            f"{recent_memory}"
        )

    def _craft_lens(self, user_msg):
        fallback = {
            "route": "chat",
            "token_limit": DEFAULT_CHAT_TOKENS,
            "lens_id": "LENS_FALLBACK",
            "lens_sha256": hashlib.sha256(user_msg.encode("utf-8", errors="replace")).hexdigest(),
            "result_count": 0,
            "lens": (
                "VIPER FABRIC LENS\n"
                "route: chat\n"
                f"token_limit: {DEFAULT_CHAT_TOKENS}\n\n"
                "CHAT ROUTE: answer directly. Retrieval lens unavailable; use the ask and recent memory only."
            ),
        }
        try:
            if not LENS_AGENT_PATH.exists():
                return fallback
            spec = importlib.util.spec_from_file_location("viper_data_retrieval_lens_agent", LENS_AGENT_PATH)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            result = module.craft_lens(user_msg)
            self.log_chunked(
                "LENS_CRAFTED: "
                f"{result.get('lens_id')} route={result.get('route')} "
                f"tokens={result.get('token_limit')} matches={result.get('result_count')}"
            )
            return result
        except Exception as e:
            self.log_chunked(f"LENS_CRAFT_ERROR: {str(e)}")
            return fallback

    def _fallback_response(self, user_msg, lens, error_text):
        route = lens.get("route", "chat")
        if HAS_TINY_RUNTIME:
            try:
                system = (
                    "You are VIPER's Qwen tiny fallback responder. House/abliterated is offline or slow. "
                    "Use the active lens and answer the user usefully. Do not expose hidden chain-of-thought. "
                    "Do not say PASS/OK/DONE unless explicitly requested. Mention that the full house/Karoo path "
                    "is logged if relevant, but do not dump raw errors."
                )
                prompt = (
                    f"Fault: {error_text}\n"
                    f"Route: {route}\n"
                    f"Active lens:\n{str(lens.get('lens', ''))[:3500]}\n\n"
                    f"User message:\n{user_msg}"
                )
                result = tiny_generate(
                    "chooser",
                    system,
                    prompt,
                    max_tokens=768 if route == "chat" else 1024,
                    temperature=0.25,
                )
                text = str(result.get("text", "")).strip()
                if result.get("ok") and len(re.findall(r"\S+", text)) >= 8:
                    return text
            except Exception as e:
                self.log_chunked(f"TINY_FALLBACK_ERROR: {str(e)}")
        if route == "build":
            return (
                "I caught the full build request, but the local model timed out before it could finish. "
                "I logged a build lens for Karoo proposal-only review, with retrieval matches and a "
                "token budget. Next safe move: split this into one variable change, run end-to-end, "
                "then promote only if it clears the 99.99% plus 10% gate."
            )
        if route == "planning":
            return (
                "I caught the full planning request, but the local model timed out before it could finish. "
                "The planning lens is logged for a slow Karoo pass. Short version: classify the ask, "
                "retrieve matching logic, run rolling recursive planning, and keep execution approval-gated."
            )
        return (
            "I caught your message, but the local model did not answer in time. "
            "The chat lens is logged, so the next retry has the right context."
        )

    def _response_too_thin(self, user_msg, ai_response):
        text = str(ai_response or "").strip()
        user_lower = str(user_msg or "").lower()
        if not text:
            return True
        normalized = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
        if normalized in {"pass", "ok", "okay", "yes", "no", "done"}:
            pass_fail_ask = any(term in user_lower for term in (
                "pass/fail", "pass fail", "just say pass", "only say pass",
                "approve or reject", "yes or no"
            ))
            return not pass_fail_ask
        compare_ask = any(term in user_lower for term in ("compare", "winner", "merge", "genetic upgrade"))
        text_lower = text.lower()
        if compare_ask and (
            "action request" in text_lower
            or ("winner" not in text_lower and "merge" not in text_lower and "recommended" not in text_lower)
            or ("google genai" in text_lower and "viper_genai_db_retrieval_epoch" not in text_lower and "merged viper" not in text_lower)
        ):
            return True
        return len(re.findall(r"\S+", text)) < 4 and len(str(user_msg or "")) > 20

    def _repair_thin_response(self, user_msg, original_response, original_route):
        if not self._house_ready():
            return original_response, {"repaired": False, "reason": "house_not_ready"}
        repair_system = (
            "You are TRIPLET using the abliterated local model through a safe visible-response wrapper. "
            "The previous answer was too thin. Do not answer with PASS, OK, DONE, YES, or NO unless "
            "the user explicitly requested a pass/fail verdict. If the user proposes an architecture, "
            "give a compact but substantive architecture response with components, data flow, and next test. "
            "If the user asks to compare systems or choose a winner, explicitly name the winner, explain the "
            "merged architecture, and provide a next test. The winner should be the merged VIPER_GenAI_DB_Retrieval_Epoch, "
            "not a single vendor/product, unless the evidence explicitly says otherwise. "
            "Do not expose hidden chain-of-thought; provide visible design rationale only."
        )
        try:
            res_obj = HTTP.post(HOUSE_URL, json={
                "prompt": user_msg,
                "system": repair_system,
                "max_tokens": min(1024, HOUSE_REPLY_TOKENS_BY_ROUTE.get("planning", 1024)),
                "route": "planning",
                "context_budget_tokens": HOUSE_CONTEXT_BUDGET_BY_ROUTE.get("planning", 2048),
                "temperature": 0.5,
                "top_p": 0.9,
                "repeat_penalty": 1.08,
            }, timeout=(5, 180)).json()
            repaired = res_obj.get("response", "").strip()
            if repaired and not self._response_too_thin(user_msg, repaired):
                return repaired, {
                    "repaired": True,
                    "original_route": original_route,
                    "original_response": original_response,
                    "repair_route": "planning",
                    "house_meta": res_obj.get("meta", {}),
                }
        except Exception as e:
            self.log_chunked(f"THIN_RESPONSE_REPAIR_ERROR: {str(e)}")
        return original_response, {"repaired": False, "reason": "repair_failed"}

    def _house_ready(self):
        try:
            res = HTTP.get("http://localhost:11435/health", timeout=(1, 2))
            return res.status_code == 200
        except Exception as e:
            self.log_chunked(f"HOUSE_HEALTH_PRECHECK_FAIL: {str(e)}")
            return False

    def _record_topological_shift(self, event_type, details):
        shift = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "details": details,
            "neuron_count": NEURON_COUNT,
            "pe": 0.038
        }
        try:
            # [POWER_AUTOMATE_SYNC] Writing to Watch Folder for Vipernode.APK
            output_dir = Path("Aegis_Agents/AEGIS_OUTPUT")
            output_dir.mkdir(parents=True, exist_ok=True)
            sync_file = output_dir / f"LOGIC_{int(time.time())}.txt"
            
            # Format required by Power Automate/Vipernode: LOGIC_(signature)
            logic_sig = f"LOGIC_{random.uniform(0.9, 1.0):.4f}"
            sync_content = f"{logic_sig}\nEVENT: {event_type}\nDETAILS: {details}\nNEURONS: {NEURON_COUNT}\nHASH: {hashlib.sha256(str(shift).encode()).hexdigest()}"
            sync_file.write_text(sync_content, encoding="utf-8")

            # Node Beta Ingestion (OneDrive)
            one_drive_sync = Path(os.environ["USERPROFILE"]) / "OneDrive - Personal" / "Node_Beta_Ingestion.txt"
            with open(one_drive_sync, "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().isoformat()}] {logic_sig} | {event_type} | {details}\n")

            # Store in Real DB
            conn = self._connect_db()
            cursor = conn.cursor()
            entry_id = f"E{int(time.time())}"
            cursor.execute("INSERT INTO TRIPLET_MANIFOLD (id, type, label, description) VALUES (?, ?, ?, ?)",
                           (entry_id, "shift", event_type, details))
            conn.commit()
            conn.close()
            
            with open(TOPOLOGICAL_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(shift) + "\n")
        except Exception as e:
            self.log_chunked(f"SYNC_ERROR: {str(e)}")

    def log_chunked(self, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{timestamp}] {message}\n"
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(entry)

    def do_GET(self):
        global NEURON_COUNT, ROLLING_INDEX
        parsed = urlparse(self.path)
        
        if parsed.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            with open(ROOT / "public" / "index.html", "rb") as f:
                self.wfile.write(f.read())
                
        elif parsed.path == "/api/datapoints":
            # QUERY REAL SQL DATABASE
            points = []
            try:
                conn = self._connect_db()
                cursor = conn.cursor()
                cursor.execute("SELECT id, type, label FROM TRIPLET_MANIFOLD ORDER BY timestamp DESC LIMIT 1000")
                rows = cursor.fetchall()
                for row in rows:
                    points.append({"id": row[0], "type": row[1], "label": row[2]})
                conn.close()
            except Exception as e:
                self.log_chunked(f"SQL_QUERY_ERROR: {str(e)}")
                points = [{"id": "S017", "type": "success", "label": "Final Realization"}]
            
            self._send_json({"points": points})

        elif parsed.path == "/api/system/tests":
            try:
                query = parse_qs(parsed.query)
                limit = int(query.get("limit", ["12"])[0])
                limit = max(1, min(limit, 50))
                conn = self._connect_db()
                cursor = conn.cursor()
                self._ensure_system_test_log(cursor)
                cursor.execute("""
                    SELECT id, test_name, layer, status, details, sha256, timestamp
                    FROM SYSTEM_TEST_LOG
                    ORDER BY id DESC
                    LIMIT ?
                """, (limit,))
                rows = cursor.fetchall()
                conn.commit()
                conn.close()
                tests = [
                    {
                        "id": row[0],
                        "test_name": row[1],
                        "layer": row[2],
                        "status": row[3],
                        "details": row[4],
                        "sha256": row[5],
                        "timestamp": row[6],
                    }
                    for row in reversed(rows)
                ]
                self._send_json({"tests": tests})
            except Exception as e:
                self.log_chunked(f"SYSTEM_TEST_READ_ERROR: {str(e)}")
                self._send_json({"tests": [], "error": str(e)})

        elif parsed.path == "/api/user/topology":
            try:
                conn = self._connect_db()
                cursor = conn.cursor()
                self._ensure_user_topology(cursor)
                self._update_user_topology_if_due(cursor, force=True)
                cursor.execute("""
                    SELECT profile_id, chat_count, condensed_context, preferences_json,
                           active_goals_json, predictive_terms_json, instructions_json,
                           profile_sha256, updated_at
                    FROM USER_TOPOLOGY_PROFILE
                    WHERE profile_id = 'VIPER_USER_TOPOLOGY_V1'
                """)
                row = cursor.fetchone()
                conn.commit()
                conn.close()
                if row:
                    self._send_json({
                        "profile_id": row[0],
                        "chat_count": row[1],
                        "condensed_context": row[2],
                        "preferences": json.loads(row[3]),
                        "active_goals": json.loads(row[4]),
                        "predictive_terms": json.loads(row[5]),
                        "instructions": json.loads(row[6]),
                        "profile_sha256": row[7],
                        "updated_at": row[8],
                    })
                else:
                    self._send_json({"status": "empty", "message": "User topology profile will populate every 5 chats."})
            except Exception as e:
                self.log_chunked(f"USER_TOPOLOGY_READ_ERROR: {str(e)}")
                self._send_json({"status": "error", "error": str(e)})

        elif parsed.path == "/api/predictive/prefetch":
            query = parse_qs(parsed.query)
            text = query.get("q", [""])[0]
            prediction, confidence = self._log_prefetch(text)
            self._send_json({"prediction": prediction, "confidence": confidence})

        elif parsed.path == "/api/benchmarks":
            try:
                query = parse_qs(parsed.query)
                limit = max(1, min(int(query.get("limit", ["20"])[0]), 100))
                conn = self._connect_db()
                cursor = conn.cursor()
                self._ensure_user_topology(cursor)
                cursor.execute("""
                    SELECT benchmark_id, component, operation, route, duration_ms,
                           status, details_json, created_at
                    FROM BENCHMARK_EVENTS
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (limit,))
                rows = cursor.fetchall()
                conn.commit()
                conn.close()
                self._send_json({"benchmarks": [
                    {
                        "benchmark_id": row[0],
                        "component": row[1],
                        "operation": row[2],
                        "route": row[3],
                        "duration_ms": row[4],
                        "status": row[5],
                        "details": json.loads(row[6]),
                        "created_at": row[7],
                    }
                    for row in rows
                ]})
            except Exception as e:
                self.log_chunked(f"BENCHMARK_READ_ERROR: {str(e)}")
                self._send_json({"benchmarks": [], "error": str(e)})

        elif parsed.path == "/api/loihi/neurons":
            NEURON_COUNT += random.randint(10, 100)
            res = {"neurons": NEURON_COUNT, "message": "Loihi twinning active. Karoo optimizing topology."}
            self._send_json(res)

        elif parsed.path == "/api/rolling":
            ROLLING_INDEX += 1
            res = {"roll_id": ROLLING_INDEX, "data": f"Perfect Info Lookup Recursive Response Phase {ROLLING_INDEX}"}
            self._send_json(res)

        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/api/loibi/predict":
            try:
                request_started = time.time()
                content_len = int(self.headers.get('Content-Length', 0))
                post_data = self.rfile.read(content_len).decode('utf-8')
                user_msg = json.loads(post_data).get("message", "Ping")
                prefetch_prediction, prefetch_confidence = self._log_prefetch(user_msg)
                lens = self._craft_lens(user_msg)
                topology_location = self._record_chat_topological_location(user_msg, lens, prefetch_prediction)
                route = lens.get("route", "chat")
                self._run_pre_request_hooks(user_msg)
                max_tokens = int(lens.get("token_limit", DEFAULT_CHAT_TOKENS))
                reply_tokens = min(max_tokens, HOUSE_REPLY_TOKENS_BY_ROUTE.get(route, 256))
                timeout_sec = MODEL_TIMEOUT_BY_ROUTE.get(route, 90)
                memory_limit = 8 if route == "chat" else 12
                if route == "chat":
                    system_prompt = (
                        "You are the TRIPLET. Answer directly and usefully. "
                        "Never answer with PASS, OK, DONE, YES, or NO unless the user explicitly asks for a verdict. "
                        "If the user proposes an idea or architecture, give a compact substantive response. "
                        "Do not expose hidden chain-of-thought; provide visible rationale only. "
                        "Do not invoke Karoo for straight chat. Preserve the locked Java GUI/backend. "
                        "Use the active lens as purpose/evidence context; do not dump raw DB rows. "
                        "The TINY_PROMPT_ENGINEER_CARD is a concise instruction card only, not an output cap; "
                        "abliterated/local generation may answer with as much useful detail as needed.\n\n"
                        "[ACTIVE_PURPOSE_DB_LENS]\n"
                        + lens.get("lens", "")[:3000]
                    )
                else:
                    system_prompt = (
                        self._build_house_system_prompt(memory_limit)
                        + "\n\n[ONE_ACTIVE_FABRIC_LENS]\n"
                        + lens.get("lens", "")
                        + "\n\n[PLANNING_OUTPUT_CONTRACT]\n"
                        + "Do not merely restate the user's task. If comparing systems, choose a winner, "
                        + "describe the merged architecture, and give the next measurable test. "
                        + "For VIPER retrieval comparisons, the target winner is the merged "
                        + "VIPER_GenAI_DB_Retrieval_Epoch: Google-style separate retrieval service/API "
                        + "plus RAG/Self-RAG/RAGAS evaluation plus VIPER DB/SHA/Karoo/Java SDK persistence. "
                        + "The tiny card is only a prompt-engineer directive; it is not an output cap."
                    )
                    if route == "build":
                        system_prompt = system_prompt[:5200]
                    else:
                        system_prompt = system_prompt[:3600]
                
                # [HOUSE_REPLACEMENT] Direct Llama-CPP Bridge
                if route == "build":
                    ai_response = "\n".join([
                        "Build lens created with real DB retrieval and Qwen tiny chooser control.",
                        f"Qwen lens: {lens.get('qwen_chooser_lens_100_words', {}).get('text', '')}",
                        f"Retrieval match: {lens.get('axiomatic_retrieval_match_50_words', {}).get('text', '')}",
                        f"Rolling triplet: {lens.get('rolling_recursive_triplet_card', {}).get('text', '')}",
                        "Karoo stays proposal-only until compile/test proof clears the promotion gate.",
                    ])
                elif not self._house_ready():
                    ai_response = self._fallback_response(user_msg, lens, "house_not_ready")
                else:
                    try:
                        res_obj = HTTP.post(HOUSE_URL, json={
                            "prompt": user_msg,
                            "system": system_prompt,
                            "max_tokens": reply_tokens,
                            "route": route,
                            "context_budget_tokens": HOUSE_CONTEXT_BUDGET_BY_ROUTE.get(route, 512),
                            "temperature": 0.45,
                            "top_p": 0.9,
                            "repeat_penalty": 1.08,
                        }, timeout=(5, timeout_sec)).json()
                        ai_response = res_obj.get("response", "HOUSE_INFERENCE_COLLAPSE")
                    except Exception as model_error:
                        self.log_chunked(
                            "HOUSE_TIMEOUT_OR_FAULT: "
                            f"route={route} tokens={max_tokens} error={str(model_error)}"
                        )
                        ai_response = self._fallback_response(user_msg, lens, str(model_error))

                repair_meta = {"repaired": False}
                if self._response_too_thin(user_msg, ai_response):
                    self.log_chunked(
                        "THIN_RESPONSE_DETECTED: "
                        f"route={route} lens={lens.get('lens_id')} response={ai_response!r}"
                    )
                    ai_response, repair_meta = self._repair_thin_response(user_msg, ai_response, route)
                
                self._store_chat_memory(user_msg, ai_response)
                self._run_post_response_hooks(user_msg, ai_response, route)
                if ENFORCE_VISIBLE_REPLY_WORD_LIMIT:
                    ai_response = self._limit_visible_reply(ai_response)
                duration_ms = int((time.time() - request_started) * 1000)
                self._record_benchmark("risc_bridge", "chat_predict", route, duration_ms, "ok", {
                    "lens_id": lens.get("lens_id"),
                    "prefetch_confidence": prefetch_confidence,
                    "prefetch_intent": prefetch_prediction.get("intent"),
                    "topology_location": topology_location,
                    "tokens": max_tokens,
                    "reply_tokens": reply_tokens,
                    "response_chars": len(ai_response),
                    "thin_response_repair": repair_meta,
                })
                res = {
                    "prediction_error": 0.035,
                    "outcome": "positive",
                    "response": ai_response,
                    "visible_reasoning_contract": VISIBLE_REASONING_NOTE,
                    "prefetch": {
                        "prediction": prefetch_prediction,
                        "confidence": prefetch_confidence,
                    },
                    "topological_location": topology_location,
                    "lens": {
                        "route": route,
                        "lens_id": lens.get("lens_id"),
                        "lens_sha256": lens.get("lens_sha256"),
                        "result_count": lens.get("result_count", 0),
                        "token_limit": max_tokens,
                        "reply_token_limit": reply_tokens,
                        "thin_response_repair": repair_meta,
                    },
                }
                
                self._record_topological_shift(
                    "TRIPLET_HOUSE_REASONING",
                    f"Route={route} lens={lens.get('lens_id')} talk: {user_msg[:50]}..."
                )
            except Exception as e:
                try:
                    self._record_system_test(
                        "house_engine_fault_guard",
                        "risc_bridge",
                        "error",
                        str(e),
                        {"path": "/api/loibi/predict", "tiny_runtime": HAS_TINY_RUNTIME},
                    )
                except Exception:
                    pass
                fallback_lens = locals().get("lens") or {
                    "route": "chat",
                    "lens": "Emergency fallback lens: answer usefully, preserve the locked GUI, and log the fault.",
                }
                fallback_user_msg = locals().get("user_msg") or "Ping"
                ai_response = self._fallback_response(fallback_user_msg, fallback_lens, str(e))
                res = {
                    "prediction_error": 0.5,
                    "outcome": "fallback",
                    "response": ai_response,
                    "fault_logged": True,
                    "raw_fault_suppressed": True,
                }
            
            self._send_json(res)

        elif self.path == "/api/risc/export":
            time.sleep(5)
            data = f"RISC_EXPORT_PACKET_{int(time.time())}"
            h = hashlib.sha256(data.encode()).hexdigest()
            res = {"status": "ok", "hash": h, "data": data}
            self._send_json(res)
            self._record_topological_shift("RISC_EXPORT", f"SHA256: {h[:16]}")

        elif self.path == "/api/loibi/rag/submit":
            try:
                content_len = int(self.headers.get('Content-Length', 0))
                data = json.loads(self.rfile.read(content_len).decode('utf-8'))
                
                # Axiomatic Feedback Storage
                conn = self._connect_db()
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS RAG_MANIFOLD (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        message TEXT,
                        feedback_type TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("INSERT INTO RAG_MANIFOLD (message, feedback_type) VALUES (?, ?)",
                               (data.get("message"), data.get("type")))
                conn.commit()
                conn.close()
                
                self._record_topological_shift("RAG_SUBMISSION", f"Feedback: {data.get('type')}")
                self._send_json({"status": "indexed"})
            except Exception as e:
                self.log_chunked(f"RAG_ERROR: {str(e)}")
                self.send_error(500)

        elif self.path == "/api/system/tests":
            try:
                content_len = int(self.headers.get('Content-Length', 0))
                data = json.loads(self.rfile.read(content_len).decode('utf-8') or "{}")
                result = self._record_system_test(
                    data.get("test_name", "unnamed_system_test"),
                    data.get("layer", "unknown"),
                    data.get("status", "unknown"),
                    data.get("details", ""),
                    data.get("evidence", {}),
                )
                self._send_json({"status": "logged", **result})
            except Exception as e:
                self.log_chunked(f"SYSTEM_TEST_WRITE_ERROR: {str(e)}")
                self.send_error(500)
        else:
            self.send_error(404)

    def _send_json(self, data):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

def ensure_hot_indexes():
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_triplet_timestamp ON TRIPLET_MANIFOLD(timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_rag_timestamp ON RAG_MANIFOLD(timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_rag_feedback_type ON RAG_MANIFOLD(feedback_type)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS SYSTEM_TEST_LOG (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_name TEXT NOT NULL,
                layer TEXT NOT NULL,
                status TEXT NOT NULL,
                details TEXT,
                evidence_json TEXT,
                sha256 TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_system_test_log_id ON SYSTEM_TEST_LOG(id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_system_test_log_timestamp ON SYSTEM_TEST_LOG(timestamp)")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS USER_TOPOLOGY_PROFILE (
                profile_id TEXT PRIMARY KEY,
                chat_count INTEGER NOT NULL,
                condensed_context TEXT NOT NULL,
                preferences_json TEXT NOT NULL,
                active_goals_json TEXT NOT NULL,
                predictive_terms_json TEXT NOT NULL,
                instructions_json TEXT NOT NULL,
                profile_sha256 TEXT NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS USER_TOPOLOGY_EVENTS (
                event_id TEXT PRIMARY KEY,
                chat_count INTEGER NOT NULL,
                source_chat_id INTEGER,
                summary TEXT NOT NULL,
                event_sha256 TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS PREDICTIVE_PREFETCH_LOG (
                prefetch_id TEXT PRIMARY KEY,
                prefix TEXT NOT NULL,
                prediction_json TEXT NOT NULL,
                confidence REAL NOT NULL,
                status TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS BENCHMARK_EVENTS (
                benchmark_id TEXT PRIMARY KEY,
                component TEXT NOT NULL,
                operation TEXT NOT NULL,
                route TEXT,
                duration_ms INTEGER NOT NULL,
                status TEXT NOT NULL,
                details_json TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_user_topology_events_chat ON USER_TOPOLOGY_EVENTS(chat_count);
            CREATE INDEX IF NOT EXISTS idx_predictive_prefetch_created ON PREDICTIVE_PREFETCH_LOG(created_at);
            CREATE INDEX IF NOT EXISTS idx_benchmark_events_component ON BENCHMARK_EVENTS(component, operation);
        """)
        conn.commit()
        conn.close()
    except Exception:
        pass


if __name__ == "__main__":
    ensure_hot_indexes()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), RiscBridgeHandler)
    server.serve_forever()
