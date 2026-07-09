#!/usr/bin/env python3
"""
VIPER Daily Status Emailer
===========================
Sends a daily 7am status email to chrisa@gmail.com
covering: port health, block mining stats, service status, DB sizes.

Set your Gmail App Password with:
  setx VIPER_EMAIL_PASS "your-app-password"

Then run once:
  python viper_daily_email.py --install-task
  
This installs a Windows Scheduled Task to run daily at 7:00 AM.
Or just run it directly to send immediately:
  python viper_daily_email.py --send-now
"""
import os
import sys
import json
import socket
import sqlite3
import datetime
import argparse
import subprocess
from pathlib import Path

# ─── Config ───────────────────────────────────────────────────────
FROM_EMAIL  = "chrisa@gmail.com"
TO_EMAIL    = "chrisa@gmail.com"
SMTP_HOST   = "smtp.gmail.com"
SMTP_PORT   = 587
APP_PASS_ENV = "VIPER_EMAIL_PASS"   # set with: setx VIPER_EMAIL_PASS "xxxx xxxx xxxx xxxx"

VIPER    = Path(r"C:\Users\viper\VIPER_JAVA_RISC")
GANOTG   = Path(r"C:\Users\viper\gan-otg-db")
CODE_DB  = VIPER / "java_notes_suite" / "data" / "code.db"
LOG_FILE = VIPER / "logs" / "daily_email.log"


PORTS = {
    1234:  "LM Studio",
    8765:  "SLM Proxy",
    11435: "House Engine",
    18181: "Java SDK",
    18282: "HUD",
    18283: "OTG Bridge A",
    18284: "OTG Bridge B",
}


def port_alive(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            return True
    except OSError:
        return False


def get_db_stats() -> dict:
    stats = {}
    if CODE_DB.exists():
        try:
            conn = sqlite3.connect(str(CODE_DB), timeout=5)
            count = conn.execute("SELECT COUNT(*) FROM code_artifacts").fetchone()[0]
            langs = conn.execute(
                "SELECT language, COUNT(*) FROM code_artifacts GROUP BY language ORDER BY COUNT(*) DESC LIMIT 5"
            ).fetchall()
            conn.close()
            stats["code_blocks"] = count
            stats["top_languages"] = {r[0]: r[1] for r in langs}
        except Exception:
            stats["code_blocks"] = "error"

    bridge_db = VIPER / "java_notes_suite" / "data" / "otg_bridge.db"
    if bridge_db.exists():
        try:
            conn = sqlite3.connect(str(bridge_db), timeout=5)
            stats["bridge_messages"] = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
            conn.close()
        except Exception:
            pass

    return stats


def get_watchdog_tail() -> str:
    wlog = VIPER / "logs" / "watchdog.log"
    if wlog.exists():
        lines = wlog.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(lines[-10:])
    return "(watchdog log not found)"


def build_html_email(ts: str, port_status: dict, db_stats: dict, watchdog_tail: str) -> str:
    rows_ports = ""
    for port, name in PORTS.items():
        alive = port_status.get(port, False)
        color = "#22c55e" if alive else "#ef4444"
        icon = "✅" if alive else "❌"
        rows_ports += f"<tr><td style='padding:4px 12px;'>{icon} {name}</td><td style='color:{color};font-weight:bold;'>:{port} {'LIVE' if alive else 'DOWN'}</td></tr>\n"

    lang_rows = ""
    for lang, count in db_stats.get("top_languages", {}).items():
        lang_rows += f"<tr><td style='padding:2px 12px;'>{lang}</td><td>{count}</td></tr>"

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><style>
body{{font-family:monospace;background:#0f0f0f;color:#e5e7eb;padding:24px;}}
h1{{color:#a78bfa;font-size:1.4em;}}
h2{{color:#60a5fa;font-size:1.1em;border-bottom:1px solid #374151;padding-bottom:4px;}}
table{{border-collapse:collapse;width:100%;}}
td{{font-size:0.9em;}}
pre{{background:#1f2937;padding:12px;border-radius:6px;font-size:0.8em;overflow-x:auto;}}
.ok{{color:#22c55e;}} .fail{{color:#ef4444;}}
</style></head>
<body>
<h1>🧠 VIPER Machine 2 — Daily Status Report</h1>
<p style="color:#9ca3af;">{ts}</p>

<h2>🔌 Service Ports</h2>
<table>{rows_ports}</table>

<h2>📦 Database Stats</h2>
<table>
<tr><td style='padding:4px 12px;'>Code Blocks Mined</td><td><b>{db_stats.get('code_blocks', 0)}</b></td></tr>
<tr><td style='padding:4px 12px;'>Bridge Messages</td><td>{db_stats.get('bridge_messages', 0)}</td></tr>
</table>
<br>
<b>Top Languages:</b>
<table>{lang_rows}</table>

<h2>🐕 Watchdog Log (last 10 lines)</h2>
<pre>{watchdog_tail}</pre>

<h2>🏗️ Architecture Reminder</h2>
<pre>
Machine 1 (Aegis/Picoclaw)  &lt;──&gt;  Machine 2 (VIPER JAVA RISC)
         │                                    │
    Inference                         Karoo Code Miner
    Aegis Prompts                     OTG Dual Bridge (18283/18284)
    Research Tasks                    code.db (syntax trees)
                                      HUD :18282
                                      SLM Proxy :8765
</pre>

<p style="color:#6b7280;font-size:0.8em;">— VIPER Auto-Reporter | Machine 2 | {ts}</p>
</body>
</html>"""


def send_email(html_body: str, subject: str) -> bool:
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    app_pass = os.environ.get(APP_PASS_ENV, "")
    if not app_pass:
        print(f"ERROR: Set {APP_PASS_ENV} env var with your Gmail App Password")
        print(f"  Run: setx {APP_PASS_ENV} \"your app password\"")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = FROM_EMAIL
    msg["To"]      = TO_EMAIL
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.login(FROM_EMAIL, app_pass)
            server.sendmail(FROM_EMAIL, [TO_EMAIL], msg.as_string())
        return True
    except Exception as e:
        print(f"SMTP error: {e}")
        return False


def install_windows_task() -> None:
    """Register a Windows Scheduled Task to run this script daily at 7:00 AM."""
    py  = sys.executable
    script = str(Path(__file__).resolve())
    task_name = "VIPER_Daily_Status"

    cmd = [
        "schtasks", "/create", "/f",
        "/tn", task_name,
        "/tr", f'"{py}" "{script}" --send-now',
        "/sc", "DAILY",
        "/st", "07:00",
        "/ru", os.environ.get("USERNAME", "viper"),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"✅ Task '{task_name}' scheduled daily at 07:00")
        print(f"   To disable: schtasks /delete /tn {task_name} /f")
    else:
        print(f"❌ Failed to create task: {result.stderr}")
        print("   Try running this script as Administrator.")


def run_and_send() -> None:
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    subject = f"VIPER Machine 2 Status — {datetime.date.today()}"

    port_status = {p: port_alive(p) for p in PORTS}
    db_stats = get_db_stats()
    watchdog_tail = get_watchdog_tail()

    html = build_html_email(ts, port_status, db_stats, watchdog_tail)

    ok = send_email(html, subject)
    status = "SENT" if ok else "FAILED"
    log_line = f"[{ts}] Email {status} to {TO_EMAIL}\n"

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_line)
    print(log_line.strip())


def main() -> None:
    parser = argparse.ArgumentParser(description="VIPER Daily Status Emailer")
    parser.add_argument("--send-now",      action="store_true", help="Send status email immediately")
    parser.add_argument("--install-task",  action="store_true", help="Install Windows Scheduled Task for 7am daily")
    parser.add_argument("--set-password",  action="store_true", help="Show instructions for setting app password")
    args = parser.parse_args()

    if args.set_password:
        print("To set your Gmail App Password:")
        print("  1. Go to https://myaccount.google.com/apppasswords")
        print("  2. Create an App Password for 'Mail'")
        print(f"  3. Run: setx {APP_PASS_ENV} \"xxxx xxxx xxxx xxxx\"")
        print("  4. Restart your terminal or reboot")
        return

    if args.install_task:
        install_windows_task()
        return

    # Default or --send-now
    run_and_send()


if __name__ == "__main__":
    main()
