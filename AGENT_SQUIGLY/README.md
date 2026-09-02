# agent-squigly

**Squigly lists everything, says what it is for, and knows what uses what.**

Chris, 2026-08-17:

> the main reason for innaction is the lack of context and system data... squigly just lists all
> files and folders, blocks all windows program folders and has a refreshed master list with the
> topological linking and usage so if we need one file it is linked to the program that uses it
> like dependencies, so any file lost or moved or added the system knows and so does aegis

## The diagnosis is the design

An agent that cannot see the disk cannot act on it. Before Squigly, three different parts of the
fleet each knew a sliver:

| Component | Knew | Blind to |
|---|---|---|
| `viper_sync` | 7 curated source paths | everything else on the disk |
| `symbolic.py` | 303 symbols from tool observations | files — it had verbs, no nouns |
| `master_graph` | the nodes it was told about | anything nobody registered |

None could answer *where is that file*, *what uses it*, or *what moved*. Squigly is the census that
makes those answerable, and it is deliberately dumb: a walk, a hash, a table. **Nothing here
infers, so nothing here can be wrong in an interesting way.**

## Zero LLM, on purpose

Purpose is not guessed by a model. It is read from three things a machine can check directly:

- **where it is** — `tests/` means test, `.github/workflows` means CI
- **what it is** — `.py` is source, `.sqlite` is data, `.jar` is a build artefact
- **what it says** — the first docstring or heading, which the author already wrote for a human

The third does most of the work and costs the least. Measured on `C:\Viper\scripts`: **321 of 400
descriptions came from the authors' own docstrings.** That is quotation, not inference. Every
classification reports how it was reached (`docstring`, `heading`, `comment`, `path`, `extension`,
`unknown`) because a caption from the author and a guess from a file extension are not the same
claim.

## What it refuses to look at

`C:\Windows`, `Program Files`, `ProgramData`, `__pycache__`, `node_modules`, caches — blocked
outright. Not for safety, since reading is harmless, but for **signal**. `C:\Windows` alone is
~128,000 files nobody will ever move, lose, or wonder about, and burying four hundred real project
files in that is how an index becomes something nobody opens. *A census that includes everything
tells you nothing.*

## Moves are a fact, not a guess

A file that disappears from one path and appears at another **with the same content hash** moved.
That is why the census hashes.

Without content identity, reorganising a folder reports as *N losses and N creations* — the two
loudest events in the system, both false, and the losses are the ones that scare you. With it, a
move is one quiet fact and only genuinely missing content is reported lost. An index that cries
wolf about reorganisation is one nobody reads twice.

## Files as states — the part that makes it a system

Chris, on what to do with local files: *"use them" / "is that 'applying something' yes" / "and then
we get a new state" / "doesnt that fit??"*

It fits exactly. A file is a **state**, using it is a **pressure**, and what you get back is a
**new state**:

| Pressure | Begin | End |
|---|---|---|
| create | absent | present |
| move | present@A | present@B *(same hash)* |
| edit | present, hash H | present, hash H′ |
| delete | present | absent |

This is why the census had to come first. `symbolic.py` learned its symbols from `tool_tape`, which
records what the fleet **did** — those are verbs. It never had the nouns, so *apply X to A* could
never have a file as its A. `states.emit_to_symbolic` supplies them, and a change stops being a
diff entry and becomes a transition carrying bans of evidence.

### The stack this completes

| Layer | Supplies |
|---|---|
| **squigly** | the nodes — every file as a state |
| **tool_tape** | the edges — which tool fired, and succeeded |
| **symbolic** | the weights — bans of evidence per transition |
| **Sophia** | the proof — is that state reachable (DPLL + bounded reachability) |

A planner built on arithmetic instead of inference. **Note: `Sophia` is listed in `FLEET_REPOS` but
is not cloned on this machine**, so the proof layer is referenced, not yet available.

## What it finds, and what it admits it misses

Dependencies come from parsing Python imports and from literal path strings in text files — which
is how the non-Python half of a fleet is actually wired: a scheduled task naming a `.ps1`, a config
pointing at a database, a batch file launching a jar.

Measured on `C:\Viper\scripts` (553 files, 3.6s): `resource_governor.py` has 20 dependents,
`telemetry.db` has 18, `python.exe` has 14 — the last two invisible to any import graph.

**Not found:** dynamic imports, `importlib` by computed name, paths built by concatenation. This is
stated rather than hidden because `orphans()` returns *candidates for review, never a delete list* —
an orphan list that is quietly wrong is more dangerous than one that names its blind spots, because
someone will eventually delete from it.

**Squigly never deletes anything.**

## Reading, never executing

Imports are resolved by `ast.parse`, never by importing. Importing a module to discover its imports
runs it — module-level code, side effects, network calls — across every file on the disk. An
indexer that executes what it indexes is a remote code execution engine with good intentions.

## Layout

```
squigly/
  census.py     walk every drive, block the noise, hash for identity
  classify.py   what is this file FOR, and how do we know
  deps.py       what uses what; who breaks if this goes
  states.py     changes as pressures and new states; bridge to symbolic.py
```
