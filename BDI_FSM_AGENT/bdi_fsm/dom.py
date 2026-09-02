"""dom.py — a real DOM-ish tree + constraints grammar + stack builder + renderer.

Chris 2026-08-15: "everything looks nested but behaves flat. Let's make it
actually structural." Templates become node TYPES, not output macros. A
constraints grammar (SCHEMA) encodes allowed children (table->thead/tbody/tr,
tr->th/td, ul->li); a stack keeps parent context so hierarchy is guaranteed;
a separate renderer walks the tree and emits HTML. Deterministic, zero-LLM.

The FSM builds a TREE; the renderer is a separate pass. That is what breaks the
"atomic template" problem — templates become node types, not output macros.
"""

VOID_ELEMENTS = {"area", "base", "br", "col", "embed", "hr", "img", "input",
                 "link", "meta", "param", "source", "track", "wbr"}

# constraints grammar: tag -> allowed child tags (the "grammar, not templates")
SCHEMA = {
    "html": {"body"},
    "body": {"form", "nav", "table", "ul", "ol", "h1", "h2", "p", "img", "a",
             "button", "input", "textarea", "header", "footer"},
    "table": {"thead", "tbody", "tr"},
    "thead": {"tr"},
    "tbody": {"tr"},
    "tr": {"th", "td"},
    "ul": {"li"},
    "ol": {"li"},
    "form": {"input", "textarea", "button"},
    "nav": {"a", "ul"},
    "header": {"h1", "p"},
    "footer": {"p"},
}


class Node:
    """A DOM-ish node: tag, attributes, children, optional role and text."""
    __slots__ = ("tag", "attrs", "children", "role", "text")

    def __init__(self, tag, attrs=None, role=None, text=None):
        self.tag = tag
        self.attrs = dict(attrs or {})
        self.children = []
        self.role = role
        self.text = text

    def append(self, child):
        self.children.append(child)
        return child


class TreeBuilder:
    """Stack-based builder. enter() pushes, exit() pops; SCHEMA is enforced.

    The stack IS the parent context: enter(table) pushes table so the next
    enter(tr)/leaf(td) is structurally guaranteed to be a child of table.
    """

    def __init__(self):
        self.html = Node("html")
        body = Node("body")
        self.html.append(body)
        self._stack = [self.html, body]

    @property
    def current(self):
        return self._stack[-1]

    def can_add(self, tag):
        return tag in SCHEMA.get(self.current.tag, set())

    def enter(self, tag, attrs=None, role=None):
        """Push a container node. Returns None (and adds nothing) if the tag
        is not a legal child of the current parent — the grammar vetoes."""
        if not self.can_add(tag):
            return None
        node = Node(tag, attrs, role)
        self.current.append(node)
        self._stack.append(node)
        return node

    def leaf(self, tag, attrs=None, role=None, text=None):
        """Add a leaf (or void) node as a child of the current parent."""
        if not self.can_add(tag):
            return None
        node = Node(tag, attrs, role, text)
        self.current.append(node)
        return node

    def exit(self):
        """Pop back to the parent (never above body)."""
        if len(self._stack) > 2:
            self._stack.pop()
        return self.current


def _render_attrs(attrs):
    if not attrs:
        return ""
    return "".join(f' {k}="{v}"' for k, v in attrs.items())


def render(node):
    """Walk the tree and emit HTML. Void elements self-close; text is inline."""
    if node.tag in VOID_ELEMENTS:
        return f"<{node.tag}{_render_attrs(node.attrs)}>"
    inner = (node.text or "") + "".join(render(c) for c in node.children)
    return f"<{node.tag}{_render_attrs(node.attrs)}>{inner}</{node.tag}>"


def open_tags(node):
    """All open tags in document order — the crib of a tree."""
    tags = [node.tag]
    for c in node.children:
        tags.extend(open_tags(c))
    return tags
