"""code_ask.py — human-readable code asks -> nested HTML tree, Nash-stopped rotor.

Chris 2026-08-15: "make an entry point for human readable code asks ... start
with blocks for a html webpage and make the nash stop the rotor when the block
makes sense." v2 added a BLOCK GRAMMAR (containers nest their children). v3
added a CONTENT EXTRACTOR (real nouns/verbs into placeholders). v4 makes it
STRUCTURAL: the FSM builds a real DOM tree (dom.py) and a separate renderer
emits HTML — templates become node TYPES, not output macros. A layout-strategy
meta-state (layout.py) decides table vs list before the lower-level FSM
enforces structural correctness.

Builds on rotor_codec_html._parse_structure (tag-balance crib) and
enigma_lock.nash_threshold (the stop condition, log10(C_miss/C_false)).
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from .dom import TreeBuilder, open_tags, render
from .enigma_lock import nash_threshold
from .layout import RuleBank, choose_strategy, features_from, log_trace
from .pos_db import _STOP
from .rotor_codec_html import _parse_structure

# --- block library -----------------------------------------------------------

# containers nest their children (mirrors dom.SCHEMA)
CONTAINER_ACCEPTS: Dict[str, set] = {
    "form": {"input", "textarea", "button"},
    "nav": {"link"},
}

INTENT_KEYWORDS: Dict[str, List[str]] = {
    "button": ["button", "click"],
    "heading": ["heading", "title", "headline", "h1"],
    "subheading": ["subheading", "subtitle", "h2"],
    "paragraph": ["paragraph", "description", "describe", "text"],
    "image": ["image", "picture", "photo", "img"],
    "link": ["link", "url", "href", "hyperlink"],
    "list": ["list", "bullet", "ul"],
    "ordered_list": ["ordered", "numbered", "ol", "steps"],
    "input": ["input", "textbox", "text field", "entry", "box"],
    "textarea": ["textarea", "multiline", "comment"],
    "form": ["form", "submit", "login", "signup"],
    "table": ["table", "rows", "columns", "grid"],
    "header": ["header", "banner"],
    "nav": ["nav", "navigation", "navbar", "menu"],
    "footer": ["footer"],
}

# --- content extraction ------------------------------------------------------

_STRUCTURAL = {
    "button", "click", "heading", "title", "headline", "subheading", "subtitle",
    "paragraph", "description", "describe", "text", "image", "picture", "photo",
    "img", "link", "url", "href", "hyperlink", "list", "bullet", "ordered",
    "numbered", "steps", "input", "textbox", "entry", "textarea", "multiline",
    "comment", "form", "submit", "table", "rows", "columns", "grid", "header",
    "banner", "nav", "navigation", "navbar", "menu", "footer", "field", "box",
    "bar", "make", "create", "build", "add", "want", "need", "give", "show",
    "display", "render", "generate", "produce", "write", "page", "webpage",
    "website", "site", "html", "please", "like", "using", "that", "has", "have",
    "h1", "h2", "compare", "comparison", "comparing", "versus", "difference",
    "differences", "diff", "between",
}

_EXTRA_STOP = {"our", "ours", "us", "them", "hello", "hi", "hey", "there",
               "how", "yes", "no", "here", "any", "some", "all", "each",
               "every", "both"}

_ACTION = {"signup", "login", "log", "signin", "signout", "logout", "register",
           "subscribe", "search", "send", "save", "download", "upload", "join",
           "continue", "order", "buy"}

_ACTION_LABEL = {"signup": "Sign up", "login": "Log in", "log": "Log in",
                 "signin": "Sign in", "signout": "Sign out", "logout": "Log out",
                 "register": "Register", "subscribe": "Subscribe", "search": "Search",
                 "send": "Send", "save": "Save", "download": "Download",
                 "upload": "Upload", "join": "Join", "continue": "Continue",
                 "order": "Order", "buy": "Buy"}

_DEFAULT_FIELDS = {"signup": ["email", "password"], "login": ["email", "password"],
                   "log": ["email", "password"], "register": ["email", "password"],
                   "signin": ["email", "password"], "search": ["query"],
                   "subscribe": ["email"]}

_INPUT_TYPES = {"email": "email", "password": "password", "passwd": "password",
                "phone": "tel", "number": "number", "search": "search"}

_ACTION_PAIRS = {("sign", "up"): "signup", ("sign", "in"): "signin",
                 ("sign", "out"): "signout", ("log", "in"): "login",
                 ("log", "out"): "logout"}

_DEFAULT_BANK = RuleBank()


def _title(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


def _phrase(words: List[str]) -> str:
    return " ".join(_title(w) for w in words)


def _tokens_with_pos(q: str) -> List[Tuple[str, int, int]]:
    return [(m.group(0), m.start(), m.end())
            for m in re.finditer(r"[a-z0-9_+-]+", q)]


def _collapse_actions(toks: List[Tuple[str, int, int]]) -> List[Tuple[str, int, int]]:
    out: List[Tuple[str, int, int]] = []
    i = 0
    while i < len(toks):
        w, s, e = toks[i]
        if i + 1 < len(toks) and (w, toks[i + 1][0]) in _ACTION_PAIRS:
            out.append((_ACTION_PAIRS[(w, toks[i + 1][0])], s, toks[i + 1][2]))
            i += 2
            continue
        out.append((w, s, e))
        i += 1
    return out


def extract_content(question: str) -> List[Tuple[str, int]]:
    """Return [(word, pos), ...] content tokens in document order."""
    q = (question or "").lower()
    toks = _collapse_actions(_tokens_with_pos(q))
    content = [(w, s) for (w, s, e) in toks
               if len(w) > 2 and w not in _STOP and w not in _STRUCTURAL
               and w not in _EXTRA_STOP]
    if content and content[0][0] == "about" and len(content) > 1:
        content = content[1:]
    return content


def split_action(words: List[str]) -> Tuple[List[str], List[str]]:
    fields = [w for w in words if w not in _ACTION]
    actions = [w for w in words if w in _ACTION]
    return fields, actions


# --- parsing ----------------------------------------------------------------

def _keyword_positions(question: str) -> Dict[str, int]:
    q = (question or "").lower()
    out: Dict[str, int] = {}
    for block, kws in INTENT_KEYWORDS.items():
        positions = []
        for k in kws:
            m = re.search(r"\b" + re.escape(k) + r"\b", q)
            if m:
                positions.append(m.start())
        if positions:
            out[block] = min(positions)
    return out


def parse_code_ask(question: str) -> List[str]:
    """Map a natural-language ask to block intents, ordered by first mention."""
    kw = _keyword_positions(question)
    intents = [b for b, _ in sorted(kw.items(), key=lambda kv: kv[1])]
    if "ordered_list" in intents and "list" in intents:
        intents = [b for b in intents if b != "list"]
    return intents


def _assign_content(content: List[Tuple[str, int]],
                    kw_positions: Dict[str, int]) -> Dict[str, List[str]]:
    """Assign each content token to its NEAREST block keyword (either side)."""
    assigned: Dict[str, List[str]] = {}
    for word, pos in content:
        best_block, best_dist = None, None
        for block, kpos in kw_positions.items():
            dist = abs(kpos - pos)
            if best_dist is None or dist < best_dist:
                best_dist = dist
                best_block = block
        if best_block:
            assigned.setdefault(best_block, []).append(word)
    return assigned


# --- tree building (the FSM builds a TREE; render() is a separate pass) ------

def build_tree(intents: List[str], assigned: Optional[Dict[str, List[str]]] = None) -> List[dict]:
    """Greedy one-level nesting + content synthesis for empty containers."""
    assigned = assigned or {}
    nodes: List[dict] = []
    current = None
    for name in intents:
        if name in CONTAINER_ACCEPTS:
            node = {"container": name, "children": [], "action": None}
            nodes.append(node)
            current = node
        else:
            tok = assigned.get(name, [])
            if current is not None and name in CONTAINER_ACCEPTS[current["container"]]:
                current["children"].append({"leaf": name, "content": tok})
            else:
                nodes.append({"leaf": name, "content": tok})
    for node in nodes:
        if "container" not in node or node["children"]:
            continue
        cname = node["container"]
        words = assigned.get(cname, [])
        if cname == "form":
            fields, actions = split_action(words)
            flds = fields or _DEFAULT_FIELDS.get(actions[0] if actions else "", [])
            node["children"] = [{"leaf": "input", "content": t} for t in flds[:4]]
            node["action"] = actions[0] if actions else None
        elif cname == "nav" and words:
            node["children"] = [{"leaf": "link", "content": t} for t in words[:6]]
    return nodes


def _add_table(b: TreeBuilder, words: List[str]) -> None:
    """A REAL table. >=2 items -> side-by-side matrix (leading Feature column
    + one column header per item); 1 item -> simple header + data row."""
    items = [w for w in words if w]
    b.enter("table")
    if len(items) >= 2:
        b.enter("thead")
        b.enter("tr")
        b.leaf("th", text="Feature")
        for it in items:
            b.leaf("th", text=_title(it))
        b.exit()  # tr
        b.exit()  # thead
        b.enter("tbody")
        b.enter("tr")
        b.leaf("td", text="\u2014")
        for _ in items:
            b.leaf("td", text="\u2014")
        b.exit()  # tr
        b.exit()  # tbody
    else:
        header = items[0] if items else None
        b.enter("thead")
        b.enter("tr")
        b.leaf("th", text=_title(header) if header else "Header")
        b.exit()  # tr
        b.exit()  # thead
        b.enter("tbody")
        b.enter("tr")
        b.leaf("td", text="Cell")
        b.exit()  # tr
        b.exit()  # tbody
    b.exit()  # table


def _add_leaf(b: TreeBuilder, name: str, words=None, in_form: bool = False):
    if isinstance(words, str):
        words = [words]
    words = list(words or [])
    tok = words[0] if words else None
    title = _title(tok) if tok else None

    if name == "button":
        if in_form:
            return b.leaf("button", {"type": "submit"}, text="Submit")
        return b.leaf("button", {"type": "button", "onclick": "alert('clicked')"},
                      text=title or "Click me")
    if name == "heading":
        return b.leaf("h1", text=_phrase(words) if words else "Lorem ipsum")
    if name == "subheading":
        return b.leaf("h2", text=_phrase(words) if words else "Lorem ipsum")
    if name == "paragraph":
        return b.leaf("p", text=_phrase(words) if words else "Lorem ipsum")
    if name == "image":
        return b.leaf("img", {"src": (tok + ".png") if tok else "image.png",
                              "alt": ("a " + tok) if tok else "an image"})
    if name == "link":
        return b.leaf("a", {"href": ("#" + tok) if tok else "#"},
                      text=title or "Lorem ipsum")
    if name == "input":
        itype = _INPUT_TYPES.get(tok, "text") if tok else "text"
        return b.leaf("input", {"type": itype,
                                "name": tok.replace(" ", "_") if tok else "field",
                                "placeholder": tok if tok else "Enter text"})
    if name == "textarea":
        return b.leaf("textarea", {"rows": "4", "cols": "40",
                                   "name": tok.replace(" ", "_") if tok else "field"})
    if name in ("list", "ordered_list"):
        tag = "ul" if name == "list" else "ol"
        b.enter(tag)
        for w in (words or [None]):
            b.leaf("li", text=_title(w) if w else "Item")
        b.exit()
        return
    if name == "table":
        return _add_table(b, words)
    if name == "header":
        b.enter("header")
        b.leaf("h1", text=_phrase(words) if words else "Lorem ipsum")
        b.exit()
        return
    if name == "footer":
        b.enter("footer")
        b.leaf("p", text=_phrase(words) if words else "Lorem ipsum")
        b.exit()
        return
    return None


def _add_container(b: TreeBuilder, node: dict):
    name = node["container"]
    children = node["children"]
    if name == "form":
        b.enter("form", {"action": "#", "method": "post"})
        has_button = False
        for ch in children:
            if ch["leaf"] == "button":
                has_button = True
            _add_leaf(b, ch["leaf"], ch.get("content"), in_form=True)
        if not has_button:
            action = node.get("action")
            lbl = _ACTION_LABEL.get(action, _title(action)) if action else "Submit"
            b.leaf("button", {"type": "submit"}, text=lbl)
        if not children:
            b.leaf("input", {"type": "submit", "value": "Submit"})
        b.exit()
        return
    if name == "nav":
        b.enter("nav")
        for ch in children:
            _add_leaf(b, "link", ch.get("content"))
        if not children:
            b.leaf("a", {"href": "#"}, text="Home")
        b.exit()
        return
    _add_leaf(b, name, [])


def _add_node(b: TreeBuilder, node: dict):
    if "leaf" in node:
        return _add_leaf(b, node["leaf"], node.get("content"))
    return _add_container(b, node)


def compose_page(intents: List[str], assigned: Optional[Dict[str, List[str]]] = None) -> str:
    """Build the tree, then render it (FSM builds, renderer emits)."""
    b = TreeBuilder()
    for node in build_tree(intents, assigned):
        _add_node(b, node)
    return "<!DOCTYPE html>\n" + render(b.html)


def crib_from_intents(intents: List[str],
                      assigned: Optional[Dict[str, List[str]]] = None) -> List[str]:
    """Expected open-tag list = the tree's own open tags (crib == structure)."""
    b = TreeBuilder()
    for node in build_tree(intents, assigned):
        _add_node(b, node)
    return open_tags(b.html)


def structure_quality(html: str, crib: Optional[List[str]] = None) -> float:
    """0..1: tag balance (0 if unbalanced) else fraction of crib matched in order."""
    ok, tags = _parse_structure(html)
    if not ok:
        return 0.0
    if not crib:
        return 1.0
    matched = 0
    ti = 0
    for tag in tags:
        if ti < len(crib) and tag == crib[ti]:
            matched += 1
            ti += 1
    return matched / len(crib)


def ask_code(question: str, c_miss: float = 10.0, c_false: float = 1.0,
             trace_path: Optional[str] = None) -> Dict:
    """The entry point: ask -> strategy meta-state -> blocks -> tree -> Nash gate.

    If trace_path is set, the outcome is appended as a trace (features +
    strategy + quality + judgment) for later rule mining / meaning promotion.
    """
    from .calc import similarity_ban
    theta = nash_threshold(c_miss, c_false)
    intents = parse_code_ask(question)
    content = extract_content(question)
    content_words = [w for w, _ in content]
    assigned = _assign_content(content, _keyword_positions(question))

    features = features_from(question, intents, content_words)
    # strategy meta-state: choose layout BEFORE the lower-level FSM builds.
    strategy = choose_strategy(features)
    if not intents and strategy == "table" and len(content_words) >= 2:
        intents = ["table"]  # comparison -> table (no explicit keyword needed)
        assigned = {"table": content_words}

    result: Dict = {"question": question, "intents": intents,
                    "content": content_words, "features": features,
                    "strategy": strategy, "html": None, "quality": 0.0,
                    "ban": float("-inf"), "theta_bans": round(theta, 3),
                    "makes_sense": False, "reason": "no block intents recognized"}
    if intents:
        html = compose_page(intents, assigned)
        q = structure_quality(html, crib_from_intents(intents, assigned))
        if q >= 1.0:
            ban = float("inf")
        elif q <= 0.0:
            ban = float("-inf")
        else:
            ban = similarity_ban(2 * q - 1)
        result.update({"html": html, "quality": round(q, 3),
                       "ban": ban if ban in (float("inf"), float("-inf")) else round(ban, 2),
                       "makes_sense": ban >= theta,
                       "reason": "crib matched, rotor stopped" if ban >= theta
                                 else "below nash threshold, keep stepping"})

    if trace_path:
        log_trace(trace_path, {
            "question": question, "intents": result["intents"],
            "features": features, "strategy": strategy,
            "quality": result["quality"], "makes_sense": result["makes_sense"],
            "judgment": "good" if result["makes_sense"] else "bad",
        })
    return result
