"""SELF-POPULATION — the structures fill themselves, from evidence, forever.

Chris 2026-08-14: *"we will need to invent some specific pedagogy routines for all to work"* and
*"I am positive we can get a self population SOP going like hero but better"*.

WHY THIS EXISTS
    Measured 2026-08-14, the agent's own state directory:

        fow.json          2 bytes      toc_tok.json    56 bytes
        nmct_vault/       empty        nmtd_db/        empty
        tok_memory/       empty        maslow/         empty
        world model       no file at all

    Every DAG, tree and state was empty. So `ask("how does the hive throttle work")` parsed the
    intent correctly and then returned fog {unknown: 36, visible: 0} — the mesh had nothing to
    route through, hit an impasse, and fell through to raw text search. The machinery was all
    built and none of it had ever been filled.

LIKE HERO, BUT BETTER
    hero_kernel is the model of always-on training: it never finishes, it yields under load, and
    a missed pass costs a tick rather than a fact. This borrows that shape and fixes the part that
    always frustrated it — hero reports a LOSS, a number that tells you it moved but not what it
    learned. Every routine here returns what it added, by name, so a pass that claims progress can
    be checked against the structure it claims to have filled.

THE SOP — five rules every routine obeys
    1. SOURCED.     Facts come from disk, git or the corpus. Nothing is invented to fill a gap;
                    an empty source yields an empty pass and says so.
    2. IDEMPOTENT.  Re-running with no new evidence adds nothing. This is what makes it safe to
                    run forever, and it is the property that stops "always training" from
                    becoming "always growing".
    3. BOUNDED.     A per-pass cap. The box is a four-core Xeon; a routine that can run for an
                    hour gets switched off, and then it is not always-on either.
    4. MEASURED.    Each returns before/after counts. A routine that cannot say how full its
                    structure is cannot tell you it is working.
    5. REVERSIBLE.  Add-only. Nothing here deletes; pruning is a separate, deliberate act.
"""
import hashlib
import json
import os
import re
import time

VIPER = r"C:\Viper"
PROJECTS = os.path.join(VIPER, "projects")
SCRIPTS = os.path.join(VIPER, "scripts")

# Per-pass caps. Deliberately small: ten passes of ten is the same coverage as one pass of a
# hundred, and only one of those can be interrupted safely.
MAX_ENTITIES = 40
MAX_TOC_NODES = 60
MAX_VERB_DOCS = 120

SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", "target",
             ".pytest_cache", "build", "dist", ".mypy_cache", "backups"}


_STATE = {"dir": None}


def _state_path(state_dir, name):
    return os.path.join(state_dir, "corpus", name)


def _load_seen(path):
    try:
        with open(path, encoding="utf-8") as f:
            return set(json.load(f))
    except (OSError, json.JSONDecodeError):
        return set()


def _save_seen(path, seen):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f)
    os.replace(tmp, path)


def _tower(agent, state_dir):
    """The TOC-TOK tower. Not an agent attribute -- built on the state file it owns."""
    t = getattr(agent, "toc_tok", None) or getattr(agent, "toc", None)
    if t is not None:
        return t
    if not state_dir:
        return None
    try:
        from .toc_tok import TocTokTower
        return TocTokTower(os.path.join(state_dir, "toc_tok.json"))
    except Exception:
        return None


def _flags(agent, state_dir):
    """The verb lexicon. Also not an agent attribute."""
    v = getattr(agent, "verb_flags", None)
    if v is not None:
        return v
    try:
        from .verb_flags import VerbFlags
        return VerbFlags(state_dir)
    except Exception:
        return None


# ── 1. WORLD MODEL: entity DAGs for the fleet ────────────────────────────────
def populate_world(agent, limit=MAX_ENTITIES):
    """Observe each repo as an entity, with its real facts and relations.

    Source is the filesystem and git — a repo's language mix, module count and branch are facts
    about it that nobody has to assert. Relations link a repo to the languages it is written in,
    so "what is written in Java" is a graph walk rather than a text search.

    Idempotent by construction: world_model.observe() merges facts into an existing DAG and only
    adds nodes for values it has not seen, so a second pass over an unchanged fleet adds nothing.
    """
    world = getattr(agent, "world", None)
    if world is None:
        return {"error": "agent has no world model"}
    before = len(getattr(world, "entities", {}) or {})
    seen = 0
    for name in sorted(os.listdir(PROJECTS)):
        if seen >= limit:
            break
        root = os.path.join(PROJECTS, name)
        if not os.path.isdir(os.path.join(root, ".git")):
            continue
        facts, langs = _repo_facts(root)
        if not facts:
            continue
        relations = [("repo:%s" % name, "written_in", "lang:%s" % l) for l in langs]
        try:
            world.observe("repo", name, facts, relations)
            seen += 1
        except Exception:
            continue
    try:
        world.save()
    except Exception:
        pass
    after = len(getattr(world, "entities", {}) or {})
    return {"observed": seen, "entities_before": before, "entities_after": after,
            "new": after - before}


def _repo_facts(root):
    """What is true about this repo, counted rather than guessed."""
    exts, modules, docs = {}, 0, 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if not ext:
                continue
            exts[ext] = exts.get(ext, 0) + 1
            if ext == ".py":
                modules += 1
            elif ext == ".md":
                docs += 1
        if sum(exts.values()) > 4000:      # bounded: a vendored tree is not more information
            break
    if not exts:
        return {}, []
    lang_of = {".py": "python", ".java": "java", ".js": "javascript", ".ts": "typescript",
               ".rs": "rust", ".go": "go", ".c": "c", ".cpp": "cpp", ".cs": "csharp",
               ".ps1": "powershell", ".sh": "shell", ".md": "markdown"}
    langs = sorted({lang_of[e] for e in exts if e in lang_of} - {"markdown"})
    top = sorted(exts.items(), key=lambda kv: -kv[1])[:4]
    return ({"modules": modules, "docs": docs, "languages": ",".join(langs) or "none",
             "file_types": ",".join("%s:%d" % (e, n) for e, n in top)}, langs)


# ── 2. TOC-TOK: the tree, placed on the dominating lattice ───────────────────
def populate_toc(agent, limit=MAX_TOC_NODES):
    """Put the fleet on the hex board, authority on lattice cells.

    The seeding law is not mine and is not negotiable: cells where (q + 3r) % 7 == 0 form a
    perfect dominating set, so a node placed there is within one hop of everything around it.
    Authoritative nodes (repos) take lattice cells; everything else fills the gaps. Placing rather
    than sampling is the whole difference between a board that dominates and one that mostly does
    — proven in toc_seeder, re-derived here for nobody.

    Idempotent on NAME: a node already on the board is skipped, so the board converges instead of
    growing a duplicate every pass. That mattered: toc_tok's hexes were once hand-typed into
    collisions.
    """
    toc = _tower(agent, _STATE.get("dir"))
    if toc is None:
        return {"error": "toc_tok unavailable"}
    try:
        existing = {n.get("name") for n in toc.tree()}
    except Exception as e:
        return {"error": "%s: %s" % (type(e).__name__, e)}
    before = len(existing)

    repos = [n for n in sorted(os.listdir(PROJECTS))
             if os.path.isdir(os.path.join(PROJECTS, n, ".git"))]
    placed, filled = 0, 0
    for q, r in _lattice_cells(radius=8):
        if placed + filled >= limit or not repos:
            break
        name = repos.pop(0)
        if name in existing:
            continue
        try:
            toc.add(name, q, r, kind="repo", parent="/fleet",
                    meta={"placed": "lattice", "law": "(q+3r)%7==0"})
            placed += 1
            existing.add(name)
        except Exception:
            continue
    after = len(toc.tree())
    return {"placed_on_lattice": placed, "nodes_before": before, "nodes_after": after,
            "law": "(q+3r)%7==0"}


def _lattice_cells(radius=8):
    """Dominating-set cells, nearest first. (q + 3r) mod 7 == 0."""
    out = []
    for q in range(-radius, radius + 1):
        for r in range(max(-radius, -q - radius), min(radius, -q + radius) + 1):
            if (q + 3 * r) % 7 == 0:
                out.append((q, r))
    out.sort(key=lambda c: (abs(c[0]) + abs(c[1]) + abs(-c[0] - c[1])) / 2)
    return out


# ── 3. VERBS: the intent lexicon, learned from what the fleet writes ─────────
def populate_verbs(agent, state_dir, limit=MAX_VERB_DOCS):
    """Teach the intent parser the words this fleet actually gives orders in.

    parse_intent returns confidence 0.0 for any sentence with no recognised verb, and the mesh
    reads 0.0 as "do not act, search instead". That is correct behaviour for a question and wrong
    for an instruction the fleet uses constantly but the builtin lexicon never heard of.

    Source is the corpus: imperative openings of real docstrings and task lines. Learned verbs are
    persisted to verb_flags.json, so this is cumulative across passes without re-reading.
    """
    vf = _flags(agent, state_dir)
    if vf is None:
        return {"error": "verb_flags unavailable"}
    before = vf.stats().get("learned", 0)

    # SOURCE: task titles, not prose.
    #
    # Docstring prose is documentation ABOUT instructions, so its sentence openings are nouns and
    # adjectives — "Available memory is...", "Doctrine: ...", "Each routine...". Learning from it
    # produced 786 "verbs" from 120 documents, including 'err', 'midstate' and 'about', every one
    # of which would enter the intent lexicon and give parse_intent false confidence on a sentence
    # containing no instruction at all. That is strictly worse than the honest 0.0 it returns now.
    #
    # A task title is an instruction BY CONSTRUCTION. projects.db holds 91 of them and their heads
    # are exactly what you would hope: run 14, build 12, add 9, install, create, make, implement,
    # connect, wire. Right source, no filter needed.
    read, learned = 0, []
    for title in _task_titles(limit):
        read += 1
        head = title.strip().split()
        if len(head) < 2:
            continue
        w = head[0].lower().strip("*`:.,()[]")
        if len(w) < 3 or not w.isalpha():
            continue
        hint = vf.action_hint(title) or "save_code"
        learned += vf.learn(w, action_name=hint)
    after = vf.stats().get("learned", 0)
    return {"titles_read": read, "verbs_before": before, "verbs_after": after,
            "new": after - before, "sample": sorted(set(learned))[:10]}


def _task_titles(limit):
    """Instructions the fleet has written for itself. Imperative by construction."""
    import sqlite3
    db = os.path.join(VIPER, "databases", "projects", "projects.db")
    try:
        con = sqlite3.connect("file:%s?mode=ro" % db, uri=True, timeout=5)
        rows = [r[0] for r in con.execute(
            "SELECT title FROM tasks WHERE title IS NOT NULL LIMIT ?", (limit,))]
        con.close()
        return rows
    except Exception:
        return []


def _corpus_lines(state_dir, limit):
    """QUESTIONS from the corpus — the chat class, unambiguously.

    The first attempt used any docstring sentence, on the theory that prose is descriptive and
    task titles are imperative. That is false for THIS corpus: docstrings here are full of
    technical imperatives ("Run the tests before committing", "Wire the crawler to..."), so
    labelling them chat taught the gate that tool words are chat words. Measured: "run the tests"
    fell from 1.129 bans to 0.124, and "wire the crawler to playwright" — a real task title —
    scored -0.785, i.e. confidently chat.

    A question is chat with no ambiguity at all: it asks rather than instructs. Narrower source,
    far fewer examples, and every one of them correctly labelled — which is the only property
    that matters, because a training set that is wrong makes the gate worse than not training it.
    """
    path = os.path.join(state_dir, "corpus", "chat_corpus.jsonl")
    out = []
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                if len(out) >= limit:
                    break
                try:
                    t = json.loads(line).get("text", "")
                except json.JSONDecodeError:
                    continue
                for sent in re.split(r"(?<=[.!?])\s+", t):
                    sent = sent.strip()
                    if not (20 < len(sent) < 240):
                        continue
                    low = sent.lower()
                    if sent.endswith("?") or low.startswith(
                            ("what ", "why ", "how ", "when ", "who ", "which ",
                             "is there", "does ", "do you", "can you")):
                        out.append(sent)
                        break
    except OSError:
        pass
    return out[:limit]


# ── 4. TOOL OBSERVER: the ban gate, taught what it is judging ───────────────
def populate_observer(agent, state_dir, limit=120):
    """Give the log-odds gate labelled examples, so it stops running on priors alone.

    Chris 2026-08-14: *"check the bans, it should be getting hits on even just the grammar,
    something isn't right"*. The grammar WAS hitting — "run the tests" scores 1.129 bans, "what
    is entropy" scores -0.261, and those are the right signs. What was wrong sat one level down:

        stats() -> {n_tool: 0, n_chat: 0, n_total: 0, vocab: 0}

    record() had never been called. The observer had a learned-vocabulary channel and nothing had
    ever been put in it, so every score came from the fixed prior plus the built-in rules. It could
    not get better at this fleet's language, only at English in general.

    The labels are free and honest: a task title is an instruction, a docstring sentence is not.
    No hand-labelling, no guessing — the two corpora ARE the two classes.
    """
    obs = getattr(agent, "tool_observer", None)
    if obs is None:
        return {"error": "agent has no tool_observer"}
    before = obs.stats()

    # Teach each example ONCE. Without this, every pass re-recorded the same 211 examples and
    # n_total climbed forever — 211, 422, 633 — a count that can only go up and corresponds to
    # nothing. Worse than a wrong number, it would also skew the class priors purely by how many
    # times the trainer happened to run.
    seen_path = _state_path(state_dir, "observer_taught.json")
    seen = _load_seen(seen_path)
    n_tool = n_chat = 0
    for text, is_tool in ([(t, True) for t in _task_titles(limit)] +
                          [(c, False) for c in _corpus_lines(state_dir, limit)]):
        h = hashlib.sha1(("%d:%s" % (is_tool, text)).encode("utf-8")).hexdigest()[:16]
        if h in seen:
            continue
        try:
            obs.record(text, is_tool)
        except Exception:
            break
        seen.add(h)
        if is_tool:
            n_tool += 1
        else:
            n_chat += 1
    if n_tool or n_chat:
        _save_seen(seen_path, seen)
    after = obs.stats()
    return {"taught_tool": n_tool, "taught_chat": n_chat,
            "before": before, "after": after}


# ── the SOP ──────────────────────────────────────────────────────────────────
def populate(agent, state_dir):
    """One pass of every routine. Each isolated: one empty source never stops the others."""
    _STATE["dir"] = state_dir
    out = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
    for name, fn in (("world", lambda: populate_world(agent)),
                     ("toc", lambda: populate_toc(agent)),
                     ("verbs", lambda: populate_verbs(agent, state_dir)),
                     ("observer", lambda: populate_observer(agent, state_dir))):
        try:
            out[name] = fn()
        except Exception as e:
            out[name] = {"error": "%s: %s" % (type(e).__name__, str(e)[:120])}
    return out


def fullness(agent, state_dir):
    """How full is each structure? The measure rule — pure reads, no writes."""
    out = {}
    world = getattr(agent, "world", None)
    out["world_entities"] = len(getattr(world, "entities", {}) or {}) if world else None
    toc = _tower(agent, state_dir)
    try:
        out["toc_nodes"] = len(toc.tree()) if toc else None
    except Exception:
        out["toc_nodes"] = None
    vf = _flags(agent, state_dir)
    try:
        out["verbs_learned"] = vf.stats().get("learned") if vf else None
    except Exception:
        out["verbs_learned"] = None
    corpus = os.path.join(state_dir, "corpus", "chat_corpus.jsonl")
    out["corpus_bytes"] = os.path.getsize(corpus) if os.path.exists(corpus) else 0
    return out

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
