from bdi_fsm.dom import Node, TreeBuilder, render, open_tags, SCHEMA


def test_node_children():
    n = Node("div")
    n.append(Node("p", text="hi"))
    assert len(n.children) == 1 and n.children[0].text == "hi"


def test_schema_enforced():
    b = TreeBuilder()
    # body may contain table; table may NOT contain p
    t = b.enter("table")
    assert b.enter("p") is None  # illegal child -> grammar vetoes
    assert b.enter("thead") is not None  # legal


def test_table_tree_structure():
    b = TreeBuilder()
    b.enter("table")
    b.enter("thead")
    b.enter("tr")
    b.leaf("th", text="Header")
    b.exit(); b.exit(); b.exit()
    assert open_tags(b.html) == ["html", "body", "table", "thead", "tr", "th"]


def test_list_tree():
    b = TreeBuilder()
    b.enter("ul")
    b.leaf("li", text="A")
    b.leaf("li", text="B")
    b.exit()
    assert render(b.html) == "<html><body><ul><li>A</li><li>B</li></ul></body></html>"


def test_render_void():
    b = TreeBuilder()
    b.leaf("img", {"src": "x.png"})
    assert render(b.html) == '<html><body><img src="x.png"></body></html>'


def test_open_tags_document_order():
    b = TreeBuilder()
    b.leaf("h1", text="T")
    b.enter("nav")
    b.leaf("a", {"href": "#"}, text="H")
    b.exit()
    assert open_tags(b.html) == ["html", "body", "h1", "nav", "a"]
