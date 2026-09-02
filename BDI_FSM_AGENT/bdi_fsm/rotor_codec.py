"""ROTOR CODEC — Enigma rotor mechanics as a collision-free code search.

Chris's end-game: apply the Enigma rotor (a bijective permutation) to CODE
synthesis. A "key" (rotor order + positions + rings + plugboard) maps,
deterministically, to a distinct program candidate. Brute-forcing keys = searching
the code space WITHOUT repeating a candidate.

  enumerator  = rotor_permutation  (collision-free, well-distributed key -> order)
  crib        = the test            (definitive input -> expected output compare)
  stop        = nash_threshold      (log10(C_miss/C_false)) + plateau detection
  fallback    = plain_enumerate     (no-fail brute foundry: try every fragment)

NO LLM. Deterministic. Symbolic.
"""
from itertools import permutations as _perm
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from .enigma_lock import Enigma, nash_threshold

ROTOR_NAMES = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII"]
_ROTOR_ORDERS: List[Tuple[str, str, str]] = list(_perm(ROTOR_NAMES, 3))  # 336


def key_to_enigma(key: int) -> Enigma:
    """Deterministically map a non-negative integer key to an Enigma machine.

    Distinct keys in the low range -> distinct machine settings (rotor order,
    positions, rings, plugboard), so the resulting permutations are distinct.
    """
    key = int(key) % (10 ** 12)
    o = key % len(_ROTOR_ORDERS); key //= len(_ROTOR_ORDERS)
    rotor_order = _ROTOR_ORDERS[o]
    p1 = key % 26; key //= 26
    p2 = key % 26; key //= 26
    p3 = key % 26; key //= 26
    positions = (p1, p2, p3)
    r1 = key % 26; key //= 26
    r2 = key % 26; key //= 26
    r3 = key % 26; key //= 26
    rings = (r1, r2, r3)
    # plugboard: derive up to 5 disjoint pairs from the remaining key bits
    pairs: List[Tuple[str, str]] = []
    used = set()
    n_pairs = key % 6; key //= 6
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    while len(pairs) < n_pairs and key > 0:
        ia = key % 26; key //= 26
        ib = key % 26; key //= 26
        if ia != ib and ia not in used and ib not in used:
            pairs.append((alphabet[ia], alphabet[ib]))
            used.update((ia, ib))
    return Enigma(rotor_order=rotor_order, positions=positions, rings=rings,
                  reflector="B", plugboard_pairs=pairs)


def _keystream(key: int, length: int) -> List[int]:
    """Deterministic int stream 0..25 driven by the rotor's time-varying map."""
    enigma = key_to_enigma(key)
    msg = "ABCDEFGHIJKLMNOPQRSTUVWXYZ" * ((length // 26) + 1)
    return [ord(c) - 65 for c in enigma.encrypt(msg[:length])]


def rotor_permutation(n: int, key: int) -> List[int]:
    """Collision-free permutation of [0..n) driven by the rotor keystream."""
    if n <= 0:
        return []
    ks = _keystream(key, max(n, 2) * 2 + 4)
    arr = list(range(n))
    j = 0
    for i in range(n - 1, 0, -1):
        r = ks[j % len(ks)]; j += 1
        k = r % (i + 1)
        arr[i], arr[k] = arr[k], arr[i]
    return arr


def generate_program(grammar: Sequence[str], key: int,
                     signature: str = "def f(a, b):",
                     indent: str = "    ", k: Optional[int] = None) -> str:
    """Assemble a program from an ORDERING of body statements chosen by the rotor.

    THE COMPOSITION LAYER, WHICH USED TO BE MISSING. v1 computed the whole
    permutation and then returned `grammar[perm[0]]` -- one fragment. Measured
    2026-08-31 over a 10-fragment grammar and 20,000 keys: the rotor produced
    17,406 DISTINCT permutations and this function collapsed every one of them
    into 10 distinct programs. 0.05% of keys did anything new; brute_find spent
    the other 19,990 re-testing the same ten candidates.

    Worse than wasteful: because the body was always ONE statement, refining a
    working 6-line function returned a 2-line one. A real case from the pool --

        def write_file(path, content):
            import os

    -- which writes nothing, scored 1.00 on a parse-only oracle and was recorded
    as a WIN. The gate that catches those bodies was fixed on 2026-08-22; the
    thing MANUFACTURING them was this line.

    Now the permutation is used in full: key -> a distinct ordering of k body
    statements. The search space goes from n to n!/(n-k)!, which is what makes
    "brute-force the code space without repeating a candidate" true rather than
    aspirational.

    Fragments may be multi-line (an unparsed `with` block is one statement), so
    each line carries the base indent and keeps its own relative indentation --
    a block is permuted as a unit and can never be split down the middle.
    """
    n = len(grammar)
    if n == 0:
        return f"{signature}\n{indent}pass\n"
    perm = rotor_permutation(n, key)
    k = n if k is None else max(1, min(int(k), n))
    lines = []
    for idx in perm[:k]:
        frag = str(grammar[idx])
        for line in (frag.splitlines() or [""]):
            lines.append((indent + line) if line.strip() else "")
    return signature + "\n" + "\n".join(lines) + "\n"


def _normalize(score) -> float:
    if score is True:
        return 1.0
    if score is False or score is None:
        return 0.0
    return float(score)


def brute_find(grammar: Sequence[str], test_fn: Callable[[str], float],
               signature: str = "def f(a, b):", max_keys: int = 20000,
               c_miss: float = 10.0, c_false: float = 1.0,
               patience: int = 60) -> Dict:
    """Brute-force rotor keys until the crib (test_fn) is matched.

    test_fn(source) -> float in [0,1] (fraction of test cases passed). 1.0 = pass.
    Stops at: crib match, score plateau (no improvement for `patience` candidates),
    or max_keys. Returns theta* = nash_threshold(c_miss, c_false) in bans so the
    caller can see the Nash stop threshold that gates commit-vs-keep-searching.
    """
    theta_bans = nash_threshold(c_miss, c_false)
    seen = set()
    best = None
    stagnant = 0
    attempts = 0
    for key in range(max_keys):
        src = generate_program(grammar, key, signature)
        if src in seen:
            continue
        seen.add(src)
        attempts += 1
        score = _normalize(test_fn(src))
        if score >= 1.0:
            return {"found": True, "source": src, "key": key,
                    "attempts": attempts, "score": 1.0,
                    "theta_bans": theta_bans, "reason": "crib matched"}
        if best is None or score > best["score"]:
            best = {"source": src, "key": key, "score": score}
            stagnant = 0
        else:
            stagnant += 1
        if stagnant >= patience:
            return {"found": False, "best": best, "attempts": attempts,
                    "theta_bans": theta_bans, "reason": "plateau"}
    return {"found": False, "best": best, "attempts": attempts,
            "theta_bans": theta_bans, "reason": "exhausted"}


def plain_enumerate(grammar: Sequence[str], test_fn: Callable[[str], float],
                    signature: str = "def f(a, b):",
                    indent: str = "    ") -> Dict:
    """No-fail brute foundry fallback: try every fragment in order, no rotor.

    Guaranteed to terminate and to test every candidate exactly once — the
    deterministic floor under the rotor path if the rotor can't build a valid
    program for a target language.
    """
    seen = set()
    attempts = 0
    for i, frag in enumerate(grammar):
        src = f"{signature}\n{indent}{frag}\n"
        if src in seen:
            continue
        seen.add(src)
        attempts += 1
        score = _normalize(test_fn(src))
        if score >= 1.0:
            return {"found": True, "source": src, "key": i,
                    "attempts": attempts, "score": 1.0, "reason": "crib matched"}
    return {"found": False, "best": None, "attempts": attempts,
            "reason": "exhausted"}
