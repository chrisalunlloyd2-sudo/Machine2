"""py4qwhip block 02 — kāraka: the semantic role layer.

Design notes (Chris, verbatim, 2026-10-12):
  kāraka = Sanskrit grammatical roles (agent, object, instrument, ...) — the
  bytecode carries a small role table so a synthesized module knows WHO does
  WHAT with WHICH instrument, not just raw operands. This is what makes
  synthesis *guided*: the resolver (block 04) reads roles, not guesses.

Roles (fixed, deterministic):
    AGT  agent      - who acts
    PAT  patient    - what is acted on
    KRN  instrument - the means
    DST  destination- where it goes
    SRC  source     - where it comes from
    RCP  recipient  - who receives

A KarakaTable is a frozen mapping (role -> slot index into frame locals).
Deterministic, stdlib-only, no I/O, no network. Local-only by construction.

Author: Hermes (Hermes=dense-code lane, per tasks/py4qwhip_lanes_20261012.md)
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

ROLES = ("AGT", "PAT", "KRN", "DST", "SRC", "RCP")
ROLE_IDS = {r: i for i, r in enumerate(ROLES)}


class KarakaError(Exception):
    """Deterministic kāraka fault (unknown role, bad slot, arity mismatch)."""


def _pq_karaka_wire(op, req):
    # -- pq4 wrapper (milestone 6, step 6 FILE-LEVEL): one block-02 op call
    # to the Rust pq.dll over pq_karaka_json (C ABI). Returns the parsed
    # ok:true response dict, or None on dll refusal -- callers fall through
    # to the verbatim pure-Python bodies so native KarakaError texts and
    # int() slot semantics stay exact (D168/D258/D269).
    import ctypes, json as _json, os as _os, sys
    lib = getattr(_pq_karaka_wire, "_lib", None)
    if lib is None:
        path = _os.path.join(_os.path.dirname(_os.path.dirname(
            _os.path.abspath(__file__))),
            "rust", "pq", "target", "release", "pq.dll")
        if not _os.path.isfile(path):
            raise KarakaError("pq4 dll not found: %s" % path)
        lib = ctypes.CDLL(str(path))
        lib.pq_karaka_json.argtypes = [ctypes.c_char_p]
        lib.pq_karaka_json.restype = ctypes.c_void_p
        lib.pq_free.argtypes = [ctypes.c_void_p]
        lib.pq_free.restype = None
        _pq_karaka_wire._lib = lib
    req = dict(req); req["op"] = op
    ptr = lib.pq_karaka_json(_json.dumps(req).encode("utf-8"))
    if not ptr:
        raise KarakaError("pq_karaka_json returned null")
    raw = ctypes.string_at(ptr)
    lib.pq_free(ptr)
    resp = _json.loads(raw.decode("utf-8"))
    if resp.get("ok") is not True:
        print("pq4: dll refused (%s); re-running pure-Python body"
              % _json.dumps(resp.get("error"))[:120], file=sys.stderr)
        return None
    return resp


def _pq_karaka_pairs(binding):
    # Ctor-binding snapshot as [role, slot] wire pairs (D250 layout); None
    # = outside the wire grammar, the pure-Python ctor must own it (D258:
    # str/upper casings and int() slot coercion stay native).
    if not isinstance(binding, dict):
        return None
    pairs = []
    for k, v in binding.items():
        if not isinstance(k, str):
            return None
        r = k.upper()
        if r not in ROLE_IDS:
            return None
        if isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= 255:
            return None
        pairs.append([r, v])
    return pairs


def _pq_karaka_snapshot(resp):
    # KarakaTable from an ok:true response (table_pairs snapshot);
    # strict validation, None on anything unexpected -> refuse.
    pairs = None if not isinstance(resp, dict) else resp.get("table_pairs")
    if not isinstance(pairs, list):
        return None
    m = {}
    for p in pairs:
        if (not isinstance(p, list) or len(p) != 2
                or not isinstance(p[0], str) or p[0] not in ROLE_IDS
                or not isinstance(p[1], int) or isinstance(p[1], bool)
                or not 0 <= p[1] <= 255):
            return None
        m[p[0]] = p[1]
    t = object.__new__(KarakaTable)
    t._m = m
    return t


class KarakaTable:
    """Role -> local-slot binding for one function frame."""

    __slots__ = ("_m",)

    def __init__(self, binding: Optional[Dict[str, int]] = None):
        pairs = [] if binding is None else _pq_karaka_pairs(binding)
        if pairs is not None:
            resp = _pq_karaka_wire("from_pairs", {"pairs": pairs})
            snap = None if resp is None else _pq_karaka_snapshot(resp)
            if snap is not None:
                self._m = snap._m
                return
        return KarakaTable._pq_init(self, binding)

    def _pq_init(self, binding: Optional[Dict[str, int]] = None):
        m: Dict[str, int] = {}
        if binding:
            for role, slot in dict(binding).items():
                r = str(role).upper()
                if r not in ROLE_IDS:
                    raise KarakaError("unknown role %r" % (role,))
                if not (0 <= int(slot) <= 255):
                    raise KarakaError("slot out of range: %r" % (slot,))
                if r in m:
                    raise KarakaError("duplicate role %r" % r)
                m[r] = int(slot)
        self._m = m

    def get(self, role: str) -> Optional[int]:
        t = _pq_karaka_wire("get", {"table_pairs": self._pq_pairs(),
                                    "role": role})
        if t is None:
            return self._pq_get(role, ())
        return t["slot"] if t.get("found") is True else None

    def _pq_get(self, role, _gate=()):
        return self._m.get(str(role).upper())

    def require(self, role: str) -> int:
        t = _pq_karaka_wire("require", {"table_pairs": self._pq_pairs(),
                                        "role": role})
        if t is None or not isinstance(t.get("slot"), int) \
                or isinstance(t["slot"], bool):
            return self._pq_require(role, ())
        return t["slot"]

    def _pq_require(self, role, _gate=()):
        s = self._m.get(str(role).upper())
        if s is None:
            raise KarakaError("required role missing: %s" % role)
        return s

    def bind(self, role: str, slot: int) -> "KarakaTable":
        t = _pq_karaka_wire("bind", {"table_pairs": self._pq_pairs(),
                                     "role": role, "slot": slot})
        if t is None:
            return self._pq_bind(role, slot, ())
        snap = _pq_karaka_snapshot(t)
        if snap is None:
            return self._pq_bind(role, slot, ())
        self._m = snap._m
        return self

    def _pq_bind(self, role, slot, _gate=()):
        r = str(role).upper()
        if r not in ROLE_IDS:
            raise KarakaError("unknown role %r" % role)
        if not (0 <= int(slot) <= 255):
            raise KarakaError("slot out of range: %r" % (slot,))
        if r in self._m:
            raise KarakaError("re-bind refused (frozen): %s" % r)
        self._m[r] = int(slot)
        return self

    def roles(self) -> List[str]:
        return sorted(self._m)

    def to_json(self) -> str:
        return json.dumps(self._m, sort_keys=True)

    @classmethod
    def from_json(cls, s: str) -> "KarakaTable":
        return cls(json.loads(s))

    def __repr__(self) -> str:
        return "KarakaTable(%s)" % self.to_json()

    def __eq__(self, o: object) -> bool:
        return isinstance(o, KarakaTable) and self._m == o._m

    def _pq_pairs(self):
        # Wire snapshot in insertion order (matches __init__ iteration).
        return [[r, s] for r, s in self._m.items()]


def parse_arguments(args: List[str], table: KarakaTable) -> Dict[str, Any]:
    """Map positional args onto roles: [AGT, PAT, KRN, DST, SRC, RCP] order.

    Raises KarakaError on arity mismatch — deterministic, no silent drops.
    """
    roles = list(ROLES)
    if len(args) > len(roles):
        raise KarakaError("too many args: %d > %d" % (len(args), len(roles)))
    out: Dict[str, Any] = {}
    for role, val in zip(roles, args):
        out[role] = val
    # any role with no arg stays absent — resolver treats absence as unknown
    return out


def merge_tables(base: KarakaTable, overrides: KarakaTable,
                 frozen_roles: Optional[List[str]] = None) -> KarakaTable:
    """Layer an override table over a base; frozen roles refuse change."""
    merged = KarakaTable(json.loads(base.to_json()))
    for role in overrides.roles():
        if frozen_roles and role in frozen_roles and merged.get(role) is not None:
            raise KarakaError("frozen role refuse override: %s" % role)
        merged.bind(role, overrides.require(role) if overrides.get(role) is not None
                    else overrides.get(role))
    return merged


def selftest() -> dict:
    checks = {}
    t = KarakaTable()
    t.bind("AGT", 0).bind("PAT", 1).bind("KRN", 2)
    checks["bind_ok"] = (t.get("agt") == 0 and t.require("PAT") == 1)
    try:
        t.bind("AGT", 9)
        checks["rebind_refused"] = False
    except KarakaError:
        checks["rebind_refused"] = True
    try:
        t.bind("BOGUS", 3)
        checks["bogus_role_refused"] = False
    except KarakaError:
        checks["bogus_role_refused"] = True
    # json round trip
    t2 = KarakaTable.from_json(t.to_json())
    checks["json_roundtrip"] = (t2 == t)
    # positional args -> roles
    m = parse_arguments(["alice", "bob", "wrench"], t)
    checks["args_mapped"] = (m == {"AGT": "alice", "PAT": "bob", "KRN": "wrench"})
    try:
        parse_arguments(["a"] * 7, t)
        checks["arity_refused"] = False
    except KarakaError:
        checks["arity_refused"] = True
    # merge with frozen
    ov = KarakaTable({"DST": 5})
    mg = merge_tables(t, ov, frozen_roles=["AGT"])
    checks["merge_ok"] = (mg.get("DST") == 5 and mg.get("AGT") == 0)
    try:
        merge_tables(t, KarakaTable({"AGT": 9}), frozen_roles=["AGT"])
        checks["frozen_refused"] = False
    except KarakaError:
        checks["frozen_refused"] = True
    # merge conflict on already-bound role errors (bind() refuses rebind)
    try:
        merge_tables(t, KarakaTable({"AGT": 3}), frozen_roles=None)
        checks["conflict_refused"] = False
    except KarakaError:
        checks["conflict_refused"] = True
    ok = all(checks.values())
    return {"ok": ok, "name": "karaka", "checks": checks,
            "roles": list(ROLES)}


if __name__ == "__main__":
    import sys
    r = selftest()
    print(json.dumps(r, default=str))
    sys.exit(0 if r["ok"] else 1)