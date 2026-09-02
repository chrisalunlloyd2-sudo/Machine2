"""GMAIL BRIDGE — live Gmail -> corpus, SELF-SENT emails ONLY.

Chris directive (2026-08-13): ingest SELF-SENT emails only — the sender AND
the recipient must both be the account address, with NO CC/BCC to anyone
else. This is the strict filter; nothing else is ever written to the corpus.

Connects to Gmail IMAP (stdlib imaplib + email), searches for self-sent
candidates, re-verifies STRICTLY at the message level, extracts the text
body, and writes it to the SOV KV store as `self_email.<uid>` — the exact
format corpus_seed.seed_from_self_emails already reads — then seeds the chat
corpus. Credentials come from env (BDI_GMAIL_USER / BDI_GMAIL_APP_PASSWORD),
never hardcoded. Pure stdlib. Deterministic. Zero LLM. ADD-only.
"""
import email
import email.utils
import imaplib
import json
import os
import time
from typing import Any, Dict, List, Optional

SOV_KV = "/root/sov/kv/data.json"
MIN_BODY_CHARS = 20


def _addr_list(header_value: Optional[str]) -> List[str]:
    """Parse an address header into a list of lowercased email addresses."""
    if not header_value:
        return []
    out = []
    for _name, addr in email.utils.getaddresses([header_value]):
        if addr:
            out.append(addr.lower())
    return out


def is_self_sent(msg: Any, account: str) -> bool:
    """STRICT filter: From == [account] AND every recipient (To+Cc+Bcc) is the
    account. Anything else — a different sender, a CC to someone, an empty
    recipient set — is rejected."""
    account = account.lower()
    fr = _addr_list(msg.get("From"))
    to = _addr_list(msg.get("To"))
    cc = _addr_list(msg.get("Cc"))
    bcc = _addr_list(msg.get("Bcc"))
    if fr != [account]:
        return False
    recipients = set(to + cc + bcc)
    if not recipients:
        return False
    return recipients <= {account}


def _extract_text(msg: Any) -> str:
    """Pull the plain-text body out of a (possibly multipart) message."""
    parts: List[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() != "text/plain":
                continue
            disp = (part.get("Content-Disposition") or "").lower()
            if "attachment" in disp:
                continue
            try:
                payload = part.get_payload(decode=True)
                if payload:
                    parts.append(payload.decode(
                        part.get_content_charset() or "utf-8", errors="replace"))
            except Exception:
                continue
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            parts.append(payload.decode(
                msg.get_content_charset() or "utf-8", errors="replace"))
    return "\n".join(p for p in parts if p).strip()


def write_self_emails_kv(kv_path: str, emails: List[Dict[str, Any]]) -> Dict[str, int]:
    """Write self-sent emails into the SOV KV store (ADD-only by uid key)."""
    os.makedirs(os.path.dirname(kv_path) or ".", exist_ok=True)
    data: Dict[str, Any] = {}
    if os.path.exists(kv_path):
        try:
            data = json.load(open(kv_path))
        except Exception:
            data = {}
    if not isinstance(data, dict):
        data = {}
    kv = data.get("kv")
    if not isinstance(kv, dict):
        kv = {}   # fresh dict — never alias `data` itself (avoids circular ref)
    for e in emails:
        kv[f"self_email.{e['uid']}"] = {
            "body": e["body"],
            "subject": e.get("subject", ""),
            "ts": e.get("ts", time.time()),
        }
    data["kv"] = kv
    tmp = kv_path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, kv_path)
    return {"written": len(emails)}


def fetch_self_sent(account: str, app_password: str, limit: int = 20,
                    host: str = "imap.gmail.com", mailbox: str = "INBOX",
                    imap_client: Optional[Any] = None) -> List[Dict[str, Any]]:
    """Connect to Gmail, search self-sent candidates, STRICT-filter, extract.

    `imap_client` is injectable for tests (a fake object with select/search/
    fetch/logout). Returns [{uid, subject, body, ts}] for self-sent only.
    """
    own = imap_client is None
    if own:
        imap_client = imaplib.IMAP4_SSL(host)
        imap_client.login(account, app_password)
    try:
        typ, _ = imap_client.select(mailbox, readonly=True)
        if typ != "OK":
            return []
        query = f'(FROM "{account}" TO "{account}")'
        typ, data = imap_client.search(None, query)
        if typ != "OK" or not data or not data[0]:
            return []
        ids = data[0].split()
        out: List[Dict[str, Any]] = []
        for num in reversed(ids[-limit:]):
            typ, msg_data = imap_client.fetch(num, "(RFC822)")
            if typ != "OK" or not msg_data:
                continue
            first = msg_data[0]
            raw = first[1] if isinstance(first, tuple) else first
            try:
                msg = email.message_from_bytes(raw)
            except Exception:
                continue
            if not is_self_sent(msg, account):
                continue
            body = _extract_text(msg)
            if len(body) < MIN_BODY_CHARS:
                continue
            uid = num.decode() if isinstance(num, bytes) else str(num)
            out.append({"uid": uid, "subject": msg.get("Subject") or "",
                        "body": body, "ts": time.time()})
        return out
    finally:
        if own:
            try:
                imap_client.logout()
            except Exception:
                pass


def bridge(account: str, app_password: str, corpus_path: str,
           kv_path: str = SOV_KV, limit: int = 20,
           imap_client: Optional[Any] = None,
           dry_run: bool = False) -> Dict[str, Any]:
    """Live Gmail -> KV -> corpus, self-sent only. Returns a report."""
    emails = fetch_self_sent(account, app_password, limit=limit,
                             imap_client=imap_client)
    if emails and not dry_run:
        write_self_emails_kv(kv_path, emails)
    from .corpus_seed import seed
    report = seed(corpus_path, kv_path=kv_path, dry_run=dry_run)
    report["self_sent_fetched"] = len(emails)
    return report

# LOCATIONS - this file lives in more than one place
#
#   live:  C:\Viper\projects\BDI_FSM_AGENT
#          -> C:\Users\viper\gan-otg-db\BDI_FSM_AGENT
#   mirror: J:\ViperVault\code\projects\BDI_FSM_AGENT
#   mirror: C:\Users\viper\gan-otg-db\BDI_FSM_AGENT
#
#   live detail (freshness, git coverage): docs\LOCATIONS.md
#   regenerate: python location_stamp.py apply
# end LOCATIONS
