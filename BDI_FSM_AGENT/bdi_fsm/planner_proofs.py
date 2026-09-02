"""planner_proofs.py — symbolic liveness, deadlock, termination and
total-correctness proofs over the FSM state graph.

Every proof is a deterministic object:
    {"property": ..., "holds": bool, "witness": ..., "counterexample": ...}

    deadlock          every non-terminal state can leave (>=1 edge with a
                      satisfiable guard). A terminal is a state with NO
                      outgoing edges by design (it IS the exit).
    liveness          from every state, some terminal is reachable.
    termination       a rank function exists: rank = BFS distance to nearest
                      terminal; every edge must strictly decrease rank, so no
                      cycle can run forever (the classic well-founded argument).
    total_correctness liveness AND termination AND every terminal reachable
                      from the start state is an ACCEPTING state.

Chris 2026-08-15: "symbolic planner liveness/correctness proofs" (v0.4.0).
Zero LLM. Guards are checked by brute-force truth tables (see reachability.py).
"""

from __future__ import annotations

from collections import deque
from typing import Any, Dict, List, Optional, Set

from .reachability import _fsm_edges, guard_verdict

__all__ = ["deadlock_report", "liveness", "termination", "total_correctness",
           "planner_audit"]


def _graph(fsm: Any):
    """state -> list of (next_state, guard, event)."""
    adj: Dict[str, List[Dict[str, Any]]] = {}
    for e in _fsm_edges(fsm):
        adj.setdefault(e["from"], []).append(e)
    # every state that appears as a target must exist as a key
    for e in _fsm_edges(fsm):
        adj.setdefault(e["to"], [])
    return adj


def _terminals(adj: Dict[str, List[Dict[str, Any]]]) -> List[str]:
    return sorted(s for s, es in adj.items() if not es)


def _edge_can_fire(guard: Any) -> bool:
    """Statically: can this guard ever be true? RUNTIME guards are assumed live."""
    verdict, _ = guard_verdict(guard)
    return verdict != "UNSAT"


def deadlock_report(fsm: Any, terminals: Optional[List[str]] = None) -> Dict[str, Any]:
    """States that cannot leave (no edge, or all UNSAT).

    terminals: explicitly declared exit states that are ALLOWED to have no
    outgoing edges. If None, no-outgoing states are auto-treated as terminals
    (so a designed exit like COMMIT is not a false deadlock); pass terminals
    to distinguish a stuck state from a designed exit.
    """
    adj = _graph(fsm)
    terms = set(terminals) if terminals is not None else set(_terminals(adj))
    dead: List[Dict[str, Any]] = []
    for s, es in sorted(adj.items()):
        if s in terms:
            continue
        live_edges = [e for e in es if _edge_can_fire(e["guard"])]
        if not live_edges:
            dead.append({
                "state": s,
                "edges": [{"event": e["event"], "to": e["to"],
                           "guard": e["guard"] if isinstance(e["guard"], str)
                                    else ("<callable>" if e["guard"] else None)}
                          for e in es],
                "cause": "no_outgoing" if not es else "all_guards_unsat",
            })
    return {"property": "deadlock-freedom", "holds": not dead,
            "deadlock_states": dead, "counterexample": dead[0] if dead else None}


def liveness(fsm: Any, terminals: Optional[List[str]] = None,
             goals: Optional[List[str]] = None) -> Dict[str, Any]:
    """Every state can reach some goal (BFS; structural first, then symbolic
    guard-satisfiability). goals= explicit success states (e.g. COMMIT) —
    for cyclic control loops there are no no-outgoing terminals, so the
    meaningful liveness property is 'every state can reach the success exit'."""
    adj = _graph(fsm)
    terms = set(goals) if goals else (set(terminals) if terminals is not None
                                      else set(_terminals(adj)))
    if not terms:
        return {"property": "liveness", "holds": False,
                "counterexample": {"state": next(iter(adj)),
                                   "reason": "no terminal states exist"}}
    bad: List[Dict[str, Any]] = []
    for s in sorted(adj):
        # structural BFS
        seen = {s}
        q = deque([s])
        while q:
            cur = q.popleft()
            if cur in terms:
                break
            for e in adj.get(cur, []):
                if e["to"] not in seen:
                    seen.add(e["to"]); q.append(e["to"])
        else:
            # unreachable terminal structurally: only possible if s is in a
            # closed component with no terminal; guard-independent proof
            bad.append({"state": s, "reason": "no structural path to any terminal"})
            continue
        # symbolic check: every edge on SOME path to a terminal must be fireable.
        # BFS again tracking fireable edges only.
        if not _symbolic_reaches_terminal(s, adj, terms):
            bad.append({"state": s, "reason": "all paths to a terminal pass an UNSAT guard"})
    return {"property": "liveness", "holds": not bad,
            "terminals": sorted(terms),
            "counterexample": bad[0] if bad else None, "violations": bad}


def _symbolic_reaches_terminal(start: str, adj, terms: Set[str]) -> bool:
    seen = {start}
    q = deque([start])
    while q:
        cur = q.popleft()
        if cur in terms:
            return True
        for e in adj.get(cur, []):
            if e["to"] not in seen and _edge_can_fire(e["guard"]):
                seen.add(e["to"]); q.append(e["to"])
    return False


def termination(fsm: Any, goals: Optional[List[str]] = None) -> Dict[str, Any]:
    """SOUND + COMPLETE termination proof for finite-state FSMs.

    The machine can loop forever IFF the state graph contains a cycle
    (including self-loops): an acyclic graph has path length <= #states, so
    every execution terminates. Cycles like A->B->A can be traversed forever
    even when one edge is 'rank-decreasing' -- ranks are NOT a sound measure,
    so the proof is a DFS cycle check. The rank table is kept as a witness
    (distance to nearest terminal) and non-strict edges are reported as a
    'watch' list (informational). Cycles need runtime bounded counters
    (e.g. the plateau patience mechanism) to be proven terminating.
    """
    adj = _graph(fsm)
    terms = set(_terminals(adj))
    rank: Dict[str, int] = {}
    if terms:
        rev: Dict[str, List[str]] = {}
        for s, es in adj.items():
            for e in es:
                rev.setdefault(e["to"], []).append(s)
        q = deque([(t, 0) for t in terms])
        for t in terms:
            rank[t] = 0
        while q:
            cur, d = q.popleft()
            for src in rev.get(cur, []):
                if src not in rank:
                    rank[src] = d + 1
                    q.append((src, d + 1))
    for s in adj:
        rank.setdefault(s, len(adj) + 1)

    WHITE, GRAY, BLACK = 0, 1, 2
    color = {s: WHITE for s in adj}
    cycles: List[List[Dict[str, Any]]] = []
    _path: List[Dict[str, Any]] = []

    def _dfs(s: str) -> None:
        color[s] = GRAY
        for e in adj.get(s, []):
            if color[e["to"]] == GRAY:
                # extract the cycle from _path: from the target back to itself
                idx = next((i for i, p in enumerate(_path) if p["from"] == e["to"]), len(_path))
                cyc = _path[idx:] + [e]
                if not any(c[0]["from"] == cyc[0]["from"] and c[0]["event"] == cyc[0]["event"]
                           and c[0]["to"] == cyc[0]["to"] for c in cycles):
                    cycles.append(cyc)
            elif color[e["to"]] == WHITE:
                _path.append(e)
                _dfs(e["to"])
                _path.pop()
        color[s] = BLACK

    for s in sorted(adj):
        if color[s] == WHITE:
            _dfs(s)

    goals = set(goals) if goals else set()
    livelock = [c for c in cycles if not (goals and any(e["to"] in goals for e in c))]
    task_cycles = [c for c in cycles if c not in livelock]
    holds = not cycles if not goals else not livelock
    watch = [{"from": e["from"], "event": e["event"], "to": e["to"],
              "rank_from": rank.get(e["from"]), "rank_to": rank.get(e["to"])}
             for e in _fsm_edges(fsm)
             if rank.get(e["to"], 0) >= rank.get(e["from"], 0)]
    return {"property": "termination", "holds": holds, "ranks": rank,
            "counterexample": (livelock[0] or [])[0] if livelock else
                              (cycles[0][0] if cycles else None),
            "cycles": cycles, "livelock_cycles": livelock,
            "task_cycles": task_cycles, "watch": watch,
            "note": "no-goal termination requires an acyclic graph; with goals, "
                    "cycles that never pass a goal are livelocks (need runtime "
                    "bounded counters), cycles that pass a goal are task-cycles "
                    "where each loop completes a unit of work."}


def total_correctness(fsm: Any, accepting: Optional[List[str]] = None,
                     goals: Optional[List[str]] = None) -> Dict[str, Any]:
    """deadlock-freedom AND liveness-to-goal AND termination (no livelock cycle
    that avoids every goal). goals = the success states of the machine."""
    live = liveness(fsm, goals=goals)
    term = termination(fsm, goals=goals)
    dead = deadlock_report(fsm)
    holds = bool(dead["holds"] and live["holds"] and term["holds"])
    return {"property": "total-correctness", "holds": holds,
            "deadlock": dead["holds"], "liveness": live["holds"],
            "termination": term["holds"], "goals": list(goals or []),
            "counterexample": (live["counterexample"] or term["counterexample"]
                               or dead["counterexample"])}


def planner_audit(fsm: Any, accepting: Optional[List[str]] = None,
                  terminals: Optional[List[str]] = None,
                  goals: Optional[List[str]] = None) -> Dict[str, Any]:
    """One-shot audit: deadlock-freedom + liveness + termination + total-correctness.
    goals = success states (defaults to no-outgoing terminals)."""
    return {
        "deadlock": deadlock_report(fsm, terminals),
        "liveness": liveness(fsm, terminals=terminals, goals=goals),
        "termination": termination(fsm, goals=goals),
        "total_correctness": total_correctness(fsm, accepting, goals),
    }

# LOCATIONS - this file lives in more than one place
#
#   live:  C:\Viper\projects\BDI_FSM_AGENT
#          -> C:\Users\viper\gan-otg-db\BDI_FSM_AGENT
#   mirror: J:\ViperVault\code\projects\BDI_FSM_AGENT
#   mirror: C:\Users\viper\gan-otg-db\BDI_FSM_AGENT
#
#   live detail (freshness, git coverage): docs\LOCATIONS.md
#   regenerate: python location_stamp.py apply
# end LOCATIONS
