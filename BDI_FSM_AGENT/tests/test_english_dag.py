"""English fluency DAG tests — performatives, variable stringing, Nash gate."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bdi_fsm.english_dag import (DAGNode, FluencyGate, agree_verb, article,
                                 pluralize, render_dag, string_variable)


def test_article():
    assert article("apple") == "an"
    assert article("banana") == "a"
    assert article("") == ""


def test_pluralize():
    assert pluralize("cat", 1) == "cat"
    assert pluralize("cat", 2) == "cats"
    assert pluralize("box", 2) == "boxes"
    assert pluralize("party", 2) == "parties"


def test_agree_verb():
    assert agree_verb("it", "be") == "is"
    assert agree_verb("they", "be") == "be"
    assert agree_verb("he", "have") == "has"
    assert agree_verb("we", "have") == "have"
    assert agree_verb("it", "run") == "runs"


def test_string_variable():
    assert string_variable("max_retries", "5") == "max_retries is set to 5."
    assert string_variable("port", "8080", "keyvalue") == "port is 8080."
    assert string_variable("handler", "x", "function") == "handler is defined as a function."


def test_dag_node_render():
    tell = DAGNode("tell", "status", slots={"subject": "system",
                                             "predicate": "be",
                                             "object": "ready"})
    assert tell.render({"subject": "system", "predicate": "be", "object": "ready"}) == "system is ready."
    ach = DAGNode("achieve", "run")
    assert ach.render({"verb": "run", "object": "the tests"}) == "I will run the tests."
    ask = DAGNode("ask", "q")
    assert ask.render({"wh": "what", "object": "this"}) == "what is this?"


def test_render_dag_walks_children():
    root = DAGNode("tell", "r", slots={"subject": "it", "predicate": "be", "object": "done"})
    root.add(DAGNode("achieve", "next", slots={"verb": "commit", "object": "the code"}))
    out = render_dag(root)   # each node uses its OWN bound slots
    assert out == "it is done. I will commit the code."


def test_fluency_gate_threshold():
    g = FluencyGate(c_miss=10, c_false=1)
    assert abs(g.theta_dban - 10.0) < 1e-9   # 10 * log10(10)


def test_fluency_gate_orders_fluent_above_garbage():
    g = FluencyGate()
    good, _ = g.score("the system is ready.")
    bad, _ = g.score("asdfgh qwerty")
    assert good > bad


def test_fluency_gate_fires_on_very_fluent():
    # lower the bar so a rich sentence clears it (c_miss/c_false symmetric -> 0)
    g = FluencyGate(c_miss=1, c_false=1)      # theta* = 0 dBan
    dban, fired = g.score("the system is ready to run the tests.")
    assert fired is True
    assert dban > 0


def test_emit_best_returns_fluent_when_above_theta():
    g = FluencyGate(c_miss=1, c_false=1)          # theta* = 0 dBan
    text, dban, fallback = g.emit_best(["asdf qwerty", "the system is ready."], "okay.")
    assert text == "the system is ready."
    assert fallback is False
    assert dban > 0


def test_emit_best_short_circuits_when_all_below_theta():
    g = FluencyGate(c_miss=100, c_false=1)        # theta* = 20 dBan (high bar)
    # even fluent sentences won't clear 20 dBan with the current feature set
    text, dban, fallback = g.emit_best(["the system is ready."], "okay.")
    assert text == "okay."
    assert fallback is True
