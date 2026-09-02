"""SYMBOLIC REGISTRY — everything the system knows, as numbered symbols and state transitions.

Chris 2026-08-14/15:
    *"start the symbolic registries with all system nodes, file topologies, githubs and locations,
    assign weights and tokenise where possible"*
    *"ban actions must equate beginning state to end state"*
    *"the system should be able to answer in states, nodes, places, people, things, but all
    numerically associated and ready to be queried by bans"*
    *"logic of states as well — if we apply x pressure to system a we get xa. that's the most
    important."*

THE ONE IDEA
    A symbol is a number. A transition is a triple: (begin, pressure, end). And the value of a
    pressure is not asserted, it is MEASURED — in bans, Turing's weight of evidence:

        bans(begin --x--> end) = log10( P(end | begin, x) / P(end | begin) )

    That is the whole design. It says: knowing that pressure x was applied, how much more do we
    believe we land in `end` than we did before? Zero bans means x told us nothing. One ban means
    ten times the odds. Negative means x makes that outcome LESS likely, which is information too
    and is normally thrown away.

WHY BANS RATHER THAN A PROBABILITY
    Bans add. Evidence from three independent pressures is the sum of three numbers, not a product
    of three fractions that underflows and stops being legible. Turing chose base ten for the same
    reason a person can hold "2.3 bans" in their head and cannot hold 1/199.5. The system already
    speaks this language -- ban.py, the tool observer's log-odds, the certainty gate -- and this
    puts state transitions in the same currency so they can be compared with everything else.

APPLY X TO A AND YOU GET XA
    `apply(state, pressure)` returns the most likely end state and the bans of evidence behind it.
    Composition is real, not notation: the end state's key IS derived from what was applied, so a
    chain of pressures leaves a readable trail rather than an opaque final label.

WHERE THE NUMBERS COME FROM
    Nothing here is invented. Symbols come from the fleet's own inventory -- hive cells, services,
    ports, repos, remotes, paths, agents, databases. Transitions come from the 12,658 rows already
    in tool_tape, which has recorded `prev_tool -> tool` on every successful call since it was
    wired. The evidence was being collected before anything could read it.

WEIGHTS
    A symbol's weight is its measured share of activity, not an opinion about its importance --
    successful invocations for a tool, runs for a cell, files for a repo. Normalised to [0,1]
    within its type, so weights are comparable inside a type and never across one: a repo's 0.8
    and a cell's 0.8 mean different things and must not be added.
"""
import json
import math
import os
import sqlite3
import time

VIPER = r"C:\Viper"
PROJECTS = os.path.join(VIPER, "projects")
TELEMETRY = os.path.join(VIPER, "databases", "telemetry", "telemetry.db")
PROJECTS_DB = os.path.join(VIPER, "databases", "projects", "projects.db")

# Chris's five kinds, plus the two the transition algebra needs.
TYPES = ("state", "node", "place", "person", "thing", "pressure", "repo")

REGISTRY = "symbolic_registry.json"

# An edge seen twice is not worthless and it is not trustworthy. It is UNCERTAIN.
#
# Chris 2026-08-15: *"fuzzy sets for the edges — not everything is always perfect"*. A crisp
# threshold (n >= 3, else nothing) throws away every partial observation and, worse, makes the
# edge at n=2 and the edge at n=200 look identical the moment they both pass. Real evidence does
# not arrive in a step function.
#
# So an edge has a MEMBERSHIP DEGREE in the fuzzy set "reliable", n / (n + k), and its ban score
# is discounted by it. This is standard shrinkage and it is also just honest: a likelihood ratio
# from two samples is a rumour, from two hundred it is a fact, and everything between is a degree.
#
#   n=1  -> 0.25    n=3  -> 0.50    n=10 -> 0.77    n=100 -> 0.97
#
# Nothing is discarded and nothing is over-trusted. The raw ban is always reported alongside, so
# the discount can never hide what was actually measured.
EDGE_K = 3.0

# Below this the edge is reported but not used for a prediction: at zero observations there is no
# ratio to compute at all. This is the only crisp line left, and it is crisp because it is the
# boundary between "some evidence" and "none".
MIN_OBS = 1


def membership(n):
    """Degree to which an edge belongs to the fuzzy set 'reliable'. n/(n+k), in [0,1)."""
    return n / (n + EDGE_K) if n > 0 else 0.0


# ── grounding: measured is not the same as wanted ────────────────────────────
#
# Chris 2026-08-15: *"a solution to 'my file isn't loading' can't be 'delete file'. It's a
# solution, but not the one we want."*
#
# That is the failure mode of every optimiser given a target and no grounding, and this registry
# is exactly such an optimiser. `evidence_for(broken, resolved)` ranks purely on bans, and
# deleting the file scores BRILLIANTLY — the problem really does go away, the end state really is
# reached, and the measurement is not wrong. It answers the question it was asked.
#
# Bans measure whether a pressure REACHES a state. They say nothing about whether you wanted to
# arrive that way, because that information was never in the transition counts. Thousands of years
# of lexical evolution carry the unstated half; a vector does not.
#
# So the measure is paired with a constraint, and the constraint is not a score. A destructive
# pressure is never *recommended* as a route, at any ban value — it cannot be out-argued by
# evidence, because the objection was never evidential. It is still RECORDED: what happened
# happened, and hiding it would corrupt the baseline every other edge is measured against.
#
# This is the fleet's existing add-only doctrine ("culling = archive, never destroy") expressed
# where a planner can actually trip over it.
DESTRUCTIVE_HINTS = (
    "delete", "remove", "rm_", "drop", "purge", "wipe", "destroy", "truncate",
    "kill", "reset_hard", "force_push", "revert", "clear", "erase", "format",
    "uninstall", "prune", "reap",
)


# ── the third class: pressures whose effect the transition cannot see ────────
#
# Chris 2026-08-15: *"like 'please mmap this' — do mem options trigger instant test thoughts?"*
#
# Yes, and for a reason that is structurally different from destructive. A destructive pressure is
# REFUSED. A resource pressure is allowed — it just cannot be judged by the same instrument.
#
# Bans are computed from (begin, pressure, end). That works whenever the consequence IS the
# transition. It fails completely for anything that changes a resource envelope, because the
# consequence arrives minutes later and lands somewhere else entirely:
#
#     --no-mmap succeeds instantly and scores a clean transition. Twenty minutes later the box is
#     swapping, an unrelated cell blows its deadline, and the tape records THAT as the failure.
#     The pressure that caused it has a perfect record.
#
# This is the same shape as the orphaned llama-server incident — five processes holding 8.7 GB,
# and the symptom was house calls taking 302s. Nothing in the transition data connects those.
#
# So a resource pressure demands an IMMEDIATE MEASUREMENT rather than a score: take the number
# before, apply, take it after. That is the only way its effect ever enters the record at all.
RESOURCE_HINTS = (
    "mmap", "num_thread", "n_thread", "num_gpu", "n_gpu", "num_ctx", "n_ctx",
    "batch", "ubatch", "rlimit", "memory", "mem_", "cache", "keep_alive",
    "max_loaded", "num_parallel", "swap", "affinity", "priority", "nice",
)


def needs_immediate_test(pressure, facts=None):
    """Does this pressure change a resource envelope rather than a state?

    If so its effect is invisible to the transition it appears in, and the registry must measure
    it directly instead of pretending the ban score means anything.
    """
    if facts and "resource" in facts:
        return bool(facts["resource"])
    p = str(pressure).lower()
    return any(h in p for h in RESOURCE_HINTS)


def is_destructive(pressure, facts=None):
    """Does this pressure remove something? Name first, declared fact wins.

    Name matching is a heuristic and heuristics are wrong sometimes, so an explicit
    facts["destructive"] always overrides it in either direction. A false positive costs a
    recommendation that has to be asked for by name; a false negative costs the file.
    """
    if facts and "destructive" in facts:
        return bool(facts["destructive"])
    p = str(pressure).lower()
    return any(h in p for h in DESTRUCTIVE_HINTS)


def _bans(p_with, p_without):
    """Weight of evidence in bans (base 10). The unit the whole registry is denominated in."""
    if p_with <= 0 or p_without <= 0:
        return 0.0
    return math.log10(p_with / p_without)


class SymbolicRegistry:
    """Numbered symbols and measured transitions between them."""

    def __init__(self, state_dir):
        self.path = os.path.join(state_dir, REGISTRY)
        self.symbols = {}       # key -> {token, type, key, weight, facts}
        self.by_token = {}
        self.transitions = {}   # "begin|pressure" -> {end: count}
        self._next = 1
        self.load()

    # ---- persistence -------------------------------------------------------
    def load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, json.JSONDecodeError):
            return
        self.symbols = d.get("symbols", {})
        self.transitions = d.get("transitions", {})
        self._next = int(d.get("next_token", 1))
        self.by_token = {int(s["token"]): s for s in self.symbols.values()}

    def save(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"symbols": self.symbols, "transitions": self.transitions,
                       "next_token": self._next,
                       "saved": time.strftime("%Y-%m-%dT%H:%M:%S")},
                      f, indent=1, sort_keys=True)
        os.replace(tmp, self.path)

    # ---- symbols -----------------------------------------------------------
    def token(self, type_, key, weight=0.0, **facts):
        """Register a symbol and return its number. Idempotent on (type, key).

        The token is a stable integer, assigned once and never reused, so a saved transition table
        keeps meaning across restarts. Facts merge rather than replace -- a later observation adds
        to what is known about a symbol instead of overwriting it.
        """
        k = "%s:%s" % (type_, key)
        s = self.symbols.get(k)
        if s is None:
            s = {"token": self._next, "type": type_, "key": key,
                 "weight": float(weight), "facts": {}}
            self._next += 1
            self.symbols[k] = s
            self.by_token[s["token"]] = s
        if weight:
            s["weight"] = float(weight)
        if facts:
            s["facts"].update({str(a): b for a, b in facts.items()})
        return s["token"]

    def lookup(self, type_=None, key=None, token=None):
        if token is not None:
            return self.by_token.get(int(token))
        return self.symbols.get("%s:%s" % (type_, key))

    def of_type(self, type_):
        return sorted((s for s in self.symbols.values() if s["type"] == type_),
                      key=lambda s: -s["weight"])

    # ---- transitions: begin --pressure--> end ------------------------------
    def observe(self, begin, pressure, end):
        """Record one observed transition. This is the evidence bans are computed from."""
        k = "%s|%s" % (begin, pressure)
        row = self.transitions.setdefault(k, {})
        row[end] = row.get(end, 0) + 1

    def _baseline(self, begin):
        """P(end | begin), pooled over every pressure. The 'without' half of the ratio."""
        pooled = {}
        for k, row in self.transitions.items():
            if not k.startswith(begin + "|"):
                continue
            for end, n in row.items():
                pooled[end] = pooled.get(end, 0) + n
        total = sum(pooled.values())
        return pooled, total

    def apply(self, state, pressure):
        """APPLY X TO A. Returns the likeliest end state and the bans of evidence for it.

        The ban answers the question the count cannot: a pressure that leads to `end` 80% of the
        time is worthless if `end` happens 80% of the time anyway. Bans measure the DIFFERENCE the
        pressure makes, which is the only thing worth calling a prediction.
        """
        row = self.transitions.get("%s|%s" % (state, pressure), {})
        obs = sum(row.values())
        if obs < MIN_OBS:
            return {"ok": False, "why": "no observations of this pressure from this state",
                    "begin": state, "pressure": pressure, "observations": obs,
                    "support": 0.0}
        pooled, pooled_total = self._baseline(state)
        ranked = []
        for end, n in row.items():
            p_with = n / obs
            p_without = (pooled.get(end, 0) / pooled_total) if pooled_total else 0.0
            raw = _bans(p_with, p_without)
            mu = membership(n)          # fuzzy degree of THIS edge, on its own count
            ranked.append({"end": end, "n": n, "p": round(p_with, 4),
                           "bans_raw": round(raw, 4), "support": round(mu, 3),
                           "bans": round(raw * mu, 4)})
        # Rank on the DISCOUNTED ban: a 2-observation edge with a huge raw score must not outrank
        # a 200-observation edge with a solid one. That inversion is exactly what a crisp
        # threshold permitted, because past the line everything counted the same.
        ranked.sort(key=lambda r: (-r["bans"], -r["n"]))
        best = ranked[0]
        out = {"ok": True, "begin": state, "pressure": pressure,
               "end": best["end"], "bans": best["bans"], "bans_raw": best["bans_raw"],
               "support": best["support"], "p": best["p"], "observations": obs,
               # xa: the composed label. A chain of pressures stays readable.
               "composed": "%s.%s" % (state, pressure),
               "alternatives": ranked[1:4]}
        sym = self.lookup("pressure", pressure) or {}
        if needs_immediate_test(pressure, sym.get("facts")):
            # Say it on the result, not in a log. A caller that reads `bans` and acts is the whole
            # risk here, and a flag it has to step over is the only warning that reliably arrives.
            out["verify_now"] = True
            out["why_verify"] = ("resource pressure: its effect is not in this transition. "
                                 "Measure RSS/latency/free-RAM before and after, or the ban "
                                 "score is measuring the wrong thing.")
        return out

    def chain(self, state, pressures, conditions=None):
        """a + b + c = d, under conditions w. Apply a sequence and SUM the evidence.

        Chris 2026-08-15: *"we won't need telemetry if the system adds — it will know a+b+c=d
        under w conditions... this is what happens when you tether lexical logic to symbolism:
        it's compressed to small steps and we have WAY more playroom."*

        This is the payoff of denominating everything in bans, and the reason the ban was the
        right unit rather than a probability. Bans ADD. Evidence for a three-step path is the sum
        of three numbers; with probabilities it would be a product of three fractions, which
        underflows and stops being readable at about four steps.

        So the registry never has to observe a path to predict it. It stores small steps -- 548 of
        them -- and composes. The reachable set is combinatorial in the steps rather than limited
        to the paths that happened to be walked, which is the compression: far fewer facts, far
        more answers.

        A step with no evidence STOPS the chain and says where. A composed answer that quietly
        guessed its third step is worse than a short one that admits where the road ended.
        """
        conditions = conditions or {}
        cur, steps, total = state, [], 0.0
        weakest = 1.0
        for p in pressures:
            r = self.apply(cur, p)
            if not r.get("ok"):
                steps.append({"pressure": p, "from": cur, "ok": False, "why": r.get("why")})
                return {"ok": False, "begin": state, "end": cur, "bans": round(total, 4),
                        "steps": steps, "stopped_at": p, "conditions": conditions,
                        "support": round(weakest, 3),
                        "composed": ".".join([state] + [s["pressure"] for s in steps if s.get("ok")])}
            total += r["bans"]
            # A path is exactly as trustworthy as its shakiest edge -- the fuzzy MIN, not the
            # average. Averaging lets two solid steps hide one that was seen once, and the whole
            # point of carrying membership is that the weak link stays visible at the end.
            weakest = min(weakest, r["support"])
            steps.append({"pressure": p, "from": cur, "to": r["end"], "bans": r["bans"],
                          "bans_raw": r["bans_raw"], "support": r["support"],
                          "n": r["observations"], "ok": True})
            cur = r["end"]
        return {"ok": True, "begin": state, "end": cur, "bans": round(total, 4),
                "support": round(weakest, 3), "steps": steps, "conditions": conditions,
                # The composed label: xa, then xab, then xabc. The trail stays readable.
                "composed": ".".join([state] + list(pressures))}

    def evidence_for(self, state, end, allow_destructive=False):
        """Which pressures carry the most evidence for reaching `end` from `state`?

        The inverse question, and the one planning actually asks: not "what does x do" but "what
        should I apply to get there".
        """
        pooled, pooled_total = self._baseline(state)
        if not pooled_total:
            return []
        p_without = pooled.get(end, 0) / pooled_total
        out, withheld = [], []
        for k, row in self.transitions.items():
            if not k.startswith(state + "|"):
                continue
            obs = sum(row.values())
            if obs < MIN_OBS or end not in row:
                continue
            pressure = k.split("|", 1)[1]
            mu = membership(row[end])
            raw = _bans(row[end] / obs, p_without)
            rec = {"pressure": pressure, "n": row[end], "observations": obs,
                   "bans_raw": round(raw, 4), "support": round(mu, 3),
                   "bans": round(raw * mu, 4)}
            sym = self.lookup("pressure", pressure) or {}
            if not allow_destructive and is_destructive(pressure, sym.get("facts")):
                # Not ranked, not scored against the others, and NOT hidden. "delete the file"
                # solves "the file will not load" and must never be the answer that comes back
                # from asking how to fix it — but a person who asks for it by name should still
                # be told it exists and that it was withheld.
                rec["withheld"] = "destructive: reaches the state by removing the thing"
                withheld.append(rec)
                continue
            out.append(rec)
        out.sort(key=lambda r: -r["bans"])
        if withheld:
            out.append({"withheld_count": len(withheld), "withheld": withheld,
                        "note": "destructive routes are recorded but never recommended; "
                                "pass allow_destructive=True to see them ranked"})
        return out

    # ---- reporting ---------------------------------------------------------
    def stats(self):
        by_type = {}
        for s in self.symbols.values():
            by_type[s["type"]] = by_type.get(s["type"], 0) + 1
        return {"symbols": len(self.symbols), "by_type": by_type,
                "transition_keys": len(self.transitions),
                "observations": sum(sum(r.values()) for r in self.transitions.values()),
                "next_token": self._next}


# ── population: the fleet, as symbols ────────────────────────────────────────
def _norm(values):
    """Normalise weights to [0,1] WITHIN a type. Never across one -- a repo's 0.8 and a cell's
    0.8 are different quantities and adding them would be meaningless."""
    hi = max(values) if values else 0
    return (lambda v: round(v / hi, 4)) if hi else (lambda v: 0.0)


def populate(reg):
    """Register the fleet. Sourced entirely from telemetry, projects.db and the filesystem."""
    added = {t: 0 for t in TYPES}

    # NODES + PRESSURES + STATES, from telemetry
    try:
        con = sqlite3.connect("file:%s?mode=ro" % TELEMETRY, uri=True, timeout=10)
        cells = list(con.execute(
            "SELECT cell, tier, runs, fails, consecutive_fails FROM hive_cells"))
        w = _norm([c[2] or 0 for c in cells])
        for cell, tier, runs, fails, cfails in cells:
            reg.token("node", cell, weight=w(runs or 0), tier=tier, runs=runs, fails=fails)
            added["node"] += 1
        tools = list(con.execute("SELECT tool, ok, failed FROM tool_tape_stats"))
        wt = _norm([t[1] or 0 for t in tools])
        for tool, ok, failed in tools:
            total = (ok or 0) + (failed or 0)
            reg.token("pressure", tool, weight=wt(ok or 0), ok=ok, failed=failed,
                      rate=round((ok or 0) / total, 4) if total else 0.0)
            added["pressure"] += 1
        # STATES: the health a node can be in. Small, closed, and what the FSM actually switches on.
        for st in ("healthy", "failing", "slow", "never_ran", "deferred"):
            reg.token("state", st, weight=1.0)
            added["state"] += 1
        con.close()
    except Exception:
        pass

    # REPOS + PLACES, from disk and git config
    try:
        repos = [n for n in sorted(os.listdir(PROJECTS))
                 if os.path.isdir(os.path.join(PROJECTS, n, ".git"))]
        sizes = {}
        for n in repos:
            root = os.path.join(PROJECTS, n)
            c = 0
            for dp, dn, fn in os.walk(root):
                dn[:] = [d for d in dn if d not in (".git", "__pycache__", "node_modules")]
                c += len(fn)
                if c > 4000:
                    break
            sizes[n] = c
        wr = _norm(list(sizes.values()))
        for n in repos:
            remote = _remote(os.path.join(PROJECTS, n))
            reg.token("repo", n, weight=wr(sizes[n]), files=sizes[n], remote=remote or "none")
            added["repo"] += 1
            reg.token("place", os.path.join(PROJECTS, n), weight=wr(sizes[n]), kind="directory")
            added["place"] += 1
            if remote:
                reg.token("place", remote, weight=wr(sizes[n]), kind="github")
                added["place"] += 1
    except Exception:
        pass

    # PLACES: listening ports are locations too
    for name, port in (("ollama", 11434), ("house_llm", 8765),
                       ("sims1337web", 8137), ("bdi_webui", 8600)):
        reg.token("place", "127.0.0.1:%d" % port, weight=1.0, kind="port", service=name)
        added["place"] += 1

    # PEOPLE and the agents that act like them
    for who, role in (("chris", "operator"), ("aegis", "manager"), ("moe", "expert"),
                      ("nyx", "queue"), ("bdi-fsm-agent", "executor"), ("kai", "peer")):
        reg.token("person", who, weight=1.0, role=role)
        added["person"] += 1

    # THINGS: the databases, which are what most actions actually touch
    dbroot = os.path.join(VIPER, "databases")
    try:
        found = []
        for dp, dn, fn in os.walk(dbroot):
            for f in fn:
                if f.endswith(".db"):
                    found.append((f, os.path.getsize(os.path.join(dp, f))))
        wd = _norm([s for _, s in found])
        for f, size in found:
            reg.token("thing", f, weight=wd(size), kind="database", bytes=size)
            added["thing"] += 1
    except Exception:
        pass

    return added


def _remote(root):
    cfg = os.path.join(root, ".git", "config")
    try:
        with open(cfg, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line.startswith("url = "):
                    return line[6:].strip()
    except OSError:
        pass
    return None


def learn_transitions(reg, limit=20000):
    """Learn (begin --pressure--> end) from the tool tape.

    tool_tape has recorded prev_tool and tool on every successful call since it was wired -- 12,658
    rows before anything read them. A call is a PRESSURE applied while the system was in the state
    the previous tool left it in, so the tape is already a transition log; it just was not being
    read as one.

    The end state is the tool's own outcome, which is what the next pressure will be applied to.
    """
    try:
        con = sqlite3.connect("file:%s?mode=ro" % TELEMETRY, uri=True, timeout=10)
        cols = {r[1] for r in con.execute("PRAGMA table_info(tool_tape)")}
        prev_col = "prev_tool" if "prev_tool" in cols else None
        if not prev_col:
            con.close()
            return {"learned": 0, "why": "tool_tape has no prev_tool column"}
        rows = list(con.execute(
            "SELECT %s, tool FROM tool_tape WHERE %s IS NOT NULL LIMIT ?" % (prev_col, prev_col),
            (limit,)))
        con.close()
    except Exception as e:
        return {"learned": 0, "why": "%s: %s" % (type(e).__name__, e)}
    for prev, tool in rows:
        if not prev or not tool:
            continue
        # begin = the node the previous pressure left us at; pressure = this tool; end = this node.
        reg.observe(str(prev), str(tool), str(tool))
    return {"learned": len(rows), "transition_keys": len(reg.transitions)}


def build(state_dir):
    """One pass: register the fleet, learn its transitions, persist. Idempotent."""
    reg = SymbolicRegistry(state_dir)
    added = populate(reg)
    learned = learn_transitions(reg)
    reg.save()
    return {"added": added, "learned": learned, "stats": reg.stats()}

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
