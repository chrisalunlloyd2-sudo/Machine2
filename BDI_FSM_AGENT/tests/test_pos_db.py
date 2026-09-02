from bdi_fsm.pos_db import tag, PosDB


def test_tag_obvious():
    assert tag("quickly") == "adverb"
    assert tag("database") == "noun"       # -e? no; 'database' -> default noun
    assert tag("modifier") == "noun"       # -er
    assert tag("modify") == "verb"         # -ify
    assert tag("symbolic") == "adjective"  # -ic
    assert tag("training") == "noun"       # -ing gerund


def test_ingest_logs_proximity():
    db = PosDB()
    r = db.ingest("nouns verbs go close together adjectives almost clear")
    assert r["relations"] > 0
    assert len(db.relations) > 0


def test_directional_verb_modifies_noun():
    db = PosDB()
    db.ingest("verbs modify nouns")
    # 'modify' (verb) -> 'nouns' (noun) direction logged
    assert ("modify", "nouns") in db.relations
    assert "verb->noun" in db.typed[("modify", "nouns")]


def test_partitioned_databases():
    db = PosDB()
    db.ingest("quickly modify the symbolic databases")
    assert "modify" in db.verbs or "databases" in db.nouns
    assert "symbolic" in db.adjectives


def test_proximity_weight_decreases():
    db = PosDB()
    db.ingest("apple banana cherry date elder fig", window=6)
    near = db.relations[("apple", "banana")]
    far = db.relations[("apple", "fig")]
    assert near > far  # closer = stronger
