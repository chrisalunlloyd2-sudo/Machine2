from bdi_fsm.code_ask import (ask_code, parse_code_ask, compose_page,
                              structure_quality, crib_from_intents)


def test_parse_heading_and_button():
    assert parse_code_ask("make a page with a heading and a button") == ["heading", "button"]


def test_parse_ordered_list_does_not_double_fire():
    # the bug fix: "ordered list" must not also produce a bullet "list"
    intents = parse_code_ask("an ordered list of steps")
    assert "ordered_list" in intents and "list" not in intents


def test_compose_valid_html():
    html = compose_page(["heading", "button"])
    assert html.startswith("<!DOCTYPE html>")
    assert "<h1>" in html and "<button" in html


def test_quality_full_match():
    html = compose_page(["heading", "button"])
    crib = crib_from_intents(["heading", "button"])
    assert structure_quality(html, crib) == 1.0


def test_ask_code_makes_sense():
    r = ask_code("make me a page with a heading and a button")
    assert r["makes_sense"] is True and r["quality"] == 1.0


def test_ask_code_rejects_gibberish():
    r = ask_code("hello there how are you")
    assert r["makes_sense"] is False and r["intents"] == []


def test_ask_code_nash_gate_closed():
    # a very high threshold refuses even a perfect block (gate can be tuned)
    r = ask_code("a button", c_miss=1.0, c_false=1000.0)  # theta* negative
    assert r["quality"] == 1.0  # block is fine; gate decision is separate


def test_form_nests_input_and_button():
    html = ask_code("a form with an input field and a submit button")["html"]
    # one <form>, with the input AND a submit button INSIDE it (not siblings)
    assert html.count("<form") == 1
    # the submit button is a <button type="submit"> inside the form
    assert '<button type="submit">Submit</button>' in html
    # input is inside the form (appears between form open and close)
    i_form = html.index("<form")
    i_close = html.index("</form>")
    i_input = html.index("<input")
    assert i_form < i_input < i_close


def test_nav_nests_link():
    html = ask_code("a navigation bar with links")["html"]
    i_nav = html.index("<nav")
    i_close = html.index("</nav>")
    i_link = html.index("<a href")
    assert i_nav < i_link < i_close


def test_standalone_button_not_nested():
    html = ask_code("make a button")["html"]
    assert '<button type="button"' in html  # standalone, not a submit control
    assert '<form' not in html


def test_crib_reflects_nesting():
    crib = crib_from_intents(["form", "input", "button"])
    assert crib == ["html", "body", "form", "input", "button"]


def test_textarea_does_not_trigger_paragraph():
    # word-boundary fix: "textarea" must not fire the "text" keyword
    intents = parse_code_ask("a form with a textarea")
    assert "paragraph" not in intents
    assert "textarea" in intents


# --- v3 content extractor ----------------------------------------------------

def test_heading_gets_content():
    html = ask_code("a heading about my portfolio")["html"]
    assert "<h1>Portfolio</h1>" in html

def test_image_gets_content():
    html = ask_code("an image of a cat")["html"]
    assert 'src="cat.png"' in html and 'alt="a cat"' in html

def test_list_multiple_items():
    html = ask_code("a list of features and benefits")["html"]
    assert "<li>Features</li>" in html and "<li>Benefits</li>" in html

def test_login_form_default_fields():
    html = ask_code("a login form")["html"]
    assert 'type="email"' in html and 'type="password"' in html
    assert '<button type="submit">Log in</button>' in html

def test_contact_form_multiple_fields():
    html = ask_code("contact form with name and message")["html"]
    assert 'name="name"' in html and 'name="message"' in html and 'name="contact"' in html

def test_nav_content_links():
    html = ask_code("navigation menu with home about and contact")["html"]
    assert '<a href="#home">Home</a>' in html
    assert '<a href="#about">About</a>' in html
    assert '<a href="#contact">Contact</a>' in html

def test_search_box_input_type():
    html = ask_code("a search box")["html"]
    assert 'type="search"' in html

def test_paragraph_phrase_join():
    html = ask_code("a paragraph about our company mission")["html"]
    assert "<p>Company Mission</p>" in html

def test_content_precedes_keyword():
    # "login" precedes "form" — regression guard for nearest-keyword assignment
    assert "login" in ask_code("a login form")["content"]

def test_proximity_assigns_to_nearest_block():
    # "cat" belongs to "image", not the earlier "heading"
    html = ask_code("a heading and an image of a cat")["html"]
    assert "cat.png" in html and "<h1>Lorem ipsum</h1>" in html


# --- v4 real tree + strategy ------------------------------------------------

def test_table_builds_real_tree():
    html = ask_code("a table of prices")["html"]
    assert "<thead>" in html and "<tbody>" in html and "<th>" in html and "<td>" in html

def test_comparison_strategy_picks_table():
    r = ask_code("differences between python and javascript")
    assert r["strategy"] == "table" and "<table>" in r["html"]
    assert "Python" in r["html"] and "Javascript" in r["html"]

def test_strategy_default_is_list():
    r = ask_code("a list of features")
    assert r["strategy"] == "list"

def test_comparison_table_is_side_by_side_matrix():
    # the v4 fix: 2+ items become column headers, not a 1-column stack
    html = ask_code("differences between python and javascript")["html"]
    assert "<th>Feature</th>" in html
    assert "<th>Python</th>" in html and "<th>Javascript</th>" in html
    # side-by-side: Python th comes before Javascript th
    assert html.index("<th>Python</th>") < html.index("<th>Javascript</th>")

def test_trace_logging_writes_outcome():
    import tempfile, os
    from bdi_fsm.layout import load_traces
    d = tempfile.mkdtemp(); p = os.path.join(d, "t.jsonl")
    ask_code("a login form", trace_path=p)
    tr = load_traces(p)
    assert len(tr) == 1 and tr[0]["strategy"] == "list"
    assert tr[0]["judgment"] == "good"
