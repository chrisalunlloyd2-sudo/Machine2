# Code Generation — Why the Agent Never Dumps Raw Files (a "how it works" you won't forget)

> A raw `cat << 'EOF' > file` dump is an *all-or-nothing overwrite*. If one
> line in a 300-line file is wrong, you re-emit everything, you can't see *which*
> line broke, and shell escaping quietly corrupts your code before it runs.
> The agent does none of that. It patches **structure**, not files.

---

## The one-paragraph version (memorise this)

**Never write a whole file. Write one structured edit — "insert this before
method X", "replace method Y's body" — validate the result in memory as a
Python AST, and only touch disk if it compiles clean. Compiler output is
evidence: a clean compile is +30 dBan and the change locks in; a syntax error
is a contradiction, the change is eliminated, and the file is never dirtied.**

That's it. Everything below is naming the pieces.

---

## The three problems with raw dumps (why this exists)

| Problem | Raw `cat << EOF` dump | Structured AST patch |
|---|---|---|
| **Escaping drift** | shell quoting / nesting corrupts code before it runs | no shell; edits are Python objects, never shell strings |
| **No state visibility** | all-or-nothing; you can't see *which* line broke | each edit targets one node (method/class); result returns the exact hunk |
| **Token waste** | re-emit a whole file to fix one line | a 3-line unified diff for a 3-line change |

---

## The three moves

### 1. Locate — find the node, don't guess

Every edit names a **target node** (a function, method, or class). The patcher
parses the file into an AST and finds that node's exact **line span + indentation**
(including decorators). If the node doesn't exist, the edit is eliminated
immediately — there's no anchor, so there's nothing to patch.

```
locate_node("run") -> NodeSpan(start_line, node_line, end_line, indent, body_indent)
```

### 2. Build — splice lines, never regenerate

The patch is a **line splice** around the located span. Because we operate on
the original lines, every byte of existing formatting is preserved — only the
touched region changes. Five actions:

```
insert_before            insert a statement before the node (same indent)
insert_after             insert a statement after the node
insert_in_method_start   insert at the top of the node's body (nesting preserved)
replace_body             keep the signature, swap the whole body
delete                   remove the node + its decorators
```

### 3. Crib-filter — validate BEFORE any write

The patched source is parsed AND compiled **in memory** — no shell, no file.
This is the crib: like Enigma's "no letter → itself" invariant, a patch that
breaks grammar is rejected the instant it's built.

```
ast.parse(new)  -> SyntaxError?  -> reject with exact line, no disk write
compile(new)    -> error?        -> reject, no disk write
```

---

## The Banburismus gate (compiler output = evidence)

The `CodeSynthesisGate` wraps the patcher and feeds compiler output to the
Bayesian BanLedger (decibans, from `bayes_engine.py`):

```
              ┌─────────────────────────────┐
              │  LLM / observer: intent     │
              └──────────────┬──────────────┘
                             ▼
              ┌─────────────────────────────┐
              │  AST structural patch       │  (targeted diff, not a raw file)
              └──────────────┬──────────────┘
                             ▼
              ┌─────────────────────────────┐
              │  Logic DAG: ast.parse +     │  (crib filter — BEFORE write)
              │  compile() in memory        │
              └──────────────┬──────────────┘
                             ▼
              ┌─────────────────────────────┐
              │  BanLedger receives output  │
              │   pass -> +30 dBan          │
              │   fail -> -inf (eliminate)  │
              └──────────────┬──────────────┘
                             ▼
              ┌─────────────────────────────┐
              │  fire? -> atomic write      │
              │          (with .bak backup) │
              │  else  -> rollback, no dirt │
              └─────────────────────────────┘
```

- **Clean compile** = `+30 dBan` (likelihood ratio ~1000:1) → the hypothesis
  "this patch is correct" clears the 20 dBan threshold → **lock in the change**.
- **Syntax/type error** = a **contradiction** → the hypothesis drops to `-∞`
  → **eliminated**, the diff is rolled back, and the workspace is never dirtied.

This is Banburismus applied to code: evidence accumulates, bad hypotheses die,
and the gate fires only when one edit is overwhelmingly likely to be correct.

---

## The involution (rollback = Enigma's reciprocity)

Because Enigma is self-inverse (`enc(enc(x)) = x`), a lock is also its own
key. The patcher is the same: every `apply` keeps a `.bak` snapshot, so a
failed write **rolls back** to the exact prior state — symmetric, reversible,
like encrypt/decrypt. A patch that fails validation never even creates the
rollback problem, because it never writes in the first place.

---

## Running it (the `apply_ast_patch` tool)

The agent exposes this as a tool in `_build_tools`:

```python
gate.validate_and_apply(PatchOp(
    target_file="app/main.py",
    action="insert_before",
    target_node="on_create",
    payload="m_bluetooth_adapter = None\n",
))
# -> {status: "applied", dban: 30.0, diff: "...", ...}
# or
# -> {status: "rejected", dban: -inf, reason: "validation failed: SyntaxError ..."}
```

15 tests cover every action + both rejection paths + the Banburismus gate
(`tests/test_code_patcher.py`).

---

## The lesson, in one line

> *Raw dumps hide failure. Structured patches expose it, validate it, and
> score it — so a broken edit dies at the crib, not in production.*
