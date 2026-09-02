"""World model (sense-of-other entity DAGs) tests — temporal identity, prune-as-learn, scrub."""
import tempfile

from bdi_fsm.world_model import WorldModel, entity_id, scrub


def test_entity_id_stable_and_distinct():
    a = entity_id("server", "localhost:8765")
    b = entity_id("server", "localhost:8765")
    c = entity_id("server", "localhost:9000")
    assert a == b
    assert a != c


def test_observe_merges_across_days():
    """Same entity today and tomorrow = ONE DAG, not two."""
    w = WorldModel()
    w.observe("server", "localhost:8765", {"health": "up", "port": "8765"}, ts=1000)
    w.observe("server", "localhost:8765", {"health": "down", "latency": "400ms"}, ts=100000)
    assert w.stats()["entities"] == 1
    dag = w.entity("server", "localhost:8765")
    assert set(dag.nodes) == {"health", "port", "latency"}


def test_history_captures_change():
    w = WorldModel()
    w.observe("server", "s", {"health": "up"}, ts=1000)
    w.observe("server", "s", {"health": "down"}, ts=2000)
    dag = w.entity("server", "s")
    assert dag.nodes["health"]["value"] == "down"
    assert dag.nodes["health"]["history"] == [("up", 1000)]


def test_changed_since_is_different_days_answer():
    w = WorldModel()
    w.observe("server", "s", {"health": "up"}, ts=1000)
    w.observe("server", "s", {"health": "down", "latency": "5ms"}, ts=5000)
    changed = w.entity("server", "s").changed_since(5000)
    assert set(changed) == {"health", "latency"}


def test_prune_exactly_as_learned():
    """Steady-state: over the cap, prune returns to cap (learn K -> evict K)."""
    w = WorldModel(max_nodes=5)
    facts = {f"f{i}": i for i in range(10)}
    w.observe("thing", "x", facts)
    assert w.entity("thing", "x").max_nodes == 5
    assert len(w.entity("thing", "x").nodes) == 5
    # learn 3 more -> still 5 (pruned exactly as much as learned)
    w.observe("thing", "x", {"g0": 0, "g1": 1, "g2": 2})
    assert len(w.entity("thing", "x").nodes) == 5


def test_prune_evicts_lowest_utility():
    w = WorldModel(max_nodes=3)
    w.observe("t", "x", {"a": 1, "b": 1, "c": 1}, ts=1000)
    # re-observe a and b (bump utility), leaving c as lowest
    w.observe("t", "x", {"a": 1, "b": 1}, ts=2000)
    # add d -> over cap, c (lowest utility) evicted
    w.observe("t", "x", {"d": 1}, ts=3000)
    nodes = w.entity("t", "x").nodes
    assert "c" not in nodes
    assert set(nodes) == {"a", "b", "d"}


def test_scrub_redacts_pii_keeps_infra():
    s = scrub("mail chrisalunlloyd2@gmail.com token github_pat_ABC123 key sk-xyz")
    assert "chrisalunlloyd2@gmail.com" not in s
    assert "github_pat_" not in s
    assert "<email>" in s and "<github_token>" in s and "<api_key>" in s
    # infrastructure identifiers are NOT scrubbed (they are the point)
    assert scrub("server localhost:8765") == "server localhost:8765"


def test_render_scrubs_values():
    w = WorldModel()
    w.observe("node", "n", {"owner": "chrisalunlloyd2@gmail.com", "port": "80"})
    r = w.render("node", "n", scrub_pii=True)
    assert "chrisalunlloyd2@gmail.com" not in r["nodes"]["owner"]["value"]


def test_save_load_roundtrip():
    d = tempfile.mkdtemp()
    p = d + "/wm.json"
    w = WorldModel(state_path=p)
    w.observe("server", "s", {"health": "up"})
    w.save()
    w2 = WorldModel(state_path=p)
    assert w2.stats()["entities"] == 1
    assert w2.entity("server", "s").nodes["health"]["value"] == "up"
