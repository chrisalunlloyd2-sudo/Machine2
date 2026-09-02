"""ENIGMA LOCK — Turing's machine as a permutation "combination lock" gate.

Chris directive 2026-08-12: use REAL Enigma data as a combination lock, and
brute-force combinations until "game = Nash" (the decision-theoretic optimum).

What this actually is, rigorously:

    Enigma encrypts letter x as the composition of permutations
        E(x) = P^-1 . R^-1 . M^-1 . L^-1 . U . L . M . R . P (x)
    where P = plugboard (an involution), U = reflector (a fixed-point-free
    involution), and L/M/R are the three rotors (each a rotation-shifted
    permutation). The rotors ADVANCE after every letter (with a double-step
    anomaly on the middle rotor), so the key is a TIME-VARYING permutation.

    Two invariants make it the perfect lock:
      1. INVOLUTION:    E(E(x)) = x      (encrypt twice => plaintext)
      2. NO FIXED POINT: E(x) != x        (no letter ever maps to itself)

    Invariant #2 is the cryptanalytic "crib": Bletchley slid a guessed
    plaintext along ciphertext and rejected any setting where a letter touched
    itself. The Bombe brute-forced rotor settings with this pruning — NOT blind
    enumeration. That is exactly "brute force until the posterior concentrates"
    (Banburismus): keep adding evidence until one setting dominates, i.e. the
    game reaches its Nash optimum where no deviation improves the score.

Pure stdlib. Deterministic. Zero LLM. Real WWII wiring data (public domain,
recovered by Marian Rejewski 1932 and Bletchley Park).
"""
import math
from itertools import permutations as _permutations
from typing import Dict, List, Optional, Tuple

A = ord('A')
ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _idx(c: str) -> int:
    return ord(c.upper()) - A


def _chr(i: int) -> str:
    return ALPHABET[i % 26]


def _wiring(s: str) -> List[int]:
    return [_idx(c) for c in s]


# ---- REAL Wehrmacht Enigma I wiring (rotors I-VIII, reflectors B/C) ----
ROTORS = {
    "I":    ("EKMFLGDQVZNTOWYHXUSPAIBRCJ", [17]),       # notch R
    "II":   ("AJDKSIRUXBLHWTMCQGZNPYFVOE", [5]),        # notch F
    "III":  ("BDFHJLCPRTXVZNYEIWGAKMUSQO", [22]),       # notch W
    "IV":   ("ESOVPZJAYQUIRHXLNFTGKDCMWB", [10]),       # notch K
    "V":    ("VZBRGITYUPSDNHLXAWMJQOFECK", [0]),        # notch A
    "VI":   ("JPGVOUMFYQBENHZRDKASXLICTW", [0, 13]),    # notch A/N
    "VII":  ("NZJHGRCXMYSWBOUFAIVLPEKQDT", [0, 13]),    # notch A/N
    "VIII": ("FKQHTLXOCBJSPDZRAMEWNIUYGV", [0, 13]),    # notch A/N
}
REFLECTORS = {
    "B": "YRUHQSLDPXNGOKMIEBFZCWVJAT",
    "C": "FVPJIAOYEDRZXWGCTKUQSBNMHL",
}
ETW = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"  # entry wheel (identity)


class Rotor:
    __slots__ = ("name", "wiring", "inverse", "notches", "ring", "position")
    def __init__(self, name: str, wiring_s: str, notches: List[int], ring: int = 0, position: int = 0):
        self.name = name
        self.wiring = _wiring(wiring_s)
        self.inverse = [0] * 26
        for i, o in enumerate(self.wiring):
            self.inverse[o] = i
        self.notches = notches
        self.ring = ring
        self.position = position
    def advance(self):
        self.position = (self.position + 1) % 26
    def at_notch(self) -> bool:
        return self.position in self.notches
    def _shift(self) -> int:
        return (self.position - self.ring) % 26
    def forward(self, c: int) -> int:
        s = self._shift()
        return (self.wiring[(c + s) % 26] - s) % 26
    def backward(self, c: int) -> int:
        s = self._shift()
        return (self.inverse[(c + s) % 26] - s) % 26


class Plugboard:
    def __init__(self, pairs: Optional[List[Tuple[str, str]]] = None):
        self.map = list(range(26))
        for a, b in (pairs or []):
            ia, ib = _idx(a), _idx(b)
            self.map[ia], self.map[ib] = ib, ia
    def swap(self, c: int) -> int:
        return self.map[c]


class Enigma:
    """A faithful Enigma I. Steps BEFORE each letter (German procedure)."""
    def __init__(self, rotor_order: Tuple[str, str, str] = ("I", "II", "III"),
                 positions: Tuple[int, int, int] = (0, 0, 0),
                 rings: Tuple[int, int, int] = (0, 0, 0),
                 reflector: str = "B",
                 plugboard_pairs: Optional[List[Tuple[str, str]]] = None):
        # rotors stored LEFT, MIDDLE, RIGHT
        self.rotors = [Rotor(n, ROTORS[n][0], ROTORS[n][1], r, p)
                       for n, p, r in zip(rotor_order, positions, rings)]
        self.reflector = _wiring(REFLECTORS[reflector])
        self.plugboard = Plugboard(plugboard_pairs)

    # ---- the double-stepping anomaly ----
    def _step(self):
        left, middle, right = self.rotors
        if middle.at_notch():
            middle.advance()
            left.advance()
        elif right.at_notch():
            middle.advance()
        right.advance()

    def encrypt_letter(self, c: int) -> int:
        self._step()
        c = self.plugboard.swap(c)
        for r in reversed(self.rotors):      # right -> middle -> left
            c = r.forward(c)
        c = self.reflector[c]                # reflector
        for r in self.rotors:                # left -> middle -> right
            c = r.backward(c)
        return self.plugboard.swap(c)

    def encrypt(self, text: str) -> str:
        return "".join(_chr(self.encrypt_letter(_idx(c)))
                       for c in text.upper() if c.isalpha())

    def positions(self) -> Tuple[int, int, int]:
        return tuple(r.position for r in self.rotors)


def verify_invariants(plugboard_pairs=None):
    """Prove E(E(x))=x and E(x)!=x across the whole alphabet (fixed state)."""
    ok_inv = ok_nofix = True
    for c in range(26):
        e = Enigma(plugboard_pairs=plugboard_pairs)     # fresh (steps to pos 1)
        y = e.encrypt_letter(c)
        if y == c:
            ok_nofix = False
        e2 = Enigma(plugboard_pairs=plugboard_pairs)    # fresh (steps to pos 1)
        x_back = e2.encrypt_letter(y)
        if x_back != c:
            ok_inv = False
    return ok_inv, ok_nofix

def verify_wiring_bijections():
    """Every rotor and reflector must be a valid permutation (bijective)."""
    ok = True
    for name, (w, _) in ROTORS.items():
        lst = _wiring(w)
        if sorted(lst) != list(range(26)):
            ok = False
            print(f"  BAD rotor {name}: not a permutation")
    for name, w in REFLECTORS.items():
        lst = _wiring(w)
        if sorted(lst) != list(range(26)):
            ok = False
            print(f"  BAD reflector {name}: not a permutation")
        # reflector must be a fixed-point-free involution
        for i, o in enumerate(lst):
            if o == i or lst[o] != i:
                ok = False
                print(f"  BAD reflector {name}: not fixed-point-free involution")
                break
    return ok


# ---- THE LOCK: crib-matching brute force with no-fixed-point pruning ----
def brute_force_crib(ciphertext: str, crib: str, rotor_pool=("I", "II", "III"),
                     max_settings: int = 200000) -> List[Dict]:
    """Miniature Bombe. Search rotor order + positions for a setting where the
    crib fits the ciphertext, pruning each candidate with the no-fixed-point
    invariant (crib letter == ciphertext letter => reject instantly)."""
    crib = crib.upper()
    ciphertext = ciphertext.upper()
    hits = []
    for order in _permutations(rotor_pool, 3):
        for a in range(26):
            for b in range(26):
                for c in range(26):
                    e = Enigma(rotor_order=order, positions=(a, b, c))
                    ok = True
                    # no-fixed-point pruning across the crib span
                    for i, ch in enumerate(crib):
                        ct = ciphertext[i] if i < len(ciphertext) else None
                        if ct is None:
                            break
                        if ch == ct:      # impossible: no letter -> itself
                            ok = False
                            break
                    if not ok:
                        continue
                    # decrypt only the crib-length prefix (Enigma is its own inverse)
                    dec = e.encrypt(ciphertext[:len(crib)])
                    if dec == crib:
                        hits.append({"order": "-".join(order),
                                     "positions": "".join(_chr(x) for x in (a, b, c)),
                                     "decrypted": dec})
                        if len(hits) >= max_settings:
                            return hits
    return hits


def nash_threshold(c_miss: float, c_false: float) -> float:
    """Decision-theoretic optimum in BANS. Fire the gate when the observer's
    log-odds exceed log10(C_miss / C_false). This is the point where acting and
    not-acting have equal expected cost = the Nash equilibrium of the gate."""
    if c_false <= 0:
        return float("inf")
    return math.log10(c_miss / c_false)


def keyspace(rotor_pool_size: int = 5, plug_pairs: int = 10) -> Dict:
    """Total Enigma key space (real numbers)."""
    order = rotor_pool_size * (rotor_pool_size - 1) * (rotor_pool_size - 2)
    positions = 26 ** 3
    # plugboard: choose 2*plug_pairs letters, pair them
    p = 26
    plug = 1
    import math as _m
    for k in range(plug_pairs):
        plug *= _m.comb(p - 2 * k, 2)
    plug //= _m.factorial(plug_pairs)
    total = order * positions * plug
    return {"rotor_order": order, "rotor_positions": positions,
            "plugboard": plug, "total": total}


if __name__ == "__main__":
    inv, nofix = verify_invariants()
    print(f"INVOLUTION (E(E(x))=x): {'PASS' if inv else 'FAIL'}")
    print(f"NO-FIXED-POINT (E(x)!=x): {'PASS' if nofix else 'FAIL'}")

    e = Enigma(rotor_order=("I", "II", "III"), positions=(0, 0, 0))
    ct = e.encrypt("HELLOWORLD")
    print("encrypt HELLOWORLD ->", ct)

    # reciprocity: decrypt the same ciphertext from the SAME starting state
    e2 = Enigma(rotor_order=("I", "II", "III"), positions=(0, 0, 0))
    pt = e2.encrypt(ct)
    print("decrypt (same state) ->", pt, "==", pt == "HELLOWORLD")

    ks = keyspace()
    print("KEYSPACE: order", ks["rotor_order"], "x positions", ks["rotor_positions"],
          "x plugboard", ks["plugboard"], "=", f'{ks["total"]:.3e}')
    print("NASH THRESHOLD (C_miss=10, C_false=1):", nash_threshold(10, 1), "bans")
