import sqlite3
import os
import sys
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nmct_code.db")

def get_connection():
    return sqlite3.connect(DB_PATH)

def init_db():
    """Initializes the Never Make Code Twice (NMCT) Database."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Snippets table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS snippets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        name TEXT UNIQUE NOT NULL,
        language TEXT NOT NULL,
        performative TEXT NOT NULL, -- e.g. ask, tell, request, achieve, command
        description TEXT,
        code TEXT NOT NULL,
        fitness_score REAL NOT NULL DEFAULT 1.0,
        hits INTEGER NOT NULL DEFAULT 0,
        lifespan_seconds INTEGER NOT NULL DEFAULT 2592000, -- Default 30 days
        expiry_timestamp TEXT NOT NULL
    )
    """)
    
    # Telemetry and Execution Costs
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS telemetry (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        snippet_id INTEGER,
        timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        execution_time_ms REAL NOT NULL,
        compute_cost REAL NOT NULL, -- Calculated resource cost
        status TEXT NOT NULL, -- success, failure
        FOREIGN KEY(snippet_id) REFERENCES snippets(id) ON DELETE CASCADE
    )
    """)
    
    conn.commit()
    conn.close()
    print(f"NMCT Database initialized at: {DB_PATH}")

def store_snippet(name, language, performative, description, code, fitness_score=1.0, lifespan_days=30):
    """
    Stores a snippet. If the snippet name already exists, updates it.
    Organizes by language and performative.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    now = datetime.utcnow()
    expiry = now + timedelta(days=lifespan_days)
    expiry_str = expiry.strftime("%Y-%m-%d %H:%M:%S")
    lifespan_seconds = lifespan_days * 86400
    
    try:
        cursor.execute("""
        INSERT INTO snippets (name, language, performative, description, code, fitness_score, lifespan_seconds, expiry_timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            language=excluded.language,
            performative=excluded.performative,
            description=excluded.description,
            code=excluded.code,
            fitness_score=excluded.fitness_score,
            lifespan_seconds=excluded.lifespan_seconds,
            expiry_timestamp=excluded.expiry_timestamp,
            timestamp=CURRENT_TIMESTAMP
        """, (name, language.lower(), performative.lower(), description, code.strip(), fitness_score, lifespan_seconds, expiry_str))
        
        conn.commit()
        print(f"Stored snippet '{name}' [{language}/{performative}] (Expires: {expiry_str})")
    except Exception as e:
        print(f"Error storing snippet: {e}", file=sys.stderr)
    finally:
        conn.close()

def lookup_snippet(language, performative, name_query=None):
    """
    Looks up a snippet by language and performative.
    Increments hit count and refreshes lifespan (prevents expiration).
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    sql = "SELECT id, name, code, fitness_score, hits, expiry_timestamp FROM snippets WHERE language = ? AND performative = ?"
    params = [language.lower(), performative.lower()]
    
    if name_query:
        sql += " AND (name LIKE ? OR description LIKE ?)"
        params.extend([f"%{name_query}%", f"%{name_query}%"])
        
    sql += " ORDER BY fitness_score DESC, hits DESC LIMIT 1"
    
    cursor.execute(sql, params)
    row = cursor.fetchone()
    
    if row:
        snippet_id, name, code, fitness_score, hits, expiry_timestamp = row
        new_hits = hits + 1
        
        # Refresh lifespan: push expiry forward from now
        now = datetime.utcnow()
        cursor.execute("SELECT lifespan_seconds FROM snippets WHERE id = ?", (snippet_id,))
        lifespan_seconds = cursor.fetchone()[0]
        new_expiry = now + timedelta(seconds=lifespan_seconds)
        new_expiry_str = new_expiry.strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute("""
        UPDATE snippets 
        SET hits = ?, expiry_timestamp = ?
        WHERE id = ?
        """, (new_hits, new_expiry_str, snippet_id))
        
        conn.commit()
        conn.close()
        
        return {
            "id": snippet_id,
            "name": name,
            "code": code,
            "fitness_score": fitness_score,
            "hits": new_hits,
            "expiry_timestamp": new_expiry_str
        }
    conn.close()
    return None

def log_telemetry(snippet_id, execution_time_ms, compute_cost, status="success"):
    """Logs runtime execution metrics and cost. Nothing runs for free."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO telemetry (snippet_id, execution_time_ms, compute_cost, status)
        VALUES (?, ?, ?, ?)
        """, (snippet_id, execution_time_ms, compute_cost, status))
        conn.commit()
    except Exception as e:
        print(f"Error logging telemetry: {e}", file=sys.stderr)
    finally:
        conn.close()

def garbage_collect():
    """
    Deletes all expired snippets.
    Nothing lives forever.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    
    # Find expired snippets to print reports
    cursor.execute("SELECT name FROM snippets WHERE expiry_timestamp < ?", (now_str,))
    expired = [row[0] for row in cursor.fetchall()]
    
    if expired:
        cursor.execute("DELETE FROM snippets WHERE expiry_timestamp < ?", (now_str,))
        conn.commit()
        print(f"Garbage collection deleted {len(expired)} expired snippet(s): {', '.join(expired)}")
    else:
        print("Garbage collection complete: 0 expired snippets found.")
        
    conn.close()

if __name__ == "__main__":
    init_db()
    # If run directly with arguments, expose a basic CLI interface
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd == "store" and len(sys.argv) >= 7:
            # store <name> <lang> <performative> <desc> <code> [fitness] [lifespan_days]
            name, lang, perf, desc, code = sys.argv[2:7]
            fit = float(sys.argv[7]) if len(sys.argv) > 7 else 1.0
            life = int(sys.argv[8]) if len(sys.argv) > 8 else 30
            store_snippet(name, lang, perf, desc, code, fit, life)
        elif cmd == "lookup" and len(sys.argv) >= 4:
            # lookup <lang> <performative> [name_query]
            lang, perf = sys.argv[2:4]
            q = sys.argv[4] if len(sys.argv) > 4 else None
            res = lookup_snippet(lang, perf, q)
            if res:
                print(f"Found Snippet: {res['name']} (Hits: {res['hits']}, Expiry: {res['expiry_timestamp']})")
                print("-" * 40)
                print(res['code'])
            else:
                print("No matching snippet found.")
        elif cmd == "gc":
            garbage_collect()
