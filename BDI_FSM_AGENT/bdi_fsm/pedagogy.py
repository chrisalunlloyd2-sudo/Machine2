"""PEDAGOGY — non-stop training, in the two languages the agent actually speaks.

Chris 2026-08-12: *"build the perfect training program for english and code for bdi agent"* and
*"it should [be] non stop pedagogy"*, alongside the reason it matters:
*"the entire point is to use the agent for code but the chat is just cool"*.

TWO MEMORIES, TWO METHODS — and they are not interchangeable
    ENGLISH is stochastic. Prose has no single correct continuation, so a Markov chain over a real
    corpus with entropy-stopping is exactly right: it measures how surprised it is and stops when
    the surprise says the thread has broken.

    CODE is not stochastic. There IS a correct continuation and a compiler that knows it. Running
    a Markov chain over code tokens produces text that looks like Python and is not, which is the
    worst of both — it costs a compile to discover, every time. So the code half is a TAPE OF AST
    TEMPLATES that advances on success (code_templates.CodeTape, Chris's own directive: *"the
    turing tape is used in a brute force ast coding method and advances on tape set every
    success... it's more of a template system really"*).

    Same organism, two substrates. Getting this wrong in either direction is the whole failure:
    template-matching prose is a phrasebook, and sampling code is a random number generator.

WHAT WAS MISSING
    `code_templates.py` is complete, tested and imported by NOBODY. `code_corpus.jsonl` and
    `code_tape.json` have never existed. The English half was in the same state until its corpus
    was built — `chat_corpus.jsonl` did not exist either, so the chain trained on 4.6 KB of its
    own log lines and answered in filenames. This module is the thing that feeds both and keeps
    feeding them.

THE REWARD SIGNAL IS REAL, NOT SYNTHETIC
    A template floats toward the tape head when it SUCCEEDS. The successes come from the agent's
    own sealed skill library — code the brute foundry mined, verified, and sealed. Nothing here
    invents a score. If the agent has never verified anything, the tape stays flat and says so,
    which is the honest state for an agent that has not yet done any work.

BOUNDED, BECAUSE THIS BOX IS A FOUR-CORE XEON WITH NO AVX
    Every pass is incremental and capped. Prose already ingested is skipped by content hash;
    templates already known are deduped by key. A tick that finds nothing new costs a directory
    walk, and a tick that finds plenty still stops at the cap and leaves the rest for next time.
"""
import hashlib
import json
import os
import time

from . import local_prose
from .code_templates import CodeTape, extract_templates

# Per-pass caps. The point of non-stop training is that it runs forever, not that any one pass
# does everything -- a trainer that pins four cores for an hour gets switched off, and then the
# training is neither non-stop nor anything else.
MAX_PROSE_PER_PASS = 120
MAX_FILES_PER_PASS = 250

DEFAULT_ROOTS = (r"C:\Viper\projects", r"C:\Viper\scripts")


def _state_path(state_dir, name):
    return os.path.join(state_dir, "corpus", name)


def _cursor(state_dir, name, total, step):
    """Where this pass starts, and where the next one will.

    Without this the walk restarts at the top every pass and stops at the cap, so the SAME first
    N files are read forever and the curriculum plateaus on pass two — the exact opposite of
    "always progressing, always advancing". The cursor rotates through the whole fleet and wraps,
    so given enough passes every file is seen, and no file is starved by alphabetical bad luck.

    Stored as a plain int; a corrupt or missing cursor simply starts at zero, because losing your
    place in a rotation costs one repeated pass and nothing else.
    """
    path = _state_path(state_dir, name)
    try:
        with open(path, encoding="utf-8") as f:
            start = int(json.load(f).get("at", 0))
    except (OSError, ValueError, json.JSONDecodeError, AttributeError):
        start = 0
    start = start % total if total else 0
    nxt = (start + step) % total if total else 0
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"at": nxt, "of": total,
                       "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}, f)
        os.replace(tmp, path)
    except OSError:
        pass
    return start


def _py_files(roots):
    """Every source file in the fleet, in a stable order so a cursor means something."""
    out = []
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames
                                 if d not in local_prose.SKIP_DIRS and not d.startswith("."))
            for fn in sorted(filenames):
                if fn.endswith(".py"):
                    out.append(os.path.join(dirpath, fn))
    return out


def _load_seen(path):
    """Content hashes already ingested. A set on disk, so a restart does not re-teach."""
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


# ── english ──────────────────────────────────────────────────────────────────
def train_english(trainer, roots=DEFAULT_ROOTS, limit=MAX_PROSE_PER_PASS):
    """Top up the prose corpus with documents not seen before.

    Dedup is on CONTENT, not path: the same docstring is vendored into several repos, and letting
    duplicates through would skew the transition table toward whatever happens to have been copied
    most rather than toward what is most often written.
    """
    seen_path = _state_path(trainer.state_dir, "prose_seen.json")
    seen = _load_seen(seen_path)
    added = chars = 0
    # Rotate like the code half does. harvest() walks in a stable order and stops at its cap, so
    # without a moving start it would re-read the same head of the fleet forever and report
    # "0 new" from the second pass onward while thousands of docstrings sat unread behind it.
    rotate = _cursor(trainer.state_dir, "prose_cursor.json",
                     max(len(_py_files(roots)), 1), MAX_FILES_PER_PASS)
    for source, text in local_prose.harvest(roots, limit_files=MAX_FILES_PER_PASS,
                                            skip_files=rotate):
        h = hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]
        if h in seen:
            continue
        got = trainer.append_corpus("local:" + source.replace("\\", "/"), text)
        if got:
            seen.add(h)
            added += 1
            chars += got
        if added >= limit:
            break
    if added:
        _save_seen(seen_path, seen)
    return {"new_docs": added, "new_chars": chars, "known": len(seen)}


# ── code ─────────────────────────────────────────────────────────────────────
def train_code(tape, state_dir, roots=DEFAULT_ROOTS, limit_files=MAX_FILES_PER_PASS):
    """Learn AST templates from the fleet's real Python.

    Extraction is by `ast`, so what lands on the tape is a real signature and a real body, not a
    regex's guess at one. A template that cannot be parsed is not a template — it is a string that
    happens to contain `def`.
    """
    files = _py_files(roots)
    if not files:
        return {"new_templates": 0, "files_read": 0, "of": 0}
    start = _cursor(state_dir, "code_cursor.json", len(files), limit_files)
    window = [files[(start + i) % len(files)] for i in range(min(limit_files, len(files)))]

    learned = unparseable = 0
    for path in window:
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                src = f.read()
        except OSError:
            continue
        try:
            tpl = extract_templates(src, "python", repo="", path=path)
        except (SyntaxError, ValueError):
            unparseable += 1
            continue      # an unparseable file costs that file, never the pass
        learned += tape.learn(tpl)
    return {"new_templates": learned, "files_read": len(window), "of": len(files),
            "from": start, "unparseable": unparseable}


def skill_library(state_dir):
    """The agent's skill library, constructed EXACTLY as agent.py constructs it.

    agent.py does `SkillLibrary(os.path.join(state_dir, "skills"))`, and SkillLibrary then appends
    "skills" again — so the real index sits at <state>/skills/skills_index.json, not the
    <state>/skills_index.json that the path plainly suggests. Two readers had already guessed the
    obvious path and found nothing, and both reported "no sealed skills yet" while five sealed
    skills sat on disk.

    Nobody should have to know that. Building it the same way the agent does means the paths
    cannot drift apart again, whatever the nesting happens to be.
    """
    from .skill_library import SkillLibrary
    return SkillLibrary(os.path.join(state_dir, "skills"))


def reward_from_skills(tape, state_dir):
    """Float templates the agent has actually PROVEN toward the tape head.

    The skill library holds code the brute foundry mined, ran and sealed. That is the only
    evidence in this system that a shape of code works, so it is the only thing allowed to move a
    template forward. Nothing here scores a template for looking plausible.

    Skills are keyed by a flattened path (`scripts_convert_lora_to_gguf_py`) while templates are
    keyed by the callable's own name (`set_vocab`), so the match is made through the skill's
    recorded `name`, falling back to the doc's leading identifier. An unmatched skill is counted,
    not silently dropped: a reward signal that quietly matches nothing looks identical to an agent
    that has never succeeded.
    """
    try:
        lib = skill_library(state_dir)
        idx = getattr(lib, "_index", {}) or {}
    except Exception as e:
        return {"rewarded": 0, "skills": 0, "why": "%s: %s" % (type(e).__name__, e)}
    if not idx:
        return {"rewarded": 0, "skills": 0, "why": "no sealed skills yet"}
    # A seal is credited ONCE. Without this the same five sealed skills were rewarded on every
    # pass, so `successes` counted passes rather than successes and grew forever -- a number that
    # cannot go down and does not correspond to anything is worse than no number. Keyed on the
    # skill's content hash where there is one, so RE-sealing changed code does count again.
    credited_path = _state_path(state_dir, "credited_skills.json")
    credited = _load_seen(credited_path)

    rewarded, unmatched, fresh = 0, [], 0
    for key, entry in idx.items():
        entry = entry if isinstance(entry, dict) else {}
        stamp = "%s@%s" % (key, entry.get("sha256") or entry.get("hash") or entry.get("sha") or "-")
        if stamp in credited:
            continue
        fresh += 1
        for cand in _callable_names(key, entry):
            if tape.reward(name=cand):
                rewarded += 1
                credited.add(stamp)
                break
        else:
            unmatched.append(str(key)[:40])
    if rewarded:
        _save_seen(credited_path, credited)
    return {"rewarded": rewarded, "new_seals": fresh, "skills": len(idx),
            "already_credited": len(credited), "unmatched": unmatched[:5]}


def _callable_names(key, entry):
    """Candidate template names for a sealed skill, best guess first.

    A skill's own `name` field is a FLATTENED PATH (`scripts_convert_lora_to_gguf_py`), because
    that is how the pool task was identified. Templates are keyed by the callable
    (`set_vocab`). The callable survives in the doc, which the foundry writes in one of two
    shapes:

        "set_vocab in scripts/convert_lora_to_gguf.py"
        "is_even(n) returns True when n is divisible by two"

    Both put the identifier first, so the leading token of the doc is the reliable link between
    what was proven and what is on the tape. The flattened name is still tried last — it costs
    nothing and covers a skill sealed under a bare function name.
    """
    out = []
    doc = str(entry.get("doc", "")).strip()
    if doc:
        head = doc.split(" in ")[0].split("(")[0].strip()
        if head and head.replace("_", "").isalnum():
            out.append(head)
    name = entry.get("name")
    if name:
        out.append(str(name))
    out.append(str(key))
    seen, uniq = set(), []
    for n in out:
        if n and n not in seen:
            seen.add(n)
            uniq.append(n)
    return uniq


# ── the program ──────────────────────────────────────────────────────────────
def train(state_dir, roots=DEFAULT_ROOTS):
    """One pass of the whole curriculum. Each half is isolated from the other.

    English and code fail for entirely unrelated reasons — a bad docstring cannot break AST
    extraction and an unparseable module cannot break prose ingestion — so one going wrong must
    never cost the other its turn.
    """
    from .webcrawl import CrawlTrainer

    out = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S")}

    try:
        trainer = CrawlTrainer(state_dir)
        out["english"] = train_english(trainer, roots)
        out["english"]["corpus"] = trainer.corpus_stats()
    except Exception as e:
        out["english"] = {"error": "%s: %s" % (type(e).__name__, e)}

    # THIRD HALF: the structures. English teaches the chain, code teaches the tape, and this
    # teaches the DAGs, the tree and the gates -- which were all measurably EMPTY until
    # 2026-08-14 (world model absent, toc_tok 56 bytes, tool_observer n_total 0). Isolated like
    # the others: a structure that cannot be filled must not cost the corpus its turn.
    # The symbolic registry: tokens, weights, and measured transitions. Cheap and additive --
    # populate() is idempotent on (type, key) and learn_transitions re-reads a tape that only ever
    # grows, so a pass costs a read and adds whatever is new.
    try:
        from . import symbolic
        out["symbolic"] = symbolic.build(state_dir)["stats"]
    except Exception as e:
        out["symbolic"] = {"error": "%s: %s" % (type(e).__name__, str(e)[:120])}

    try:
        from . import self_populate
        from .agent import BDIFSMAgent
        agent = BDIFSMAgent(state_dir=state_dir)
        out["structures"] = self_populate.populate(agent, state_dir)
        out["fullness"] = self_populate.fullness(agent, state_dir)
    except Exception as e:
        out["structures"] = {"error": "%s: %s" % (type(e).__name__, str(e)[:120])}

    try:
        tape = CodeTape(os.path.join(state_dir, "corpus", "code_tape.json"))
        out["code"] = train_code(tape, state_dir, roots)
        out["code"]["reward"] = reward_from_skills(tape, state_dir)
        tape.save()
        out["code"]["tape"] = tape.stats()
    except Exception as e:
        out["code"] = {"error": "%s: %s" % (type(e).__name__, e)}

    return out


def progress(state_dir):
    """Where the curriculum has got to. Pure reads."""
    from .webcrawl import CrawlTrainer
    out = {}
    try:
        out["english"] = CrawlTrainer(state_dir).corpus_stats()
    except Exception as e:
        out["english"] = {"error": str(e)[:120]}
    try:
        out["code"] = CodeTape(os.path.join(state_dir, "corpus", "code_tape.json")).stats()
    except Exception as e:
        out["code"] = {"error": str(e)[:120]}
    return out
