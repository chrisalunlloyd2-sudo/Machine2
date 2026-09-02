"""Regression: _gather_corpus_texts must USE the corpus, not silently fall
back to the journal. (Bug: `json` was never imported at module level, so
`json.loads` raised NameError on the first corpus line, swallowed by the
bare `except: pass`, and the rich corpus was dropped in favour of 9 journal
entries.)"""
import json
import os
import tempfile

from bdi_fsm.agent import BDIFSMAgent


def test_gather_corpus_uses_corpus_not_journal():
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, "corpus"), exist_ok=True)
    corpus_path = os.path.join(d, "corpus", "chat_corpus.jsonl")
    with open(corpus_path, "w") as f:
        for i in range(50):
            f.write(json.dumps({"text": f"distinctive corpus sentence number {i}",
                                "src": "test"}) + "\n")
    a = BDIFSMAgent(state_dir=d)
    texts = a._gather_corpus_texts()
    assert len(texts) >= 50, f"expected >=50 corpus texts, got {len(texts)}"
    assert any("distinctive corpus sentence" in t for t in texts), \
        "corpus text missing — fell back to journal/_FALLBACK_CORPUS"


def test_chat_long_uses_min_words_not_legacy_one():
    """chat_long must thread min_words (default 40) into generate(); before the
    fix it was ignored and chats died at the first period (4-5 words)."""
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, "corpus"), exist_ok=True)
    corpus_path = os.path.join(d, "corpus", "chat_corpus.jsonl")
    prose = [
        "the cat sat on the mat and watched the birds .",
        "a dog ran through the park chasing the wind .",
        "birds fly high over the quiet blue lake .",
        "the sun sets slowly behind the tall green hills .",
        "we walk down the long winding road together .",
        "she reads an old book beside the warm fire .",
        "rain falls gently on the old wooden roof .",
        "he climbs the steep rocky mountain every morning .",
        "the river flows quietly into the wide sea .",
        "they sing old songs around the glowing camp fire .",
        "morning light fills the small quiet room .",
        "the old tree stands alone in the open field .",
        "we bake fresh bread in the warm kitchen .",
        "the moon glows softly over the sleeping hills .",
        "children play near the cool clear water .",
        "the wind moves softly through the autumn leaves .",
        "stars shine bright in the clear night sky .",
        "the train rolls slowly past the old station .",
        "coffee warms her cold hands on the grey morning .",
        "the garden grows wild and green every year .",
    ]
    with open(corpus_path, "w") as f:
        for t in prose:
            f.write(json.dumps({"text": t, "src": "test"}) + "\n")
    a = BDIFSMAgent(state_dir=d)
    short = a.chat_long(seed="the cat", max_words=200, min_words=1)
    long_ = a.chat_long(seed="the cat", max_words=200, min_words=40)
    # a full-length request must produce more words than the legacy stop-at-period
    assert long_["words"] > short["words"], (short, long_)
    assert long_["words"] >= 20, long_
