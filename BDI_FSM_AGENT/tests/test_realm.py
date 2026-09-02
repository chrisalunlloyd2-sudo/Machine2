from bdi_fsm.realm import Realm, ChoiceTree


def test_realm_place_into_child_concept():
    r = Realm()
    r.place("aider", "agents", "coding")
    r.place("sophia", "agents", "thinking")
    assert r.lookup("agents", "coding") == ["aider"]
    assert r.lookup("agents", "thinking") == ["sophia"]
    assert r.lookup("places") == []  # not created unless navigated


def test_realm_render_tree():
    r = Realm()
    r.place("aider", "agents", "coding")
    lines = "\n".join(r.render())
    assert "root/" in lines and "agents/" in lines and "coding/" in lines
    assert "* aider" in lines


def test_choice_tree_nesting():
    t = ChoiceTree()
    t.add_node("A", parent="B")  # A is in B -> edge B->A
    assert "A" in t.children("B")
    assert t.nodes["A"]["parent"] == "B"


def test_choice_tree_reward_shifts_best():
    t = ChoiceTree()
    t.add_node("x", parent="root")
    t.add_node("y", parent="root")
    # uniform prior -> deterministic tie-break picks lexicographically smallest
    assert t.best("root") == "x"
    t.reward_edge("root", "y", 5.0)  # incremental feedback
    assert t.best("root") == "y"


def test_choice_tree_traverse_reads_direction():
    t = ChoiceTree()
    t.add_node("greet", hook="echo hello", parent="root")
    t.add_node("ask", hook="echo which repo", parent="greet")
    t.add_node("answer", hook="echo BDI_FSM_AGENT", parent="ask")
    seen = []
    trace = t.traverse("greet", run=lambda h: seen.append(h))
    assert seen == ["echo hello", "echo which repo", "echo BDI_FSM_AGENT"]
    assert trace[0] == "greet"


def test_long_horizon_propagate():
    t = ChoiceTree()
    t.add_node("root")
    t.add_node("a", parent="root")
    t.add_node("b", parent="a")
    t.propagate(["root", "a", "b"], reward=10.0, discount=0.9)
    assert t.nodes["root"]["weights"]["a"] > 1.0
    assert t.nodes["a"]["weights"]["b"] > 1.0
