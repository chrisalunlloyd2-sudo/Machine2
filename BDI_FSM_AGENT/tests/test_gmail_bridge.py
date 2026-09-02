"""Gmail bridge tests — self-sent-only filter, KV write, end-to-end (no network)."""
import json
import os
import tempfile
from email.message import EmailMessage

from bdi_fsm.gmail_bridge import (bridge, is_self_sent, _extract_text,
                                  write_self_emails_kv)

ACCT = "chrisalunlloyd2@gmail.com"


def _msg(from_, to_, cc=None, body="hello world this is a self email body"):
    m = EmailMessage()
    m["From"] = from_
    m["To"] = to_
    if cc:
        m["Cc"] = cc
    m["Subject"] = "test"
    m.set_content(body)
    return m


class FakeIMAP:
    def __init__(self, messages):
        self.messages = messages

    def select(self, mailbox, readonly=True):
        return ("OK", [b"1"])

    def search(self, *args):
        ids = " ".join(str(i + 1) for i in range(len(self.messages)))
        return ("OK", [ids.encode()])

    def fetch(self, num, spec):
        i = int(num) - 1
        return ("OK", [(b"%d (RFC822)" % int(num), self.messages[i].as_bytes())])

    def logout(self):
        return ("OK", [])


def test_is_self_sent_strict():
    assert is_self_sent(_msg(ACCT, ACCT), ACCT) is True
    assert is_self_sent(_msg("someone@else.com", ACCT), ACCT) is False
    assert is_self_sent(_msg(ACCT, ACCT, cc="other@else.com"), ACCT) is False
    assert is_self_sent(_msg(ACCT, None), ACCT) is False          # no recipient


def test_extract_text_plain_and_multipart():
    plain = _msg(ACCT, ACCT, body="plain text body here")
    assert "plain text body here" in _extract_text(plain)
    # multipart: a text/plain part survives, an attachment is dropped
    m = EmailMessage()
    m["From"] = ACCT
    m["To"] = ACCT
    m.set_content("real body content here")
    m.add_attachment("attachment bytes", filename="x.bin")
    txt = _extract_text(m)
    assert "real body content here" in txt


def test_write_self_emails_kv_format():
    d = tempfile.mkdtemp()
    kv = os.path.join(d, "kv.json")
    write_self_emails_kv(kv, [{"uid": "7", "body": "hello world this is a self email body",
                               "subject": "s"}])
    data = json.load(open(kv))
    assert "self_email.7" in data["kv"]
    assert data["kv"]["self_email.7"]["body"].startswith("hello world")


def test_bridge_filters_non_self_sent_end_to_end():
    d = tempfile.mkdtemp()
    corpus = os.path.join(d, "corpus", "chat_corpus.jsonl")
    kv = os.path.join(d, "kv.json")
    imap = FakeIMAP([
        _msg(ACCT, ACCT, body="this is my own self note to the sovereign memory"),
        _msg("someone@else.com", ACCT),                    # other sender -> dropped
        _msg(ACCT, ACCT, cc="other@else.com"),             # cc other -> dropped
    ])
    r = bridge(ACCT, "dummy-pass", corpus, kv_path=kv, imap_client=imap)
    assert r["self_sent_fetched"] == 1       # strict filter kept exactly one
    data = json.load(open(kv))
    assert len(data["kv"]) == 1
    # the corpus gained a self-email line via the seed
    assert os.path.exists(corpus)
    corpus_text = open(corpus).read()
    assert "sovereign memory" in corpus_text


def test_bridge_dry_run_writes_nothing():
    d = tempfile.mkdtemp()
    corpus = os.path.join(d, "corpus", "chat_corpus.jsonl")
    kv = os.path.join(d, "kv.json")
    imap = FakeIMAP([_msg(ACCT, ACCT, body="self note for the sovereign memory stream")])
    r = bridge(ACCT, "dummy-pass", corpus, kv_path=kv, imap_client=imap, dry_run=True)
    assert r["self_sent_fetched"] == 1        # fetched, but...
    assert not os.path.exists(kv)             # ...no KV write
    assert not os.path.exists(corpus)         # ...no corpus write
