"""ROTOR CODEC — HTML crib. Same Enigma permutation, different filter.

The rotor (bijective key -> candidate) is language-agnostic; only the CRIB
changes. Python = exec + compare. Java = javac compile + run + compare.
HTML = tag-balance (well-formedness) + ordered-tag-structure match (tree diff).

  enumerator  = rotor_permutation    (shared with rotor_codec.py)
  crib        = tag balance + structure match
  stop        = nash_threshold       (log10(C_miss/C_false))
  fallback    = plain_enumerate_html (no-fail brute foundry)

NO LLM. Deterministic. Symbolic.
"""
import re
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from .enigma_lock import nash_threshold
from .rotor_codec import _normalize, rotor_permutation

HTML_SKELETON = "<!DOCTYPE html>\n<html><body>\n__FRAGMENT__\n</body></html>\n"

# Elements that never take a closing tag (self-contained).
VOID_ELEMENTS = {"area", "base", "br", "col", "embed", "hr", "img", "input",
                 "link", "meta", "param", "source", "track", "wbr"}

_TAG_RE = re.compile(r"</?([a-zA-Z][a-zA-Z0-9-]*)")


def _parse_structure(html: str) -> Tuple[bool, List[str]]:
    """Tag-balance parser -> (balanced, ordered open-tag list).

    The crib's "compile" step: a candidate is well-formed iff every non-void
    open tag has a matching close in a legal order (a stack never crosses).
    Returns (False, []) on any imbalance. Comments and <!DOCTYPE> are skipped
    because their '<' is followed by '!'/'?', never a letter.
    """
    stack: List[str] = []
    tags: List[str] = []
    for m in _TAG_RE.finditer(html):
        name = m.group(1).lower()
        closing = html[m.start():m.start() + 2] == "</"
        if closing:
            if not stack or stack[-1] != name:
                return False, []
            stack.pop()
        else:
            tags.append(name)
            if name not in VOID_ELEMENTS:
                stack.append(name)
    return (len(stack) == 0), (tags if not stack else [])


def generate_html(grammar: Sequence[str], key: int) -> str:
    """Assemble a full HTML document whose body is the rotor-chosen fragment.

    v1 = single-fragment body (the rotor picks WHICH fragment). Composition is
    deferred so every generated document is trivially well-formed — the HTML
    analog of rotor_codec.generate_program.
    """
    perm = rotor_permutation(len(grammar), key)
    return HTML_SKELETON.replace("__FRAGMENT__", grammar[perm[0]])


def make_html_test_fn(target_structure: Sequence[str]) -> Callable[[str], float]:
    """Return test_fn(html) -> float: 1.0 iff well-formed AND tag order matches.

    target_structure is the full ordered open-tag list INCLUDING the skeleton's
    html/body wrapper, e.g. ['html', 'body', 'div', 'p'] for a <div><p></p></div>.
    """
    target = list(target_structure)

    def test_fn(html: str) -> float:
        ok, tags = _parse_structure(html)
        if not ok:
            return 0.0
        return 1.0 if tags == target else 0.0

    return test_fn


def brute_find_html(grammar: Sequence[str], target_structure: Sequence[str],
                    max_keys: int = 20000, c_miss: float = 10.0,
                    c_false: float = 1.0, patience: int = 60) -> Dict:
    """Brute-force rotor keys until the HTML crib (balance + structure) matches.

    Mirrors rotor_codec.brute_find with the tag-tree crib. Returns theta* in
    bans (nash_threshold) so the caller sees the commit-vs-keep-searching stop.
    """
    test_fn = make_html_test_fn(target_structure)
    theta_bans = nash_threshold(c_miss, c_false)
    seen = set()
    best = None
    stagnant = 0
    attempts = 0
    for key in range(max_keys):
        html = generate_html(grammar, key)
        if html in seen:
            continue
        seen.add(html)
        attempts += 1
        score = _normalize(test_fn(html))
        if score >= 1.0:
            return {"found": True, "html": html, "key": key,
                    "attempts": attempts, "score": 1.0,
                    "theta_bans": theta_bans, "reason": "crib matched"}
        if best is None or score > best["score"]:
            best = {"html": html, "key": key, "score": score}
            stagnant = 0
        else:
            stagnant += 1
        if stagnant >= patience:
            return {"found": False, "best": best, "attempts": attempts,
                    "theta_bans": theta_bans, "reason": "plateau"}
    return {"found": False, "best": best, "attempts": attempts,
            "theta_bans": theta_bans, "reason": "exhausted"}


def plain_enumerate_html(grammar: Sequence[str],
                         target_structure: Sequence[str]) -> Dict:
    """No-fail brute foundry fallback for HTML: try every fragment in order.

    Guaranteed to terminate and to test every candidate exactly once — the
    deterministic floor under the rotor path.
    """
    test_fn = make_html_test_fn(target_structure)
    seen = set()
    attempts = 0
    for i, frag in enumerate(grammar):
        html = HTML_SKELETON.replace("__FRAGMENT__", frag)
        if html in seen:
            continue
        seen.add(html)
        attempts += 1
        score = _normalize(test_fn(html))
        if score >= 1.0:
            return {"found": True, "html": html, "key": i,
                    "attempts": attempts, "score": 1.0, "reason": "crib matched"}
    return {"found": False, "best": None, "attempts": attempts,
            "reason": "exhausted"}


if __name__ == "__main__":
    grammar = ['<p class="p">hello</p>', '<div class="d">box</div>',
               '<span>inline</span>', '<h1>title</h1>',
               '<ul><li>item</li></ul>', '<a href="#">link</a>']
    target = ["html", "body", "ul", "li"]   # want the <ul><li> structure
    r = brute_find_html(grammar, target)
    print("brute_find_html:", r["found"], "key", r.get("key"),
          "attempts", r["attempts"], "theta*", round(r["theta_bans"], 3), "bans")
    if r["found"]:
        print(r["html"])
