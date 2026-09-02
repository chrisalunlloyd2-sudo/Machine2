"""HTML rotor codec tests — tag balance + structure-match crib."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bdi_fsm.rotor_codec_html import (HTML_SKELETON, _parse_structure,
                                      generate_html, make_html_test_fn,
                                      brute_find_html, plain_enumerate_html)


def test_parse_structure_balanced():
    ok, tags = _parse_structure("<html><body><p>x</p></body></html>")
    assert ok and tags == ["html", "body", "p"]


def test_parse_structure_nested():
    ok, tags = _parse_structure("<div><ul><li>a</li></ul></div>")
    assert ok and tags == ["div", "ul", "li"]


def test_parse_structure_unbalanced_wrong_close():
    ok, tags = _parse_structure("<p>x</div>")
    assert not ok and tags == []


def test_parse_structure_unclosed():
    ok, tags = _parse_structure("<div><p>x</p>")   # div never closed
    assert not ok and tags == []


def test_parse_structure_void_and_selfclosing():
    ok, tags = _parse_structure("<img src='x.png'><br/><hr>")
    assert ok and tags == ["img", "br", "hr"]


def test_parse_structure_skips_comments_doctype():
    ok, tags = _parse_structure("<!DOCTYPE html><!-- hi --><p>x</p>")
    assert ok and tags == ["p"]


def test_generate_html_picks_fragment():
    grammar = ['<p>a</p>', '<div>b</div>']
    out = generate_html(grammar, 0)
    assert out == HTML_SKELETON.replace("__FRAGMENT__", grammar[0])


def test_make_html_test_fn():
    test = make_html_test_fn(["html", "body", "p"])
    assert test("<html><body><p>x</p></body></html>") == 1.0
    assert test("<html><body><div>x</div></body></html>") == 0.0  # wrong structure
    assert test("<html><body><p>x</div></body></html>") == 0.0    # unbalanced


def test_brute_find_html():
    grammar = ['<p>hello</p>', '<div>box</div>', '<span>inline</span>',
               '<ul><li>item</li></ul>']
    r = brute_find_html(grammar, ["html", "body", "ul", "li"])
    assert r["found"] is True
    assert "<ul>" in r["html"]
    assert abs(r["theta_bans"] - 1.0) < 1e-9   # c_miss=10, c_false=1


def test_plain_enumerate_html():
    grammar = ['<p>hello</p>', '<div>box</div>', '<span>inline</span>',
               '<h1>title</h1>']
    r = plain_enumerate_html(grammar, ["html", "body", "h1"])
    assert r["found"] is True
    assert "<h1>" in r["html"]
