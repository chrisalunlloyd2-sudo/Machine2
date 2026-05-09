import argparse
import hashlib
import json
import os
import random
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


HOME = Path(r"C:\Users\viper")
ROOT = HOME / "VIPER_JAVA_RISC"
DB_PATH = HOME / "gemini_bridge.db"
FABRIC_SOURCE = HOME / ".old" / "AIEngine" / "external_sources" / "fabric"
TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

try:
    from tiny_model_runtime import (
        axiomatic_retrieval_match,
        model_status as tiny_model_status,
        qwen_choose_lens,
        qwen_rolling_triplet_card,
    )

    HAS_TINY_RUNTIME = True
except Exception as tiny_import_error:
    HAS_TINY_RUNTIME = False
    TINY_IMPORT_ERROR = str(tiny_import_error)

STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "your",
    "you", "can", "could", "would", "should", "have", "has", "are", "was",
    "were", "but", "not", "all", "any", "our", "out", "then", "than",
}

BUILD_TERMS = {
    "build", "make", "create", "write", "patch", "fix", "implement",
    "code", "program", "app", "application", "automate", "ship", "deploy",
    "download", "install", "spin", "wire", "hook", "sync", "backup", "stage",
    "fork", "crawl", "benchmark", "test",
}

PLAN_TERMS = {
    "plan", "architecture", "design", "breakdown", "strategy", "protocol",
    "epoch", "logic", "topological", "network", "agent", "agents", "swarm",
    "karoo", "loihi", "acl", "kqml", "fabric", "architechture",
    "reasoning", "rationale", "chain", "thought", "novel",
    "compare", "winner", "merge", "genetic", "upgrade", "standards",
    "checkpoint", "epoch", "nas", "github", "loihi", "lava",
}

CHAT_TERMS = {
    "hello", "hi", "thanks", "thank", "lol", "nice", "what", "why",
    "explain", "think", "feel", "question",
}

SOURCE_TRUST_WEIGHTS = {
    "USER_TOPOLOGY_PROFILE": 9,
    "CHAT_MEMORY": 8,
    "CODE_BLOCKCHAIN_DB_SUCCESS": 10,
    "LOGIC_BLOCKCHAIN_QUEUE_SHIPPED": 10,
    "BLOCKCHAIN_LEDGER_SUCCESS": 9,
    "KAROO_CANDIDATES": 8,
    "TOPO_APPROVAL_REPORTS": 8,
    "TOPO_CANDIDATES": 8,
    "TOPO_CHUNKS": 7,
    "GLOBAL_TODO_QUEUE": 7,
    "GLOBAL_ACL_MESSAGES": 7,
    "TRIPLET_MANIFOLD": 6,
    "RAG_MANIFOLD": 6,
    "GAME_DATA": 6,
    "WEBCRAWL_RESEARCH_REQUESTS": 5,
    "INDUSTRY_RESEARCH_NOTES": 9,
}

GENERIC_SCAN_EXCLUDE = {
    "AI_CHOOSER_ACTIVE_LENSES",
    "AI_CHOOSER_REVIEWS",
    "DATA_RETRIEVAL_EVENTS",
    "FABRIC_LENSES",
    "FABRIC_TEMPLATE_SNAPSHOTS",
    "PREDICTIVE_PREFETCH_LOG",
    "CHAT_TOPOLOGICAL_LOCATION",
    "CONVERSATION_BINOMIAL_SUMMARY",
    "SECURITY_SENTINEL_SEEN",
    "sqlite_sequence",
    "USER_TOPOLOGY_PROFILE",
    "CHAT_MEMORY",
    "CODE_BLOCKCHAIN_DB",
    "LOGIC_BLOCKCHAIN_QUEUE",
    "BLOCKCHAIN_LEDGER",
    "TRIPLET_MANIFOLD",
    "RAG_MANIFOLD",
    "TOPO_CHUNKS",
    "TOPO_APPROVAL_REPORTS",
    "GLOBAL_TODO_QUEUE",
    "GLOBAL_ACL_MESSAGES",
    "GAME_DATA",
    "WEBCRAWL_RESEARCH_REQUESTS",
    "SYSTEM_TEST_LOG",
    "BENCHMARK_EVENTS",
}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def unique_prefix(prefix, ask_sha):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"{prefix}_{stamp}_{ask_sha[:10]}_{random.randrange(16**4):04x}"


def connect_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    conn.row_factory = sqlite3.Row
    return conn


def migrate(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS DATA_RETRIEVAL_EVENTS (
            event_id TEXT PRIMARY KEY,
            ask_sha256 TEXT NOT NULL,
            ask_preview TEXT NOT NULL,
            route TEXT NOT NULL,
            token_limit INTEGER NOT NULL,
            lens_id TEXT NOT NULL,
            result_count INTEGER NOT NULL,
            decision_json TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS FABRIC_LENSES (
            lens_id TEXT PRIMARY KEY,
            route TEXT NOT NULL,
            ask_sha256 TEXT NOT NULL,
            token_limit INTEGER NOT NULL,
            lens_text TEXT NOT NULL,
            lens_sha256 TEXT NOT NULL,
            sources_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS KAROO_EPOCH_REQUESTS (
            epoch_id TEXT PRIMARY KEY,
            ask_sha256 TEXT NOT NULL,
            route TEXT NOT NULL,
            loop_count INTEGER NOT NULL,
            actor_critic TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'proposal_only',
            contract_json TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS FABRIC_TEMPLATE_SNAPSHOTS (
            template_id TEXT PRIMARY KEY,
            route TEXT NOT NULL,
            ask_sha256 TEXT NOT NULL,
            template_text TEXT NOT NULL,
            template_sha256 TEXT NOT NULL,
            hooks_json TEXT NOT NULL,
            noise_policy_json TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS WEBCRAWL_RESEARCH_REQUESTS (
            request_id TEXT PRIMARY KEY,
            ask_sha256 TEXT NOT NULL,
            route TEXT NOT NULL,
            query_json TEXT NOT NULL,
            noise_policy_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued_proposal_only',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

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

        CREATE TABLE IF NOT EXISTS AXIOMATIC_RETRIEVAL_MATCHES (
            match_id TEXT PRIMARY KEY,
            ask_sha256 TEXT NOT NULL,
            route TEXT NOT NULL,
            fabric_layer TEXT NOT NULL,
            match_text TEXT NOT NULL,
            status TEXT NOT NULL,
            candidate_count INTEGER NOT NULL,
            model_meta_json TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS TINY_MODEL_EVENTS (
            event_id TEXT PRIMARY KEY,
            ask_sha256 TEXT,
            model_role TEXT NOT NULL,
            status TEXT NOT NULL,
            details_json TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS ROLLING_TRIPLET_RUNS (
            triplet_id TEXT PRIMARY KEY,
            ask_sha256 TEXT NOT NULL,
            route TEXT NOT NULL,
            fabric_layer TEXT NOT NULL,
            chooser_lens_text TEXT NOT NULL,
            retrieval_match_text TEXT NOT NULL,
            rolling_card_text TEXT NOT NULL,
            status TEXT NOT NULL,
            meta_json TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS USER_WORD_STATS (
            term TEXT PRIMARY KEY,
            count INTEGER NOT NULL DEFAULT 0,
            route_hits_json TEXT NOT NULL DEFAULT '{}',
            last_seen_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS USER_TOPOLOGICAL_WANTS (
            want_key TEXT PRIMARY KEY,
            count INTEGER NOT NULL DEFAULT 0,
            last_ask_sha256 TEXT NOT NULL,
            last_route TEXT NOT NULL,
            last_seen_at DATETIME DEFAULT CURRENT_TIMESTAMP
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

        CREATE INDEX IF NOT EXISTS idx_retrieval_ask ON DATA_RETRIEVAL_EVENTS(ask_sha256);
        CREATE INDEX IF NOT EXISTS idx_fabric_lenses_route ON FABRIC_LENSES(route);
        CREATE INDEX IF NOT EXISTS idx_karoo_epoch_status ON KAROO_EPOCH_REQUESTS(status);
        CREATE INDEX IF NOT EXISTS idx_fabric_template_route ON FABRIC_TEMPLATE_SNAPSHOTS(route);
        CREATE INDEX IF NOT EXISTS idx_webcrawl_research_status ON WEBCRAWL_RESEARCH_REQUESTS(status);
        CREATE INDEX IF NOT EXISTS idx_ai_chooser_reviews_status ON AI_CHOOSER_REVIEWS(review_status);
        CREATE INDEX IF NOT EXISTS idx_axiomatic_matches_route ON AXIOMATIC_RETRIEVAL_MATCHES(route, created_at);
        CREATE INDEX IF NOT EXISTS idx_tiny_model_events_role ON TINY_MODEL_EVENTS(model_role, created_at);
        CREATE INDEX IF NOT EXISTS idx_rolling_triplet_route ON ROLLING_TRIPLET_RUNS(route, created_at);
        CREATE INDEX IF NOT EXISTS idx_benchmark_events_component ON BENCHMARK_EVENTS(component, operation);
        """
    )


def tokenize(text, limit=32):
    words = re.findall(r"[A-Za-z0-9_#.+-]{3,}", text.lower())
    scored = []
    seen = set()
    for word in words:
        if word in STOPWORDS or word in seen:
            continue
        seen.add(word)
        score = len(word)
        if word in BUILD_TERMS or word in PLAN_TERMS:
            score += 12
        scored.append((score, word))
    scored.sort(reverse=True)
    return [word for _, word in scored[:limit]]


def classify_ask(text):
    lower = text.lower()
    tokens = set(tokenize(text, 80))
    build_score = sum(1 for term in BUILD_TERMS if term in tokens or term in lower)
    plan_score = sum(1 for term in PLAN_TERMS if term in tokens or term in lower)
    chat_score = sum(1 for term in CHAT_TERMS if term in tokens or term in lower)
    user_performative_phrases = (
        "spin up", "wire", "hook", "sync", "ship", "checkpoint",
        "upgrade epoch", "ping", "open notes", "backup", "crawl",
        "benchmark", "stage", "fork", "deploy", "download", "install",
    )
    if any(phrase in lower for phrase in user_performative_phrases):
        build_score += 2
    has_directive = bool(re.search(
        r"\b(can you|please|make sure|add|implement|fix|build|create|wire|hook|spin up|test|download|install)\b",
        lower,
    ))

    if build_score >= 2 or (has_directive and build_score >= 1):
        route = "build"
    elif plan_score >= 2 or (has_directive and plan_score >= 1):
        route = "planning"
    else:
        route = "chat"

    word_count = len(re.findall(r"\S+", text))
    if route == "chat":
        token_limit = 1024 if word_count < 90 else 1536
    elif route == "planning":
        token_limit = 3072 if word_count < 220 else 4096
    else:
        token_limit = 4096 if word_count < 260 else 6144

    return {
        "route": route,
        "token_limit": token_limit,
        "scores": {
            "build": build_score,
            "planning": plan_score,
            "chat": chat_score,
            "word_count": word_count,
        },
        "tokens": tokenize(text),
    }


def table_exists(conn, table):
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def score_text(text, tokens):
    lower = text.lower()
    score = 0
    for token in tokens:
        if token in lower:
            score += 1 + min(5, lower.count(token))
    return score


def compact_words(text, limit=15, char_limit=220):
    words = re.findall(r"\S+", str(text or ""))
    compact = " ".join(words[:limit])
    if len(compact) > char_limit:
        return compact[: max(0, char_limit - 3)] + "..."
    return compact


def infer_purpose(ask, decision):
    lower = ask.lower()
    if decision["route"] == "build":
        action = "perform_task"
        purpose = "turn the user request into one safe code/change proposal with compile/test proof"
    elif decision["route"] == "planning":
        action = "plan_or_architect"
        purpose = "create a useful operating architecture, protocol, or next-step plan"
    else:
        action = "commence_chat"
        purpose = "answer conversationally with enough context and no unnecessary tool/agent loop"

    if any(term in lower for term in ("hurt", "finger", "cut", "pain")):
        purpose += "; keep typing burden low and avoid asking unnecessary questions"
    if any(term in lower for term in ("retrieval", "retreival", "db", "database", "data")):
        purpose += "; improve DB-backed evidence retrieval before response"
    if any(term in lower for term in ("web", "research", "industry", "standard", "standards")):
        purpose += "; include reduced web/research snippets when local DB lacks enough evidence"

    return {
        "purpose": purpose,
        "action": action,
        "route": decision["route"],
        "ask_card_15": compact_words(ask, 15),
        "success_criteria": [
            "answer uses the retrieved evidence packet",
            "irrelevant DB rows are excluded or marked low confidence",
            "web snippets are reduced to claims + source + applicability + risk",
            "task directions are explicit enough for the model/agent to act",
        ],
    }


def tiny_prompt_engineer_card(purpose, decision, web_plan):
    if decision["route"] == "build":
        directive = (
            "Use the evidence cards to perform the smallest safe build step. Prefer successful ledger code. "
            "If evidence is insufficient, request or queue reduced web snippets. Return action, proof, and next test."
        )
    elif decision["route"] == "planning":
        directive = (
            "Compare the candidate systems, choose a winner for VIPER, explain why, then give the merged architecture "
            "and next test. Use evidence cards; do not drift into generic summaries."
        )
    else:
        directive = (
            "Answer naturally but ground the reply in the purpose and evidence cards. Do not dump raw retrieval. "
            "If the user asks to compare, choose a winner."
        )
    if web_plan.get("status") == "queued_if_needed":
        directive += " Web snippets are claim/source/hash/applicability/risk only."
    return compact_words(directive, 50, 420)


def query_variants(ask, tokens, route):
    base = " ".join(tokens[:10])
    variants = [
        ask,
        base,
        " ".join(tokens[:6]),
    ]
    if route == "build":
        variants.extend([
            "successful code compile test " + base,
            "karoo candidate shipped logic " + base,
        ])
    elif route == "planning":
        variants.extend([
            "architecture protocol topology " + base,
            "sop agent workflow evidence " + base,
        ])
    else:
        variants.extend([
            "user preference recent chat " + base,
            "direct answer context " + base,
        ])
    clean = []
    seen = set()
    for variant in variants:
        normalized = re.sub(r"\s+", " ", variant.strip())
        if normalized and normalized not in seen:
            clean.append(normalized)
            seen.add(normalized)
    return clean[:6]


def source_trust(source_name):
    if source_name.startswith("FULL_DB::"):
        table = source_name.split("::", 1)[1]
        return SOURCE_TRUST_WEIGHTS.get(table, 3)
    return SOURCE_TRUST_WEIGHTS.get(source_name, 4)


def route_fit(source_name, route):
    source = source_name.upper()
    if "INDUSTRY_RESEARCH" in source:
        return 5 if route in {"planning", "build", "chat"} else 3
    if route == "build" and any(term in source for term in ("CODE", "BLOCKCHAIN", "CANDIDATE", "QUEUE")):
        return 5
    if route == "planning" and any(term in source for term in ("TOPO", "TODO", "ACL", "GAME", "AGENT", "POLICY")):
        return 5
    if route == "chat" and any(term in source for term in ("CHAT", "USER", "RAG", "TRIPLET")):
        return 4
    return 1


def compress_source_card(item, purpose, route):
    data = item.get("data", {})
    joined = " | ".join(f"{key}={value}" for key, value in data.items())
    card = {
        "source": item.get("source", "unknown"),
        "sha256": item.get("sha256", "")[:16],
        "score": item.get("score", 0),
        "trust": item.get("trust", source_trust(item.get("source", ""))),
        "route_fit": item.get("route_fit", route_fit(item.get("source", ""), route)),
        "compound_score": item.get("compound_score", item.get("score", 0)),
        "card_15": compact_words(joined, 15),
        "applicability": compact_words(f"Use for {purpose['action']} via {item.get('source', 'unknown')}", 15),
        "risk": "may be stale or keyword-only; verify before promotion",
    }
    return card


def rerank_and_compress(items, purpose, tokens, route, limit=12):
    enriched = []
    for index, item in enumerate(items):
        source_name = item.get("source", "")
        if route != "build" and any(term in source_name.upper() for term in ("CODE_BLOCKCHAIN", "LOGIC_BLOCKCHAIN_QUEUE", "BLOCKCHAIN_LEDGER")):
            item = dict(item)
            item["score"] = max(0, int(item.get("score", 0)) - 24)
        trust = source_trust(item.get("source", ""))
        fit = route_fit(item.get("source", ""), route)
        diversity = max(0, 4 - index // 4)
        density = min(6, len(json.dumps(item.get("data", {}), ensure_ascii=True)) // 180)
        compound = int(item.get("score", 0)) + trust + fit + diversity + density
        item = dict(item)
        item["trust"] = trust
        item["route_fit"] = fit
        item["compound_score"] = compound
        item["retrieval_epoch"] = "query_expand_hybrid_rerank_compress"
        item["card"] = compress_source_card(item, purpose, route)
        enriched.append(item)
    enriched.sort(key=lambda row: (row["compound_score"], row["trust"], row.get("score", 0)), reverse=True)

    selected = []
    seen_sources = {}
    for item in enriched:
        source = item.get("source", "unknown")
        count = seen_sources.get(source, 0)
        if count >= 3 and len(selected) >= 6:
            continue
        selected.append(item)
        seen_sources[source] = count + 1
        if len(selected) >= limit:
            break
    return selected


def evidence_sufficiency(cards, route):
    if not cards:
        return {
            "status": "insufficient",
            "confidence": 0.1,
            "reason": "no retrieval cards found",
        }
    trust_sum = sum(card.get("trust", 0) for card in cards)
    fit_sum = sum(card.get("route_fit", 0) for card in cards)
    confidence = min(0.96, 0.12 + trust_sum / 80 + fit_sum / 70)
    needed = 0.55 if route == "chat" else 0.7
    return {
        "status": "sufficient" if confidence >= needed else "needs_web_or_more_db",
        "confidence": round(confidence, 3),
        "reason": "computed from source trust, route fit, and card count",
    }


def web_snippet_plan(ask, decision, purpose, cards, sufficiency):
    tokens = decision["tokens"]
    return {
        "status": "queued_if_needed" if sufficiency["status"] != "sufficient" or decision["route"] != "chat" else "not_needed_for_direct_chat",
        "query": " ".join(tokens[:10]),
        "ask_card_15": compact_words(ask, 15),
        "purpose_card_15": compact_words(purpose["purpose"], 15),
        "required_format": [
            "claim",
            "source_url_or_local_path",
            "source_sha256",
            "applicability",
            "risk",
        ],
        "noise_policy": "discard marketing/duplicates; keep API contracts, standards, test commands, safety constraints",
    }


def merged_winner_architecture(decision, sufficiency):
    return {
        "name": "VIPER_GenAI_DB_Retrieval_Epoch",
        "winner_logic": "separate retrieval sidecar/API plus purpose-first Fabric lens",
        "patterns_merged": [
            "RAG: explicit DB/ledger memory grounds generation",
            "Self-RAG: retrieve only when useful and critique sufficiency",
            "RAGAS/ARES: evaluate context relevance, faithfulness, answer relevance",
            "Google GenAI DB Retrieval App: DB-backed retrieval service triggered by agent/tool flow",
            "VIPER: topological purpose cards, SHA-256 ledger, Karoo proposal gate, Java SDK persistence",
        ],
        "runtime_flow": [
            "classify route",
            "infer purpose",
            "rewrite/expand query",
            "retrieve local DB/ledger/success records",
            "trust+routing rerank",
            "compress to 15-word evidence cards",
            "check sufficiency",
            "queue web snippets only if needed",
            "send task directions to chat/build/planning",
            "log tests/eval/proof",
        ],
        "promotion_metrics": {
            "context_relevance": "retrieved cards match purpose",
            "faithfulness": "answer uses cards without inventing unsupported facts",
            "answer_relevance": "answer performs the requested chat/planning/build task",
            "latency": "avoid web/tool calls when DB sufficiency is high",
            "safety": "no raw data export; no GUI mutation without request",
        },
        "current_sufficiency": sufficiency,
        "next_vector_layer": "add BM25/vector/topology similarity behind the retrieval API when resources permit",
    }


def search_table(conn, table, columns, label, tokens, limit=24):
    if not table_exists(conn, table):
        return []
    safe_cols = ", ".join(columns)
    try:
        rows = conn.execute(f"SELECT {safe_cols} FROM {table} LIMIT 800").fetchall()
    except sqlite3.Error:
        return []
    results = []
    for row in rows:
        parts = []
        data = {}
        for col in columns:
            value = row[col] if col in row.keys() else None
            if value is None:
                continue
            text = str(value)
            data[col] = text[:700]
            parts.append(text)
        haystack = "\n".join(parts)
        score = score_text(haystack, tokens)
        if score:
            results.append({
                "source": label,
                "score": score,
                "data": data,
                "sha256": sha256_text(haystack),
            })
    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:limit]


def generic_search_all_tables(conn, tokens, limit_per_table=3, max_tables=80):
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    results = []
    for table_row in tables[:max_tables]:
        table = table_row["name"]
        if table in GENERIC_SCAN_EXCLUDE:
            continue
        try:
            cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
            col_names = [col["name"] for col in cols]
            if not col_names:
                continue
            select_cols = col_names[:8]
            safe_cols = ", ".join(select_cols)
            rows = conn.execute(f"SELECT {safe_cols} FROM {table} LIMIT 250").fetchall()
        except sqlite3.Error:
            continue
        table_hits = []
        for row in rows:
            data = {}
            parts = []
            for col in select_cols:
                value = row[col] if col in row.keys() else None
                if value is None:
                    continue
                text = str(value)
                data[col] = text[:500]
                parts.append(text)
            haystack = "\n".join(parts)
            score = score_text(haystack, tokens)
            if score:
                table_hits.append({
                    "source": f"FULL_DB::{table}",
                    "score": score,
                    "data": data,
                    "sha256": sha256_text(haystack),
                })
        table_hits.sort(key=lambda item: item["score"], reverse=True)
        results.extend(table_hits[:limit_per_table])
    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:24]


def industry_research_cards(tokens, route):
    joined = " ".join(tokens).lower()
    wants_research = any(term in joined for term in (
        "rag", "retrieval", "retreival", "research", "industry", "standard",
        "standards", "database", "db", "agent", "react", "web"
    ))
    if not wants_research:
        return []
    cards = [
        {
            "source": "INDUSTRY_RESEARCH_NOTES",
            "score": score_text("RAG combines parametric model memory with explicit non-parametric retrieved memory and improves factuality", tokens) + 40,
            "data": {
                "claim": "Use retrieval to ground generation in explicit external memory instead of relying only on model weights.",
                "source_url": "https://arxiv.org/abs/2005.11401",
                "applicability": "VIPER DB/ledger acts as non-parametric memory.",
                "risk": "Current local version lacks vector embeddings; use hybrid keyword/trust until vector layer exists.",
            },
            "sha256": sha256_text("RAG Lewis 2020 explicit non-parametric memory"),
        },
        {
            "source": "INDUSTRY_RESEARCH_NOTES",
            "score": score_text("Self-RAG adaptively retrieve generate critique reflection factuality relevance", tokens) + 40,
            "data": {
                "claim": "Retrieve only when useful, then critique relevance and factuality before final generation.",
                "source_url": "https://arxiv.org/abs/2310.11511",
                "applicability": "VIPER sufficiency check decides whether local DB is enough or web/research is needed.",
                "risk": "Local critique is deterministic for now; model judge can be added later.",
            },
            "sha256": sha256_text("Self-RAG adaptive retrieval critique"),
        },
        {
            "source": "INDUSTRY_RESEARCH_NOTES",
            "score": score_text("RAGAS context relevance faithfulness answer relevance evaluation", tokens) + 40,
            "data": {
                "claim": "Evaluate RAG with context relevance, answer faithfulness, and answer relevance.",
                "source_url": "https://arxiv.org/abs/2309.15217",
                "applicability": "VIPER tests should log whether retrieved cards were relevant and faithfully used.",
                "risk": "Metrics are approximated until a judge/eval runner is wired.",
            },
            "sha256": sha256_text("RAGAS context relevance faithfulness answer relevance"),
        },
        {
            "source": "INDUSTRY_RESEARCH_NOTES",
            "score": score_text("Google Cloud GenAI database retrieval app RAG ReACT separate retrieval service SQL vector security latency cost", tokens) + 44,
            "data": {
                "claim": "Run retrieval as a separate service/API, use DB precision plus semantic similarity, and gate by security, scale, quality, latency, and cost.",
                "source_url": "https://cloud.google.com/blog/products/databases/introducing-sample-genai-databases-retrieval-app",
                "applicability": "VIPER should keep the Java SDK/bridge as orchestration and the retrieval sidecar as a separate service.",
                "risk": "Cloud/vector pieces are future layers; local SQLite must remain conservative and auditable.",
            },
            "sha256": sha256_text("Google GenAI Databases Retrieval App RAG ReACT service API"),
        },
        {
            "source": "INDUSTRY_RESEARCH_NOTES",
            "score": score_text("LangChain retrieval 2-step agentic hybrid RAG knowledge base retrieval pipeline", tokens) + 36,
            "data": {
                "claim": "Choose retrieval architecture by task: simple two-step for predictable queries, agentic/hybrid for tool-heavy tasks.",
                "source_url": "https://docs.langchain.com/oss/python/langchain/retrieval",
                "applicability": "VIPER route decides chat/planning/build retrieval depth.",
                "risk": "Agentic retrieval can increase latency; use sufficiency gates.",
            },
            "sha256": sha256_text("LangChain retrieval architectures"),
        },
    ]
    return cards


def search_database(conn, tokens):
    sources = []
    sources.extend(industry_research_cards(tokens, "unknown"))
    sources.extend(search_table(conn, "USER_TOPOLOGY_PROFILE", [
        "profile_id", "condensed_context", "preferences_json", "active_goals_json", "predictive_terms_json"
    ], "USER_TOPOLOGY_PROFILE", tokens, limit=4))
    sources.extend(search_table(conn, "CHAT_MEMORY", [
        "id", "user_message", "ai_response", "timestamp"
    ], "CHAT_MEMORY", tokens, limit=8))
    sources.extend(search_table(conn, "TRIPLET_MANIFOLD", ["id", "type", "label", "description"], "TRIPLET_MANIFOLD", tokens))
    sources.extend(search_table(conn, "RAG_MANIFOLD", ["id", "message", "feedback_type", "timestamp"], "RAG_MANIFOLD", tokens))
    sources.extend(search_table(conn, "TOPO_CHUNKS", ["id", "subsystem_id", "symbol", "source_path", "metadata_json"], "TOPO_CHUNKS", tokens))
    sources.extend(search_table(conn, "TOPO_APPROVAL_REPORTS", ["id", "subsystem_id", "summary", "status"], "TOPO_APPROVAL_REPORTS", tokens))
    sources.extend(search_table(conn, "GLOBAL_TODO_QUEUE", ["todo_id", "title", "details", "status"], "GLOBAL_TODO_QUEUE", tokens))
    sources.extend(search_table(conn, "GLOBAL_ACL_MESSAGES", ["message_id", "sender", "receiver", "performative", "content"], "GLOBAL_ACL_MESSAGES", tokens))
    sources.extend(search_table(conn, "GAME_DATA", ["game_id", "data_type", "payload_json", "status"], "GAME_DATA", tokens))
    sources.extend(search_table(conn, "WEBCRAWL_RESEARCH_REQUESTS", [
        "request_id", "route", "query_json", "noise_policy_json", "status"
    ], "WEBCRAWL_RESEARCH_REQUESTS", tokens, limit=6))
    sources.extend(search_table(conn, "SYSTEM_TEST_LOG", [
        "id", "test_name", "layer", "status", "details", "evidence_json"
    ], "SYSTEM_TEST_LOG", tokens, limit=6))
    sources.extend(search_table(conn, "BENCHMARK_EVENTS", [
        "benchmark_id", "component", "operation", "route", "status", "details_json"
    ], "BENCHMARK_EVENTS", tokens, limit=6))
    sources.extend(generic_search_all_tables(conn, tokens))
    sources.sort(key=lambda item: item["score"], reverse=True)
    return sources[:48]


def search_successful_code(conn, tokens):
    sources = []
    sources.extend(search_table(conn, "CODE_BLOCKCHAIN_DB", [
        "code_block_id", "source_queue_id", "payload_sha256", "chain_hash", "payload_json", "storage_role"
    ], "CODE_BLOCKCHAIN_DB_SUCCESS", tokens, limit=12))
    sources.extend(search_table(conn, "BLOCKCHAIN_LEDGER", [
        "id", "block_hash", "prev_hash", "data", "timestamp"
    ], "BLOCKCHAIN_LEDGER_SUCCESS", tokens, limit=12))
    if table_exists(conn, "LOGIC_BLOCKCHAIN_QUEUE"):
        try:
            rows = conn.execute("""
                SELECT id, payload_sha256, chain_hash, payload_json, status, attempts
                FROM LOGIC_BLOCKCHAIN_QUEUE
                WHERE status = 'shipped'
                LIMIT 200
            """).fetchall()
            for row in rows:
                haystack = "\n".join(str(row[col]) for col in row.keys())
                score = score_text(haystack, tokens)
                if score:
                    sources.append({
                        "source": "LOGIC_BLOCKCHAIN_QUEUE_SHIPPED",
                        "score": score,
                        "data": {col: str(row[col])[:700] for col in row.keys()},
                        "sha256": sha256_text(haystack),
                    })
        except sqlite3.Error:
            pass
    sources.extend(search_table(conn, "TOPO_CANDIDATES", [
        "id", "experiment_id", "chunk_id", "candidate_sha256", "comparison_count", "confidence", "action", "report"
    ], "KAROO_CANDIDATES", tokens, limit=12))
    filtered = []
    for item in sources:
        data_blob = json.dumps(item["data"], sort_keys=True).lower()
        if any(marker in data_blob for marker in ["shipped", "success", "pass", "approved", "candidate", "logic_block"]):
            item["score"] += 4
            filtered.append(item)
    filtered.sort(key=lambda item: item["score"], reverse=True)
    return filtered[:10]


def noise_policy(route):
    return {
        "route": route,
        "webcrawl": "logical_summary_only",
        "discard": [
            "ads",
            "marketing",
            "duplicate snippets",
            "unverified claims",
            "style-only variants unless comparing syntax",
            "content without license/provenance signal",
        ],
        "keep": [
            "API contracts",
            "compile/test commands",
            "minimal working examples",
            "security constraints",
            "performance notes",
            "project-local successful code hashes",
        ],
        "reduction": "summarize to claims + source hash + applicability + risk",
    }


def template_hooks(route):
    return {
        "database_hooks": [
            "TRIPLET_MANIFOLD",
            "RAG_MANIFOLD",
            "TOPO_CHUNKS",
            "TOPO_APPROVAL_REPORTS",
            "GLOBAL_TODO_QUEUE",
            "GAME_DATA",
        ],
        "programming_success_hooks": [
            "CODE_BLOCKCHAIN_DB",
            "BLOCKCHAIN_LEDGER",
            "LOGIC_BLOCKCHAIN_QUEUE(status=shipped)",
            "TOPO_CANDIDATES",
        ] if route == "build" else [],
        "webcrawl_hooks": [
            "WEBCRAWL_RESEARCH_REQUESTS",
            "approved external docs only",
            "summarize and reduce noise before model injection",
        ],
        "onedrive_slow_pipeline": "hash summaries and approved artifacts only",
    }


def fabric_layer_for_route(route):
    if route == "build":
        return "programming"
    if route == "chat":
        return "chat"
    return "generalist"


def fetch_user_profile(conn):
    profile = {}
    if table_exists(conn, "USER_TOPOLOGY_PROFILE"):
        row = conn.execute(
            """
            SELECT chat_count, condensed_context, preferences_json,
                   active_goals_json, predictive_terms_json, instructions_json,
                   profile_sha256, updated_at
            FROM USER_TOPOLOGY_PROFILE
            WHERE profile_id = 'VIPER_USER_TOPOLOGY_V1'
            """
        ).fetchone()
        if row:
            profile["topology"] = {key: row[key] for key in row.keys()}
    if table_exists(conn, "CONVERSATION_BINOMIAL_SUMMARY"):
        rows = conn.execute(
            """
            SELECT want_summary, action_summary, summary_sha256, created_at
            FROM CONVERSATION_BINOMIAL_SUMMARY
            ORDER BY created_at DESC
            LIMIT 3
            """
        ).fetchall()
        profile["recent_binomial_summaries"] = [dict(row) for row in rows]
    if table_exists(conn, "USER_WORD_STATS"):
        rows = conn.execute(
            """
            SELECT term, count, route_hits_json
            FROM USER_WORD_STATS
            ORDER BY count DESC, last_seen_at DESC
            LIMIT 24
            """
        ).fetchall()
        profile["frequent_terms"] = [dict(row) for row in rows]
    return profile


def update_user_prediction_tables(conn, ask, decision, ask_sha):
    tokens = tokenize(ask, 80)
    wants = {
        "preserve_gui": ("gui" in tokens or "webpage" in tokens or "java" in tokens),
        "real_tiny_models": any(term in tokens for term in ("qwen", "smollm", "danube", "tiny", "model")),
        "database_retrieval": any(term in tokens for term in ("database", "retrieval", "retreival", "db", "data")),
        "agent_network": any(term in tokens for term in ("agent", "agents", "network", "sync", "nas")),
        "rolling_triplet": any(term in tokens for term in ("rolling", "triplet", "recursive", "karoo")),
        "benchmarking": any(term in tokens for term in ("benchmark", "test", "proof", "graphs")),
    }
    route = decision["route"]
    for term in tokens:
        row = conn.execute("SELECT route_hits_json FROM USER_WORD_STATS WHERE term = ?", (term,)).fetchone()
        route_hits = {}
        if row:
            try:
                route_hits = json.loads(row["route_hits_json"] or "{}")
            except Exception:
                route_hits = {}
        route_hits[route] = int(route_hits.get(route, 0)) + 1
        conn.execute(
            """
            INSERT INTO USER_WORD_STATS (term, count, route_hits_json, last_seen_at)
            VALUES (?, 1, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(term) DO UPDATE SET
                count = count + 1,
                route_hits_json = excluded.route_hits_json,
                last_seen_at = CURRENT_TIMESTAMP
            """,
            (term, json.dumps(route_hits, ensure_ascii=True, sort_keys=True)),
        )
    for want_key, active in wants.items():
        if not active:
            continue
        conn.execute(
            """
            INSERT INTO USER_TOPOLOGICAL_WANTS (
                want_key, count, last_ask_sha256, last_route, last_seen_at
            )
            VALUES (?, 1, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(want_key) DO UPDATE SET
                count = count + 1,
                last_ask_sha256 = excluded.last_ask_sha256,
                last_route = excluded.last_route,
                last_seen_at = CURRENT_TIMESTAMP
            """,
            (want_key, ask_sha, route),
        )


def build_dynamic_template(route, token_limit):
    hooks = template_hooks(route)
    policy = noise_policy(route)
    fabric_layer = fabric_layer_for_route(route)
    if route == "build":
        mode = (
            "PROGRAMMING TEMPLATE: retrieve successful code first, then webcrawl for "
            "missing facts, reduce to tested claims, compare with Karoo, and return "
            "a compile-ready proposal."
        )
    elif route == "planning":
        mode = (
            "PLANNING TEMPLATE: retrieve topology and SOPs first, webcrawl only for "
            "current facts, reduce to decision points, then propose gates."
        )
    else:
        mode = (
            "CHAT TEMPLATE: answer directly with generous room, but keep DB/crawl "
            "noise out unless needed."
        )
    return "\n".join([
        "DYNAMIC VIPER FABRIC TEMPLATE",
        f"route: {route}",
        f"fabric_layer: {fabric_layer}",
        f"token_budget: {token_limit}",
        mode,
        "",
        "HOOKS:",
        json.dumps(hooks, ensure_ascii=True, indent=2),
        "",
        "NOISE REDUCTION:",
        json.dumps(policy, ensure_ascii=True, indent=2),
    ]), hooks, policy


def local_fabric_hint(route):
    if FABRIC_SOURCE.exists():
        return {
            "status": "available_local_archive",
            "path": str(FABRIC_SOURCE),
            "mode": "concept-compatible; no template mutation",
        }
    return {
        "status": "not_found",
        "path": str(FABRIC_SOURCE),
        "mode": "using built-in minimal lens templates",
    }


def build_lens(
    ask,
    decision,
    sources,
    code_sources,
    purpose,
    web_plan,
    sufficiency,
    winner,
    tiny_card,
    retrieval_match,
    qwen_lens,
    rolling_card,
    fabric_layer,
):
    route = decision["route"]
    token_limit = decision["token_limit"]
    fabric_hint = local_fabric_hint(route)
    template_text, hooks, policy = build_dynamic_template(route, token_limit)
    db_cards = [item["card"] for item in sources[:8] if "card" in item]
    code_cards = [item["card"] for item in code_sources[:5] if "card" in item]
    if route == "chat":
        contract = (
            "CHAT ROUTE: answer directly. Do not invoke Karoo. Do not propose file "
            "edits unless the user asks for action. Keep it warm and useful. "
            "Use the PURPOSE and DB cards to maintain logical presence without dumping raw data."
        )
        source_lines = [
            f"Retrieval ran and compressed {len(db_cards)} DB cards. "
            "Use only cards that directly help the answer."
        ]
    elif route == "planning":
        contract = (
            "PLANNING ROUTE: retrieve topology/SOPs, optionally queue webcrawl "
            "research, reduce noise to decisions, then run rolling recursive "
            "planning with approval gates. Karoo stays proposal-only."
        )
        source_lines = []
    else:
        contract = (
            "BUILD ROUTE: pull successful code from Karoo DB and SHA ledger first. "
            "Abliterated queues webcrawl/code suggestions only for missing context. "
            "Karoo compares each advancement against three options, logs actor-critic "
            "stop/best decisions, then returns the compile-ready proposal path to "
            "chat. No self-mutation outside the 99.99% + 10% gate."
        )
        source_lines = []

    if route != "chat":
        if code_sources:
            source_lines.append("SUCCESSFUL CODE / LEDGER HOOKS:")
            for i, source in enumerate(code_sources[:5], start=1):
                data = source["data"]
                compact = " | ".join(f"{k}={str(v)[:120]}" for k, v in data.items())
                source_lines.append(
                    f"C{i}. {source['source']} compound={source.get('compound_score', source['score'])} "
                    f"trust={source.get('trust')} fit={source.get('route_fit')} sha={source['sha256'][:12]} :: {compact}"
                )
        for i, source in enumerate(sources[:5], start=1):
            data = source["data"]
            compact = " | ".join(f"{k}={str(v)[:120]}" for k, v in data.items())
            source_lines.append(
                f"{i}. {source['source']} compound={source.get('compound_score', source['score'])} "
                f"trust={source.get('trust')} fit={source.get('route_fit')} sha={source['sha256'][:12]} :: {compact}"
            )
        if not source_lines:
            source_lines.append("No strong DB matches. Use current ask only and log uncertainty.")

    return "\n".join([
        "VIPER FABRIC LENS",
        f"route: {route}",
        f"fabric_layer: {fabric_layer}",
        f"token_limit: {token_limit}",
        f"fabric_source: {fabric_hint['status']} ({fabric_hint['mode']})",
        f"template_sha256: {sha256_text(template_text)}",
        f"tiny_runtime: {'real_qwen_smollm' if HAS_TINY_RUNTIME else 'unavailable'}",
        "",
        "PURPOSE:",
        json.dumps(purpose, ensure_ascii=True, indent=2),
        "",
        "ACTIVE_QWEN_CHOOSER_LENS_100_WORDS:",
        qwen_lens.get("text", ""),
        "",
        "AXIOMATIC_RETRIEVAL_MATCH_50_WORDS:",
        retrieval_match.get("text", ""),
        "",
        "ROLLING_RECURSIVE_TRIPLET_CARD:",
        rolling_card.get("text", ""),
        "",
        "RETRIEVAL_EPOCH:",
        "purpose -> real_DB_retrieval -> SmolLM2_axiom_match -> Qwen2.5_lens -> route_response_or_task",
        "",
        "QUERY_VARIANTS:",
        "\n".join(f"- {variant}" for variant in decision.get("query_variants", [])[:6]),
        "",
        "DB_RETRIEVAL_CARDS:",
        json.dumps({
            "sufficiency": sufficiency,
            "logic_cards": db_cards,
            "successful_code_cards": code_cards,
        }, ensure_ascii=True, indent=2)[:3600],
        "",
        "WEB_SNIPPET_PLAN:",
        json.dumps(web_plan, ensure_ascii=True, indent=2),
        "",
        "MERGED_WINNER_ARCHITECTURE:",
        json.dumps(winner, ensure_ascii=True, indent=2),
        "",
        "TINY_PROMPT_ENGINEER_CARD_50_WORDS:",
        tiny_card,
        "",
        "TASK_DIRECTIONS:",
        "- Read ACTIVE_QWEN_CHOOSER_LENS first and answer/act toward that purpose.",
        "- Use DB_RETRIEVAL_CARDS as the grounded evidence packet.",
        "- Use AXIOMATIC_RETRIEVAL_MATCH as the closest 50-word context card.",
        "- Use ROLLING_RECURSIVE_TRIPLET_CARD to coordinate Qwen/Karoo/abliterated passes.",
        "- If sufficiency is low, say what evidence is missing and use WEB_SNIPPET_PLAN.",
        "- For task requests, perform the smallest useful step and log proof.",
        "- For chat, keep the answer natural but grounded by the cards.",
        "",
        contract,
        "",
        "ASK_SHA256:",
        sha256_text(ask),
        "",
        "TOP TOKENS:",
        ", ".join(decision["tokens"][:24]),
        "",
        "MATCHED LOGIC SOURCES:",
        "\n".join(source_lines),
        "",
        "ACTIVE TEMPLATE:",
        template_text[:1800],
        "",
        "OUTPUT RULES:",
        "- Use exactly one lens for this chat turn.",
        "- Do not answer PASS/OK/DONE unless the user explicitly requests a verdict.",
        "- Preserve the locked Java/Three.js GUI unless the user explicitly asks.",
        "- For build work: one changed variable per test; end-to-end proof required.",
        "- For web research: crawl/log separately, then inject only reduced claims.",
        "- For long asks: use generous budget, summarize intent, then answer the highest-impact part.",
    ])


def craft_lens(ask):
    ask_sha = sha256_text(ask)
    event_id = unique_prefix("RET", ask_sha)
    lens_id = unique_prefix("LENS", ask_sha)
    epoch_id = unique_prefix("KAROO_EPOCH", ask_sha)
    with connect_db() as conn:
        migrate(conn)
        decision = classify_ask(ask)
        decision["query_variants"] = query_variants(ask, decision["tokens"], decision["route"])
        fabric_layer = fabric_layer_for_route(decision["route"])
        update_user_prediction_tables(conn, ask, decision, ask_sha)
        purpose = infer_purpose(ask, decision)
        expanded_tokens = tokenize(" ".join(decision["query_variants"]), 64)
        sources = search_database(conn, expanded_tokens)
        sources = rerank_and_compress(sources, purpose, expanded_tokens, decision["route"], limit=16)
        code_sources = search_successful_code(conn, expanded_tokens) if decision["route"] == "build" else []
        code_sources = rerank_and_compress(code_sources, purpose, expanded_tokens, decision["route"], limit=8)
        cards = [item["card"] for item in sources[:8] if "card" in item]
        sufficiency = evidence_sufficiency(cards, decision["route"])
        web_plan = web_snippet_plan(ask, decision, purpose, cards, sufficiency)
        winner = merged_winner_architecture(decision, sufficiency)
        tiny_card = tiny_prompt_engineer_card(purpose, decision, web_plan)
        user_profile = fetch_user_profile(conn)
        if HAS_TINY_RUNTIME:
            retrieval_match = axiomatic_retrieval_match(
                ask,
                decision["route"],
                purpose,
                (code_sources if decision["route"] == "build" else []) + sources,
            )
            qwen_lens = qwen_choose_lens(
                ask,
                decision["route"],
                fabric_layer,
                decision["token_limit"],
                purpose,
                retrieval_match,
                sources,
                code_sources,
                web_plan,
                user_profile=user_profile,
            )
            rolling_card = qwen_rolling_triplet_card(
                ask,
                decision["route"],
                qwen_lens,
                retrieval_match,
            )
            tiny_status = tiny_model_status()
        else:
            retrieval_match = {
                "text": compact_words(json.dumps((sources[:1] or [{}])[0], ensure_ascii=True), 50, 600),
                "status": "tiny_runtime_import_failed",
                "meta": {"error": globals().get("TINY_IMPORT_ERROR", "unknown")},
            }
            qwen_lens = {
                "text": compact_words(tiny_card, 100, 900),
                "status": "tiny_runtime_import_failed",
                "meta": {"error": globals().get("TINY_IMPORT_ERROR", "unknown")},
            }
            rolling_card = {
                "text": "Qwen chooser unavailable; use deterministic guardrail fallback and keep Karoo proposal-only.",
                "status": "tiny_runtime_import_failed",
                "meta": {"error": globals().get("TINY_IMPORT_ERROR", "unknown")},
            }
            tiny_status = {"enabled": False, "error": globals().get("TINY_IMPORT_ERROR", "unknown")}

        lens = build_lens(
            ask,
            decision,
            sources,
            code_sources,
            purpose,
            web_plan,
            sufficiency,
            winner,
            tiny_card,
            retrieval_match,
            qwen_lens,
            rolling_card,
            fabric_layer,
        )
        lens_sha = sha256_text(lens)
        template_text, hooks, policy = build_dynamic_template(decision["route"], decision["token_limit"])
        template_id = unique_prefix("FABT", ask_sha)
        match_id = unique_prefix("AXMATCH", ask_sha)
        triplet_id = unique_prefix("ROLLTRIP", ask_sha)
        conn.execute(
            """
            INSERT INTO AXIOMATIC_RETRIEVAL_MATCHES (
                match_id, ask_sha256, route, fabric_layer, match_text, status,
                candidate_count, model_meta_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                match_id,
                ask_sha,
                decision["route"],
                fabric_layer,
                retrieval_match.get("text", ""),
                retrieval_match.get("status", "unknown"),
                len(sources) + len(code_sources),
                json.dumps(retrieval_match.get("meta", {}), ensure_ascii=True, sort_keys=True),
            ),
        )
        conn.execute(
            """
            INSERT INTO ROLLING_TRIPLET_RUNS (
                triplet_id, ask_sha256, route, fabric_layer, chooser_lens_text,
                retrieval_match_text, rolling_card_text, status, meta_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                triplet_id,
                ask_sha,
                decision["route"],
                fabric_layer,
                qwen_lens.get("text", ""),
                retrieval_match.get("text", ""),
                rolling_card.get("text", ""),
                rolling_card.get("status", "unknown"),
                json.dumps({
                    "chooser": qwen_lens.get("meta", {}),
                    "retrieval": retrieval_match.get("meta", {}),
                    "rolling": rolling_card.get("meta", {}),
                    "tiny_status": tiny_status,
                }, ensure_ascii=True, sort_keys=True),
            ),
        )
        for role, item in (
            ("retrieval_matcher", retrieval_match),
            ("qwen_chooser", qwen_lens),
            ("qwen_rolling_triplet", rolling_card),
        ):
            meta = item.get("meta", {})
            conn.execute(
                """
                INSERT INTO TINY_MODEL_EVENTS (
                    event_id, ask_sha256, model_role, status, details_json
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    unique_prefix("TINYEVT", ask_sha),
                    ask_sha,
                    role,
                    item.get("status", "unknown"),
                    json.dumps(meta, ensure_ascii=True, sort_keys=True),
                ),
            )
            conn.execute(
                """
                INSERT INTO BENCHMARK_EVENTS (
                    benchmark_id, component, operation, route, duration_ms, status, details_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    unique_prefix("BENCH", ask_sha),
                    "tiny_model_runtime",
                    role,
                    decision["route"],
                    int(meta.get("duration_ms", 0) or 0),
                    item.get("status", "unknown"),
                    json.dumps(meta, ensure_ascii=True, sort_keys=True),
                ),
            )
        conn.execute(
            """
            INSERT INTO FABRIC_TEMPLATE_SNAPSHOTS (
                template_id, route, ask_sha256, template_text, template_sha256, hooks_json, noise_policy_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                template_id,
                decision["route"],
                ask_sha,
                template_text,
                sha256_text(template_text),
                json.dumps(hooks, ensure_ascii=True, sort_keys=True),
                json.dumps(policy, ensure_ascii=True, sort_keys=True),
            ),
        )
        conn.execute(
            """
            INSERT INTO FABRIC_LENSES (
                lens_id, route, ask_sha256, token_limit, lens_text, lens_sha256, sources_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                lens_id,
                decision["route"],
                ask_sha,
                decision["token_limit"],
                lens,
                lens_sha,
                json.dumps({
                    "purpose": purpose,
                    "query_variants": decision["query_variants"],
                    "evidence_sufficiency": sufficiency,
                    "web_snippet_plan": web_plan,
                    "merged_winner_architecture": winner,
                    "tiny_prompt_engineer_card_50_words": tiny_card,
                    "fabric_layer": fabric_layer,
                    "axiomatic_retrieval_match_50_words": retrieval_match,
                    "qwen_chooser_lens_100_words": qwen_lens,
                    "rolling_recursive_triplet_card": rolling_card,
                    "tiny_model_status": tiny_status,
                    "logic_sources": sources,
                    "code_sources": code_sources,
                }, ensure_ascii=True, sort_keys=True),
            ),
        )
        conn.execute(
            """
            INSERT INTO DATA_RETRIEVAL_EVENTS (
                event_id, ask_sha256, ask_preview, route, token_limit, lens_id, result_count, decision_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                ask_sha,
                ask[:240],
                decision["route"],
                decision["token_limit"],
                lens_id,
                len(sources),
                json.dumps(decision, ensure_ascii=True, sort_keys=True),
            ),
        )
        conn.execute(
            """
            INSERT INTO AI_CHOOSER_REVIEWS (
                review_id, ask_sha256, lens_id, template_id, route,
                draft_lens_sha256, reviewed_lens_sha256, review_status, review_json, reviewed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                unique_prefix("AICHOOSER", ask_sha),
                ask_sha,
                lens_id,
                template_id,
                decision["route"],
                lens_sha,
                sha256_text(qwen_lens.get("text", "")),
                qwen_lens.get("status", "reviewed_by_qwen2_5"),
                json.dumps({
                        "purpose": "real_qwen_rewrite_fabric_prompt",
                        "retrieval_epoch": "purpose_db_smollm_qwen_rolling_triplet",
                        "purpose_card_15": purpose["ask_card_15"],
                        "evidence_sufficiency": sufficiency,
                        "merged_winner_architecture": winner,
                        "tiny_prompt_engineer_card_50_words": tiny_card,
                        "fabric_layer": fabric_layer,
                        "axiomatic_retrieval_match": retrieval_match,
                        "qwen_lens": qwen_lens,
                        "rolling_card": rolling_card,
                        "rules": [
                            "preserve route and safety gates",
                            "reduce noise",
                            "prefer project-local successful logic",
                            "make topological instructions clearer",
                            "use purpose -> evidence cards -> web snippet plan -> task directions",
                        ],
                    }, ensure_ascii=True, sort_keys=True),
            ),
        )
        if decision["route"] in {"planning", "build"}:
            webcrawl_request_id = unique_prefix("WCRAWL", ask_sha)
            conn.execute(
                """
                INSERT INTO WEBCRAWL_RESEARCH_REQUESTS (
                    request_id, ask_sha256, route, query_json, noise_policy_json
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    webcrawl_request_id,
                    ask_sha,
                    decision["route"],
                    json.dumps({
                        "tokens": decision["tokens"][:16],
                        "query_variants": decision["query_variants"][:6],
                        "ask_preview": ask[:240],
                        "purpose": purpose["purpose"],
                        "fabric_layer": fabric_layer,
                        "web_snippet_plan": web_plan,
                        "merged_winner_architecture": winner,
                        "tiny_prompt_engineer_card_50_words": tiny_card,
                        "qwen_chooser_lens_100_words": qwen_lens.get("text", ""),
                        "axiomatic_retrieval_match_50_words": retrieval_match.get("text", ""),
                    }, ensure_ascii=True, sort_keys=True),
                    json.dumps(policy, ensure_ascii=True, sort_keys=True),
                ),
            )
            contract = {
                "loop_count": 20 if decision["route"] == "build" else 3,
                "actor_critic": "stop_best",
                "mode": "proposal_only",
                "karoo": "compare three options per advancement",
                "abliterated": "crawl/suggest only",
                "qwen_chooser": "real tiny chooser writes active lens",
                "smollm_retrieval": "real tiny retrieval matcher injects closest 50 words",
                "ministry": "fault-filter and toss failed triplet back",
                "webcrawl_request_id": webcrawl_request_id,
                "template_id": template_id,
                "triplet_id": triplet_id,
                "axiomatic_match_id": match_id,
                "successful_code_sources": [item["sha256"] for item in code_sources[:5]],
            }
            conn.execute(
                """
                INSERT INTO KAROO_EPOCH_REQUESTS (
                    epoch_id, ask_sha256, route, loop_count, actor_critic, contract_json
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    epoch_id,
                    ask_sha,
                    decision["route"],
                    contract["loop_count"],
                    contract["actor_critic"],
                    json.dumps(contract, ensure_ascii=True, sort_keys=True),
                ),
            )
    return {
        "event_id": event_id,
        "lens_id": lens_id,
        "ask_sha256": ask_sha,
        "route": decision["route"],
        "fabric_layer": fabric_layer,
        "token_limit": decision["token_limit"],
        "result_count": len(sources),
        "code_result_count": len(code_sources),
        "template_id": template_id,
        "axiomatic_match_id": match_id,
        "triplet_id": triplet_id,
        "purpose": purpose,
        "evidence_sufficiency": sufficiency,
        "web_snippet_plan": web_plan,
        "merged_winner_architecture": winner,
        "tiny_prompt_engineer_card_50_words": tiny_card,
        "axiomatic_retrieval_match_50_words": retrieval_match,
        "qwen_chooser_lens_100_words": qwen_lens,
        "rolling_recursive_triplet_card": rolling_card,
        "tiny_model_status": tiny_status,
        "lens": lens,
        "lens_sha256": sha256_text(lens),
    }


def main():
    parser = argparse.ArgumentParser(description="VIPER data retrieval agent and Fabric lens crafter.")
    parser.add_argument("ask", nargs="*", help="Ask text. If omitted, stdin is used.")
    parser.add_argument("--json", action="store_true", help="Emit full JSON result.")
    args = parser.parse_args()
    ask = " ".join(args.ask).strip()
    if not ask:
        ask = input().strip()
    result = craft_lens(ask)
    if args.json:
        print(json.dumps(result, ensure_ascii=True, indent=2))
    else:
        print(result["lens"])


if __name__ == "__main__":
    main()
