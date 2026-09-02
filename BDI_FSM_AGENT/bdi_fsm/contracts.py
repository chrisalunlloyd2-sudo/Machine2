"""CONTRACTS — point BDI, the SLM and Aegis at todos, and let them take work under lease.

Chris 2026-08-15: *"we are getting VERY close to the point where we can point bdi and an slm and
aegis at todos and give contracts. they are all there, the parts are there — we need to unify with
the fow."*

He is right that the parts existed. All four of them, none of them touching:

    todos       todo_crawl -> 19 real open items (93 raw, once duplicates,
                non-tasks and already-done work were removed)
    board       toc_tok -> 31 nodes placed on the dominating lattice, (q+3r)%7==0
    lease       fow.FOW -> claim / TTL / release, and fow.json was `{}`. Two bytes.
                Nothing had ever claimed anything.
    workers     BDI (deterministic), the SLM (Moe), Aegis (manager)

WHAT A CONTRACT IS
    A todo, placed on a hex, that exactly one party may hold at a time, for a bounded period.
    That is all. The lease is what makes it a contract rather than an assignment: the holder does
    not have to succeed, and does not have to report — if it stops, the TTL expires and the work
    returns to the pool. Nothing can be lost by a worker dying, and nothing can be done twice.

    Chris's own doctrine, applied: nothing lives forever, nothing runs for free.

WHY LEASES RATHER THAN A QUEUE
    A queue needs a broker that is up. A lease needs only a shared file and a clock, so three
    processes that never speak to each other cannot collide — which is exactly this fleet, where
    the hive, sovereign_daemons and the GUI bridge are separate processes that restart
    independently. It is also why the TTL is the safety property and not an optimisation: a
    crashed holder is indistinguishable from a slow one, and after the TTL both are treated the
    same way, correctly.

CAPABILITY, NOT PREFERENCE
    Who may take what is decided by the SHAPE of the work, not by a score. A deterministic agent
    should not be handed "explain the architecture", and a language model should not be handed
    "run the test suite" — and no amount of evidence about how well either did last time changes
    that. Bans rank options WITHIN a capability; they never grant one.
"""
import contextlib
import functools
import json
import os
import re
import time

# ONE WRITER AT A TIME. The lease says who may WORK a contract; nothing said who
# may WRITE THE FILE. Every mutator here is a whole-file read-modify-write, and
# this board has at least three independent writers (miner_daemon, bdi_cell and
# the audit pass). Two of them overlapping means the second one's write is built
# on a copy read before the first one's, so the first's change is silently
# reverted. Observed 2026-08-30: an audit reopened ten falsely-closed contracts
# and one came back "done" moments later with its ORIGINAL done_at timestamp --
# not re-closed, restored, by a writer holding a stale copy.
#
# On a board where offer() is idempotent on id, a lost write is not a cosmetic
# race: a contract wrongly restored to "done" can never be re-offered, so the
# work is gone.
#
# An OS byte-range lock, not a lock FILE, and deliberately:
#   * the kernel drops it when the process dies, so a crashed holder cannot
#     wedge the board -- there is no stale-lock case to get wrong, which is the
#     part hand-rolled lock files always get wrong;
#   * nothing is ever deleted to release it. A lock file has to be unlinked,
#     and "only add, never delete" is the standing rule here.
try:                                    # Windows
    import msvcrt
except ImportError:                     # pragma: no cover - POSIX
    msvcrt = None
try:                                    # POSIX
    import fcntl
except ImportError:                     # pragma: no cover - Windows
    fcntl = None

# Lease length. Long enough that a real mine (~6s) or a house-LLM call (300-470s measured on this
# box) finishes inside it; short enough that a dead holder does not park work for an afternoon.
DEFAULT_TTL_S = 900

# Attempts before a contract is PARKED. The pool learned this the hard way: a task that could not
# be mined came back as top priority forever, and one unmineable item ate the whole duty cycle at
# ~6s a pass. A contract is no different -- and unlike a pool task it is visible to three parties,
# so an unparked failure starves all of them.
#
# Parked is not deleted and not done. It keeps its attempts and its last reason, stays on the
# board, and can be released deliberately. Nothing lives forever; nothing runs for free.
MAX_ATTEMPTS = 3

# What each party is ALLOWED to take. Matched on the todo's text, deterministically.
#
# The BDI agent is the default because it is the only one that verifies what it produces. Work
# only leaves it when the shape of the task says it must.
CAPABILITY = {
    # Language work: explaining, describing, summarising, naming. A deterministic miner has
    # nothing to offer here and would park after three attempts.
    # THE GROUP MUST CLOSE WITH \b. It opened with one and closed inside the
    # alternation (why\b), so every OTHER alternative matched as a prefix:
    # "write[- ]?up" fired on "Write upsert_auditor.py", sending a
    # code-generation task to the language party. "document" would match
    # "documentation", "comment" would match "commentary".
    # Third sighting of this one bug: the :8765 keyword matcher ("hi" inside
    # "this") and talon.extract_directive were the first two.
    "slm": re.compile(r"\b(explain|describe|summari[sz]e|document|write[- ]?up|draft|rename|"
                      r"comment|readme|blurb|why)\b", re.I),   # )\b, not why\b) -- see below
    # Decisions, priorities, and anything touching the outside world. Aegis holds these because
    # they need judgement or authorisation, not because she is better at them.
    "aegis": re.compile(r"\b(decide|prioriti[sz]e|approve|review|plan|schedule|choose|"
                        r"publish|deploy|onboard|auth|oauth|credential|migrate)\b", re.I),
}


# Where a contract stops asking for work and starts describing the artifact.
# "Write alert_router.py in C:\Viper\scripts. Its job: Decide what is worth
# interrupting for." Everything after "Its job:" describes what the FINISHED
# MODULE will do. It is not a description of the work being commissioned.
_PURPOSE_CLAUSE = re.compile(r"\b(?:its?\s+job|purpose|role|it\s+should)\s*[:\-]", re.I)


def work_clause(text):
    """The part of a contract that states the work, with any purpose clause removed.

    Routing read the WHOLE string, so a contract was assigned to whichever party
    the module's subject matter sounded like. Measured 2026-08-31 -- all 9 open
    contracts on the board were misrouted, every one of them "Write <name>.py":

        Write note_writer.py     ... job: One note per repo: README     -> slm
        Write epoch_manager.py   ... open the next: why                 -> slm
        Write incident_writer.py ... job: Write up what broke           -> slm
        Write chunk_splitter.py  ... document                           -> slm
        Write alert_router.py    ... job: Decide what is worth ...      -> aegis
        Write patch_critic.py    ... job: Review a generated patch      -> aegis
        Write recall_ranker.py   ... job: Decide which prior turns ...  -> aegis

    Writing a Python module is code generation -- party "bdi", the default -- no
    matter what the module goes on to do. miner_daemon is the only consumer of
    take("bdi"), so every one of those tasks was invisible to the only thing that
    could do them. The board reported 9 open contracts and the miner reported no
    work, both truthfully, for 14 hours; that is when Chris's update emails
    stopped, because the miner emits per mined block and mined none.
    """
    t = str(text or "")
    m = _PURPOSE_CLAUSE.search(t)
    return t[:m.start()] if m else t


def _revive_rec(rec, reason, now):
    rec["state"] = "open"
    rec["parked_reason"] = None
    rec["attempts_since_revive"] = 0
    rec["revived_at"] = now
    rec["history"] = (rec.get("history") or [])[-9:] + [{
        "ts": now, "party": "audit", "ok": None,
        "evidence": "revived: %s" % str(reason)[:220]}]
    return rec


def route(text):
    """Which party may take this todo. Deterministic, and BDI unless the shape says otherwise.

    Judged on work_clause(), not the raw text -- see above for why.
    """
    t = work_clause(text)
    if CAPABILITY["aegis"].search(t):
        return "aegis"
    if CAPABILITY["slm"].search(t):
        return "slm"
    return "bdi"


def _hex_for(key, radius=8):
    """A stable cell for a todo. Filler cells only — authority keeps the lattice.

    toc_tok places repos on cells where (q + 3r) % 7 == 0, which is the perfect dominating set.
    A todo is not authority, so it must NOT take a lattice cell: doing so would displace a repo
    off the dominating set and quietly break the property the whole board rests on. The same rule
    toc_seeder already follows — authority on the lattice, everything else in the gaps.
    """
    h = 0
    for ch in str(key):
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    for _ in range(64):                       # bounded search for a non-lattice cell
        q = (h % (2 * radius + 1)) - radius
        r = ((h >> 8) % (2 * radius + 1)) - radius
        if (q + 3 * r) % 7 != 0:
            return q, r
        h = (h * 1103515245 + 12345) & 0xFFFFFFFF
    return radius, radius                     # last resort, still off-lattice for odd radii


def _locked(fn):
    """Run one whole read-modify-write with the board held.

    On the METHOD, not inside _read/_write: the race is the GAP between the two,
    so a lock that only covers the write closes nothing. Reentrant, because
    offer_backlog() calls offer() and a second acquire from the same object must
    not deadlock.
    """
    @functools.wraps(fn)
    def wrapper(self, *a, **kw):
        with self._hold():
            return fn(self, *a, **kw)
    return wrapper


class Contracts:
    """Todos on hexes, taken under lease by whichever party may do them."""

    def __init__(self, state_dir, ttl_seconds=DEFAULT_TTL_S):
        from .fow import FOW
        self.state_dir = state_dir
        self.path = os.path.join(state_dir, "contracts.json")
        self.fow = FOW(os.path.join(state_dir, "fow.json"), ttl_seconds=ttl_seconds)
        self.ttl = ttl_seconds

    # ---- the register ------------------------------------------------------
    @contextlib.contextmanager
    def _hold(self, timeout=20.0):
        """Exclusive hold on the board for the duration of the block.

        Reentrant via a depth count: offer_backlog() -> offer() must not
        deadlock on itself.

        The lock is taken on a SIDECAR file, never on contracts.json itself.
        _write() finishes with os.replace(), which swaps the inode out from
        under any handle held on the real path -- so a lock held there would be
        guarding a file that no longer exists at that name. The sidecar is
        created once and then lives forever; it holds no data and is never
        deleted.

        If the platform cannot lock at all, SAY SO and continue unguarded. A
        board that refuses to serve is worse than one with a narrow race, and a
        silent unguarded write is worse than both.
        """
        if getattr(self, "_depth", 0):
            self._depth += 1
            try:
                yield
            finally:
                self._depth -= 1
            return

        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        fh = open(self.path + ".lock", "a+b")
        locked = False
        try:
            deadline = time.time() + timeout
            while True:
                try:
                    fh.seek(0)
                    if msvcrt is not None:
                        msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                    elif fcntl is not None:
                        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    else:
                        print("[contracts] no lock primitive on this platform -- "
                              "writing UNGUARDED")
                        break
                    locked = True
                    break
                except OSError:
                    # Held by someone else. Windows LK_NBLCK and POSIX LOCK_NB
                    # both raise rather than wait, which is what lets us bound
                    # the wait ourselves instead of blocking forever.
                    if time.time() >= deadline:
                        print("[contracts] board busy for %.0fs -- proceeding "
                              "UNGUARDED rather than dropping the work" % timeout)
                        break
                    time.sleep(0.05)
            self._depth = 1
            yield
        finally:
            self._depth = 0
            if locked:
                try:
                    fh.seek(0)
                    if msvcrt is not None:
                        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
                    elif fcntl is not None:
                        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
                except OSError as e:
                    print("[contracts] lock release failed (%s) -- the kernel "
                          "drops it when this process exits" % str(e)[:60])
            fh.close()

    def _read(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}

    def _write(self, d):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        # PER-PROCESS TEMP. Under _hold() one writer runs at a time and a shared
        # ".tmp" would be safe -- but any writer that skipped the lock, or an
        # older copy of this file still running elsewhere, would land on the same
        # temp path and one os.replace() would publish the other's half-written
        # board. The pid costs nothing and removes the shared name entirely.
        tmp = "%s.%d.tmp" % (self.path, os.getpid())
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=1, sort_keys=True)
        os.replace(tmp, self.path)

    @_locked
    def offer(self, todo_id, text, source="todo_crawl", repo=None):
        """Put a todo on the board. Idempotent on todo_id — re-offering never duplicates."""
        d = self._read()
        if todo_id in d:
            return {"offered": False, "why": "already on the board", "id": todo_id}
        q, r = _hex_for(todo_id)
        rec = {"id": todo_id, "text": str(text)[:400], "source": source, "repo": repo,
               "hex": [q, r], "for": route(text), "state": "open",
               "offered_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "attempts": 0, "history": []}
        d[todo_id] = rec
        self._write(d)
        return {"offered": True, **rec}

    def offer_backlog(self, limit=25):
        """Offer the real backlog. Sourced from todo_crawl, which is now honest about what a task is."""
        try:
            import sys
            if r"C:\Viper\scripts" not in sys.path:
                sys.path.insert(0, r"C:\Viper\scripts")
            import todo_crawl
            items = todo_crawl.crawl()
        except Exception as e:
            return {"offered": 0, "why": "%s: %s" % (type(e).__name__, str(e)[:100])}
        n = 0
        for it in items[:limit]:
            tid = str(it.get("id") or "")[:16]
            if tid and self.offer(tid, it.get("text", ""), repo=it.get("repo"))["offered"]:
                n += 1
        return {"offered": n, "considered": len(items)}

    # ---- taking and delivering --------------------------------------------
    def available(self, party):
        """Open contracts this party may take, and nobody currently holds."""
        out = []
        for rec in self._read().values():
            if rec.get("for") != party or rec.get("state") in ("done", "parked"):
                continue
            if self.fow.held(rec["id"]):
                continue                      # somebody is genuinely working on it
            # `held` in the register with NO live lease means the holder died or stalled. The
            # lease is the source of truth about possession; the register only records what was
            # last believed. Without this the work stayed marked held forever and nobody could
            # take it again -- the lease expired into nothing.
            out.append(rec)
        return out

    @_locked
    def take(self, party):
        """Claim one contract. Returns None when there is nothing for this party.

        The lease is taken BEFORE the register is written, so a crash between the two leaves a
        claim that expires rather than a register entry nobody holds. Failing toward "the work
        comes back" is the only safe direction here.
        """
        for rec in self.available(party):
            if not self.fow.claim(rec["id"], owner=party):
                continue                      # someone took it between listing and claiming
            d = self._read()
            r = d.get(rec["id"], rec)
            r["state"] = "held"
            r["holder"] = party
            r["taken_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            r["attempts"] = int(r.get("attempts", 0)) + 1
            # Two counters, because they answer different questions. `attempts`
            # is the lifetime record and is never reset -- it is history.
            # `attempts_since_revive` is what the park rule reads, so a contract
            # revived for a REASON gets a genuine fresh run at MAX_ATTEMPTS
            # instead of parking again on its next failure.
            r["attempts_since_revive"] = int(r.get("attempts_since_revive", 0)) + 1
            d[r["id"]] = r
            self._write(d)
            return r
        return None

    @_locked
    def revive(self, reason, todo_ids=None, only_if=None):
        """Un-park contracts because the reason they failed has CHANGED. Never deletes.

        A park is a statement about the past: "three attempts, none good enough".
        It is not a verdict that the work is impossible, and nothing on this box
        could ever take it back -- so on 2026-08-31 all 93 contracts were parked
        and the miner had no work at all. A board that can only ever lose
        contracts empties itself.

        Reviving is deliberately NOT automatic and NOT free: it takes a reason,
        writes that reason into the contract's history, and resets only
        `attempts_since_revive`. The lifetime `attempts` count is untouched,
        because how many times something has been tried is evidence.

        `only_if(rec) -> bool` filters, so a caller can revive just the contracts
        the change actually affects rather than the whole board.
        """
        d = self._read()
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        revived = []
        for tid, rec in d.items():
            if rec.get("state") != "parked":
                continue
            if todo_ids is not None and tid not in todo_ids:
                continue
            if only_if is not None:
                try:
                    if not only_if(rec):
                        continue
                except Exception:
                    continue
            d[tid] = _revive_rec(rec, reason, now)
            revived.append(tid)
        if revived:
            self._write(d)
        return {"revived": len(revived), "ids": revived, "reason": reason}

    @_locked
    def deliver(self, todo_id, party, ok=True, evidence=""):
        """Finish a contract. Requires EVIDENCE on success.

        Refusing to close without evidence is the same rule todo_crawl.tick_off already enforces:
        a tick with nothing behind it retires real work permanently, and is a lie the board then
        keeps telling. A failure needs no evidence -- only a reason.
        """
        if ok and not str(evidence).strip():
            return {"delivered": False, "why": "refused: success needs evidence"}
        d = self._read()
        rec = d.get(todo_id)
        if not rec:
            return {"delivered": False, "why": "no such contract"}
        rel = self.fow.release_reason(todo_id, owner=party)
        if not rel["released"]:
            # The lease expired and possibly moved on. The work may well have been done, but this
            # party is no longer the holder and must not close someone else's contract.
            return {"delivered": False, "why": "lease lost: %s" % rel["why"], **rel}
        rec["state"] = "done" if ok else "open"
        rec["history"] = (rec.get("history") or [])[-9:] + [{
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "party": party,
            "ok": bool(ok), "evidence": str(evidence)[:300]}]
        if ok:
            rec["done_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            rec["done_by"] = party
        else:
            rec.pop("holder", None)
            since = int(rec.get("attempts_since_revive",
                                 rec.get("attempts", 0)))
            if since >= MAX_ATTEMPTS:
                rec["state"] = "parked"
                rec["parked_reason"] = "failed %d attempts; last: %s" % (
                    since, str(evidence)[:160])
        d[todo_id] = rec
        self._write(d)
        return {"delivered": True, "state": rec["state"], "attempts": rec["attempts"]}

    @_locked
    def reconcile(self, is_satisfied):
        """Close every contract whose DELIVERABLE now exists, whoever produced it.

        The missing last step. block_promoter stages a mined module and stops,
        deliberately -- "install() ... is a human act". But nothing then told the
        BOARD that the act had happened, so a contract sat parked for ever after
        its module was installed, and the work looked undone while the file sat
        on disk. The pipeline could finish and still report failure.

        This is not a weakening of "DONE MEANS THE MODULE EXISTS" -- it is that
        rule, applied in the one direction nobody had implemented. The predicate
        decides; the board only records. Keeping the filesystem knowledge OUT of
        here is the point: this class knows about leases and states, not about
        .py files or C:\Viper\scripts.

        `is_satisfied(rec)` returns (bool, evidence). Evidence is required on a
        close, exactly as deliver() requires it.

        HELD contracts are skipped on purpose. A worker holding a lease may be
        mid-write, and closing underneath it would race the thing this class
        exists to prevent. It will be picked up on the next pass once the lease
        ends -- there is no hurry about a file that already exists.
        """
        d = self._read()
        closed = []
        for todo_id, rec in d.items():
            if rec.get("state") in ("done", "held"):
                continue
            try:
                ok, why = is_satisfied(rec)
            except Exception as e:
                # Never let one bad predicate call abandon the whole sweep, and
                # never swallow it either -- a reconciler that goes quiet is
                # indistinguishable from one with nothing to do.
                print("[contracts] reconcile predicate failed for %s (%s: %s)"
                      % (todo_id, type(e).__name__, str(e)[:100]))
                continue
            if not ok or not str(why).strip():
                continue
            rec["state"] = "done"
            rec["done_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            rec["done_by"] = "reconcile"
            rec.pop("holder", None)
            rec.pop("parked_reason", None)      # it is no longer parked, it is done
            rec["history"] = (rec.get("history") or [])[-9:] + [{
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "party": "reconcile",
                "ok": True, "evidence": str(why)[:300]}]
            closed.append(todo_id)
        if closed:
            self._write(d)
        return closed

    @_locked
    def abandon(self, todo_id, party, why=""):
        """Give a contract back without claiming failure. Honest and cheap."""
        rel = self.fow.release_reason(todo_id, owner=party)
        d = self._read()
        rec = d.get(todo_id)
        if rec and rel["released"]:
            rec["state"] = "open"
            rec.pop("holder", None)
            rec["history"] = (rec.get("history") or [])[-9:] + [{
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "party": party,
                "ok": None, "evidence": "abandoned: %s" % str(why)[:200]}]
            d[todo_id] = rec
            self._write(d)
        return rel

    # ---- reporting ---------------------------------------------------------
    def board(self):
        """The whole board: who may take what, who holds what, what is finished."""
        d = self._read()
        by_party, by_state = {}, {}
        held = []
        for rec in d.values():
            by_party[rec.get("for")] = by_party.get(rec.get("for"), 0) + 1
            by_state[rec.get("state")] = by_state.get(rec.get("state"), 0) + 1
            h = self.fow.held(rec["id"])
            if h:
                held.append({"id": rec["id"], "owner": h.get("owner"),
                             "text": rec.get("text", "")[:60]})
        return {"contracts": len(d), "by_party": by_party, "by_state": by_state,
                "currently_held": held, "ttl_s": self.ttl}

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
