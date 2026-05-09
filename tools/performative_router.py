import argparse
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


HOME = Path(r"C:\Users\viper")
DB_PATH = HOME / "gemini_bridge.db"

FIPA_PERFORMATIVES = {
    "accept-proposal",
    "agree",
    "cancel",
    "cfp",
    "confirm",
    "disconfirm",
    "failure",
    "inform",
    "inform-if",
    "inform-ref",
    "not-understood",
    "propagate",
    "propose",
    "proxy",
    "query-if",
    "query-ref",
    "refuse",
    "reject-proposal",
    "request",
    "request-when",
    "request-whenever",
    "subscribe",
}

KQML_PERFORMATIVES = {
    "ask-one",
    "ask-all",
    "ask-if",
    "tell",
    "achieve",
    "advertise",
    "broker-one",
    "broker-all",
    "deny",
    "delete-one",
    "delete-all",
    "eos",
    "error",
    "evaluate",
    "forward",
    "generator",
    "insert",
    "monitor",
    "next",
    "ready",
    "recommend-one",
    "recommend-all",
    "reply",
    "rest",
    "sorry",
    "standby",
    "stream-about",
    "subscribe",
    "unadvertise",
    "untell",
}

ACTION_VERBS = {
    "run",
    "spin",
    "spin up",
    "start",
    "stop",
    "restart",
    "open",
    "create",
    "write",
    "edit",
    "patch",
    "fix",
    "install",
    "deploy",
    "sync",
    "upload",
    "download",
    "ship",
    "queue",
    "hash",
    "scan",
    "optimize",
    "compare",
    "execute",
    "call",
    "ping",
    "check",
    "wire",
    "hook",
    "stage",
    "fork",
    "backup",
    "checkpoint",
    "benchmark",
    "crawl",
    "upgrade",
    "download",
    "install",
}

TALK_MARKERS = {
    "hi",
    "hello",
    "lol",
    "thanks",
    "thank",
    "what do you think",
    "i think",
    "i feel",
    "explain",
    "tell me",
    "do you",
    "could we",
}


def connect_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def migrate():
    with connect_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS PERFORMATIVE_ROUTE_LOG (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message TEXT NOT NULL,
                route TEXT NOT NULL,
                performatives_json TEXT NOT NULL,
                confidence REAL NOT NULL,
                decision_json TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_performative_route_created
            ON PERFORMATIVE_ROUTE_LOG(created_at);
            """
        )


def extract_parenthesized_performatives(text):
    found = []
    for match in re.finditer(r"\(([A-Za-z][A-Za-z0-9_-]*)\b", text):
        token = match.group(1).lower()
        if token in FIPA_PERFORMATIVES or token in KQML_PERFORMATIVES:
            found.append(token)
    return found


def classify(message):
    text = message.strip()
    lower = text.lower()
    performatives = extract_parenthesized_performatives(text)
    explicit_acl = bool(performatives) or ":sender" in lower or ":content" in lower
    action_hits = sorted({word for word in ACTION_VERBS if re.search(rf"\b{re.escape(word)}\b", lower)})
    phrase_hits = sorted({
        phrase for phrase in (
            "spin up",
            "upgrade epoch",
            "open notes",
            "send all logs",
            "copy paste",
            "copy and paste",
            "push to github",
            "upload to github",
            "start hashing",
            "ship block",
        )
        if phrase in lower
    })
    action_hits = sorted(set(action_hits + phrase_hits))
    talk_hits = sorted({marker for marker in TALK_MARKERS if marker in lower})

    performative_score = 0.0
    if explicit_acl:
        performative_score += 0.75
    if action_hits:
        performative_score += min(0.35, 0.08 * len(action_hits))
    if phrase_hits:
        performative_score += min(0.36, 0.22 * len(phrase_hits))
    if action_hits and ("?" in text or "can you" in lower or "could you" in lower):
        performative_score += 0.3
    if "approval" in lower or "tool" in lower or "code" in lower:
        performative_score += 0.12

    talk_score = 0.0
    if talk_hits:
        talk_score += min(0.45, 0.12 * len(talk_hits))
    if "?" in text:
        talk_score += 0.2
    if len(text.split()) > 8 and not explicit_acl:
        talk_score += 0.18

    performative_score = min(1.0, performative_score)
    talk_score = min(1.0, talk_score)

    if performative_score >= 0.42 and talk_score >= 0.25:
        route = "both"
    elif performative_score >= 0.42:
        route = "performative"
    else:
        route = "chat"

    confidence = round(max(performative_score, talk_score, 0.35), 3)
    return {
        "route": route,
        "confidence": confidence,
        "performatives": performatives,
        "action_hits": action_hits,
        "talk_hits": talk_hits,
        "routing_contract": {
            "chat": "send to rolling recursive chat response",
            "performative": "send to Karoo/Codex approval-gated tool/code planner",
            "both": "split: execute performative intent only after approval, answer talk portion normally",
        },
    }


def classify_and_log(message):
    migrate()
    decision = classify(message)
    with connect_db() as conn:
        conn.execute(
            """
            INSERT INTO PERFORMATIVE_ROUTE_LOG (
                message, route, performatives_json, confidence, decision_json
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                message,
                decision["route"],
                json.dumps(decision["performatives"]),
                decision["confidence"],
                json.dumps(decision, sort_keys=True),
            ),
        )
    return decision


def main():
    parser = argparse.ArgumentParser(description="FIPA/KQML-inspired chat vs performative router.")
    parser.add_argument("message", nargs="*", help="Message to classify")
    parser.add_argument("--migrate", action="store_true")
    args = parser.parse_args()
    if args.migrate:
        migrate()
        print("PERFORMATIVE_ROUTE_TABLE_READY")
        return
    message = " ".join(args.message).strip()
    if not message:
        raise SystemExit("message required")
    print(json.dumps(classify_and_log(message), indent=2))


if __name__ == "__main__":
    main()
