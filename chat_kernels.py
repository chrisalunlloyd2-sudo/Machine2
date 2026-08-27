"""Which model answers Chris in the chat window, and how she changes it.

SCOPE, stated first because it is the whole point: this is the CHAT PATH ONLY.
Chris, 2026-08-26: "just for chat the system stays as it". model_router.py still
owns every other role -- critic, tools, math, quick. Nothing here is imported by
the hive, by todo_driver, or by any cell. If you find yourself wanting to route a
non-chat call through this file, you want model_router instead.

WHY A REGISTRY AND NOT A CONSTANT

The chat model was the literal string "tinyllama:1.1b", twice, in two different
functions of desktop_moe_orchestrator.py. Changing it meant editing both, and
missing one meant the synthesis path and the direct path silently disagreed
about who was talking. A registry makes the choice one value, written down in
one place, with the reasons attached.

WHY THE REASONS ARE ATTACHED

This box is a 4-core Xeon with a 3GB Quadro 4000, and everything runs on CPU
(num_gpu: 0). Measured: ~15 tok/s on a 1.1b, ~7.4 tok/s under hive load. A 9b
kernel is not "the good one", it is roughly a token per second and a reply that
arrives after the question stopped mattering. So every entry carries an honest
speed note. A menu that lets you pick a kernel without telling you it will take
four minutes is a menu that wastes your afternoon politely.
"""

import json
import os
import time
import urllib.request as _req

CONFIG = r"C:\Viper\databases\aegis\chat_kernel.json"
OLLAMA = "http://127.0.0.1:11434"

# Chris's pick, 2026-08-26, after testing both: "oh tested sorry was testing use
# this one aegis-gemma2-abliterated:2b-q8" then "default actually".
#
# THIS IS A DELIBERATE EXCEPTION TO THE GEMMA RULE and it is hers to make. The
# standing rule (feedback_model_selection) is gemma never; she tested this one,
# in the chat window, and chose it. A rule she wrote does not outrank her saying
# otherwise to my face. The rule still holds for every gemma she has NOT named --
# see the exclusion list below.
#
# Abliterated: no refusal layer, which is the point -- it is here so a sensitive
# or odd conversation does not get met with a lecture.
#
# Measured 2026-08-26, 300 tokens, num_gpu 0:
#   aegis-gemma2-abliterated:2b-q8   5.19 tok/s, 13.1s cold load, 1454 chars
#   dagbs/qwen2.5-coder-3b...:q8_0   4.61 tok/s,  5.5s cold load, 1548 chars
# Faster to generate, slower to load, and she preferred the prose. Both stay in
# the menu; this one answers by default.
DEFAULT = "aegis-gemma2-abliterated:2b-q8"

# key -> (ollama tag, group, one honest line about what it costs you)
#
# NOT LISTED, ON PURPOSE:
#   gemma2:2b, codegemma:2b, gemma-summarizer, gemma-overseer, gemma-fast,
#   aegis-distilled-27b
#       Standing rule: gemma never -- see feedback_model_selection. Chris named
#       ONE exception on 2026-08-26 (aegis-gemma2-abliterated:2b-q8, now the
#       default) after testing it. An exception she named is not a licence to
#       relist the others, so they stay out. 27b is also simply unrunnable here.
#   smollm, smollm2, phi, phi3
#       Not approved. Present on disk is not the same as cleared for use.
#   nomic-embed-text
#       An embedding model. It has no chat head. Listing it would offer a
#       choice that cannot answer, which is worse than not offering it.
KERNELS = {
    # ── the default ──────────────────────────────────────────────────────────
    "aegis": (
        "aegis-gemma2-abliterated:2b-q8", "unfiltered",
        "2.8GB q8 | abliterated | 5.2 tok/s measured | THE DEFAULT: her pick after testing; loads slow (13s), writes fast"),

    # ── unfiltered, for sensitive or strange ground ──────────────────────────
    "coder3b": (
        "dagbs/qwen2.5-coder-3b-instruct-abliterated:q8_0", "unfiltered",
        "3.3GB q8 | abliterated | 4.6 tok/s measured | the previous default; loads in 5s, so quicker to first word"),
    "qwen3-8b": (
        "huihui_ai/qwen3-abliterated:8b", "unfiltered",
        "5.0GB | abliterated | ~2 tok/s | noticeably smarter, noticeably slower - worth it for one hard question, not for a back-and-forth"),
    "qwen3-8b-q4": (
        "huihui_ai/qwen3-abliterated:8b-Q4_K_M", "unfiltered",
        "5.0GB q4 | abliterated | ~2.5 tok/s | the same model cheaper; q4 blurs fine detail"),
    "qwen35-9b": (
        "kiwi_kiwi/qwen3.5-abliterated:9b", "unfiltered",
        "6.6GB | abliterated | ~1.5 tok/s | the most capable one here and the slowest; expect minutes, not seconds"),
    "qwen3-vl": (
        "huihui_ai/qwen3-vl-abliterated:latest", "unfiltered",
        "6.1GB | abliterated | vision-capable | ~1.5 tok/s | this is what glm-4.7-flash actually is"),
    "qwen25-vl": (
        "huihui_ai/qwen2.5-vl-abliterated:latest", "unfiltered",
        "6.0GB | abliterated | vision-capable | ~1.5 tok/s"),

    # ── fast, for when the answer matters less than having one ───────────────
    "tinyllama": (
        "tinyllama:1.1b", "fast",
        "637MB | ~15 tok/s idle, ~7.4 under load | what chat used before today"),
    "danube": (
        "hf.co/h2oai/h2o-danube3-500m-chat-GGUF:latest", "fast",
        "317MB | ~25 tok/s | the quickest thing on the box"),
    "qwen05": (
        "qwen2.5:0.5b", "fast",
        "397MB | ~20 tok/s | small but coherent"),
    "llama32-1b": (
        "llama3.2:1b", "fast",
        "1.3GB | ~12 tok/s"),
    "falcon3-1b": (
        "falcon3:1b", "fast",
        "1.8GB | ~10 tok/s"),

    # ── code ─────────────────────────────────────────────────────────────────
    "deepseek-coder": (
        "deepseek-coder:1.3b", "code",
        "776MB | ~12 tok/s | fast enough to ask mid-edit"),
    "deepseek-r1": (
        "deepseek-r1:1.5b", "code",
        "1.1GB | ~10 tok/s | shows its reasoning, which costs tokens"),
    "qwen-coder-3b": (
        "qwen2.5-coder:3b", "code",
        "1.9GB | ~5 tok/s | the un-abliterated sibling of the default"),
    "qwen-coder-15b": (
        "qwen2.5-coder:1.5b", "code",
        "986MB | ~10 tok/s"),
    "codellama": (
        "codellama:7b", "code",
        "3.8GB | ~2.5 tok/s"),

    # ── japanese ─────────────────────────────────────────────────────────────
    "jp-elyza": (
        "hf.co/elyza/Llama-3-ELYZA-JP-8B-GGUF:latest", "japanese",
        "4.9GB | llama-3 8b tuned for Japanese | ~2 tok/s"),
    "jp-youko": (
        "hf.co/mmnga/rinna-llama-3-youko-8b-gguf:latest", "japanese",
        "4.9GB | llama-3 8b, rinna Youko | ~2 tok/s"),
    "jp-evollm": (
        "hf.co/mmnga/SakanaAI-EvoLLM-JP-v1-7B-gguf:latest", "japanese",
        "4.4GB | SakanaAI evolutionary merge | ~2.5 tok/s"),
}

GROUPS = ["unfiltered", "fast", "code", "japanese"]

# The intent classifier is NOT the chat kernel and must not follow it.
#
# get_agent_from_llm asks "which of these 13 agents" and wants 20 tokens back
# inside an 8 second timeout. The default chat kernel generates at a measured
# 4.61 tok/s and cold-loads for 5.5s -- it would blow that budget every single
# time, and because stream is False a tripped timeout returns NOTHING, so every
# query would silently fall through to keyword_classify. Classification would
# get worse while looking like it had been upgraded.
#
# So this stays small on purpose. Chris, 2026-08-26: "just for chat the system
# stays as it" -- and routing is system, not chat.
CLASSIFIER = "tinyllama:1.1b"

# tokens/sec and GB on disk, per kernel key. Only coder3b and tinyllama are
# measured; the rest are scaled from parameter count and quantisation and are
# marked as such. They exist so the menu can be honest about cost and so
# plan() can size a timeout, not to be quoted as benchmarks.
#
#   aegis     MEASURED 2026-08-26: 300 tokens in 57.8s gen, 13.1s load -> 5.19
#   coder3b   MEASURED 2026-08-26: 300 tokens in 65.0s gen,  5.5s load -> 4.61
#   tinyllama MEASURED: ~15 idle, ~7.4 with the hive running. 7.4 is the honest
#             number to plan with, because the hive is always running.
SPEC = {
    "aegis":          (5.19, 2.8),   # measured
    "coder3b":        (4.61, 3.3),   # measured
    "qwen3-8b":       (2.0,  5.0),
    "qwen3-8b-q4":    (2.5,  5.0),
    "qwen35-9b":      (1.5,  6.6),
    "qwen3-vl":       (1.5,  6.1),
    "qwen25-vl":      (1.5,  6.0),
    "tinyllama":      (7.4,  0.64),  # measured, under load
    "danube":         (25.0, 0.32),
    "qwen05":         (20.0, 0.40),
    "llama32-1b":     (12.0, 1.3),
    "falcon3-1b":     (10.0, 1.8),
    "deepseek-coder": (12.0, 0.78),
    "deepseek-r1":    (10.0, 1.1),
    "qwen-coder-3b":  (5.0,  1.9),
    "qwen-coder-15b": (10.0, 0.99),
    "codellama":      (2.5,  3.8),
    "jp-elyza":       (2.0,  4.9),
    "jp-youko":       (2.0,  4.9),
    "jp-evollm":      (2.5,  4.4),
}

# Seconds of cold load per GB. EVERY chat turn pays this in full, because the
# orchestrator sends keep_alive: 0 and ollama drops the weights after each
# reply. Two measurements, 2026-08-26, and they disagree by nearly 3x:
#   coder3b  5.5s / 3.3GB = 1.67 s/GB   (warm page cache)
#   aegis   13.1s / 2.8GB = 4.68 s/GB   (cold, first load of the session)
# 5.0 is the cold number rounded up, because cold is the case that matters: the
# warm reading only happens on the second question in a row, and a budget sized
# for the warm case fails exactly when someone opens the window and asks one
# thing. Sizing to the best measurement is how you get a timeout that works in
# testing and not in use.
LOAD_S_PER_GB = 5.0

# Margin on the arithmetic. A timeout set to exactly the predicted time trips
# on the first slow token, and a tripped timeout with stream: False discards
# the entire reply -- so the failure mode of being 1% too tight is a blank
# window, not a shorter answer. Cheap to be generous here.
MARGIN = 1.4

# The longest the chat window may be left with nothing on screen. Past this
# the answer has stopped being an answer. Nothing is silently truncated when
# this binds: plan() cuts num_predict instead of the timeout and SAYS SO, so
# a short reply reads as "I was cut off" rather than "I had nothing to add".
MAX_WAIT_S = 600


def key_for(tag: str) -> str:
    """Short name for an ollama tag, or the tag back if it isn't listed."""
    for k, (t, _g, _n) in KERNELS.items():
        if t == tag:
            return k
    return tag


def spec(tag: str):
    """(tok_s, gb) for an ollama tag. Unknown tags get a pessimistic guess."""
    k = key_for(tag)
    return SPEC.get(k, (3.0, 4.0))


def plan(tag: str = None, want_tokens: int = 900) -> dict:
    """How many tokens to ask for, and how long to wait, for this kernel.

    The chat model used to be one hardcoded string with one hardcoded 180s
    timeout beside it. Once the kernel became switchable that pairing became a
    bug waiting for Chris to pick the 9b: 900 tokens at ~1.5 tok/s is ten
    minutes, and a 180s timeout would have thrown all ten minutes of it away
    with no error the GUI could show.
    """
    tag = tag or current()
    tok_s, gb = spec(tag)
    load = gb * LOAD_S_PER_GB
    need = (load + want_tokens / tok_s) * MARGIN
    if need <= MAX_WAIT_S:
        return {"model": tag, "num_predict": want_tokens,
                "timeout_s": int(need) + 1, "capped": False, "note": ""}
    # Won't fit. Shrink the ASK, not the wait.
    room = (MAX_WAIT_S / MARGIN) - load
    fits = int(max(64, room * tok_s))
    return {"model": tag, "num_predict": fits, "timeout_s": MAX_WAIT_S,
            "capped": True,
            "note": (f"[{key_for(tag)} generates at ~{tok_s:g} tok/s and cold-loads "
                     f"for ~{load:.0f}s, so this reply was capped at {fits} tokens "
                     f"instead of {want_tokens} to answer inside {MAX_WAIT_S}s. "
                     f"Ask again for the rest, or switch to a faster kernel.]")}


def _read():
    try:
        with open(CONFIG, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        # No config, or an unreadable one, is not an error -- it is the first
        # run. Falling back to DEFAULT is the correct answer to both.
        return {}


def current() -> str:
    """The ollama tag chat should use right now. Never raises, always answers.

    Called on every single chat turn, so it must not be able to break the chat
    window. A missing file, a corrupt file, or a kernel that has since been
    deleted from ollama all resolve to DEFAULT rather than to an exception --
    the one thing worse than the wrong model is no reply at all.
    """
    tag = _read().get("kernel")
    if not tag:
        return DEFAULT
    # Accept either a short key or a full ollama tag, because both will get
    # typed and refusing one of them is just a papercut.
    if tag in KERNELS:
        return KERNELS[tag][0]
    return tag


def current_key() -> str:
    """The short name of the current kernel, for display."""
    return key_for(current())


def select(name: str) -> dict:
    """Switch the chat kernel. Returns what happened, in words.

    Verifies against ollama BEFORE writing. Writing an unknown tag would move
    the failure to the next chat turn, where it would surface as a broken reply
    with no obvious cause -- and the whole reason this function exists is that a
    silent model failure is indistinguishable from a bad model.
    """
    name = (name or "").strip()
    if not name:
        return {"ok": False, "why": "no kernel named"}
    if name in KERNELS:
        tag = KERNELS[name][0]
    else:
        tag = name
        if tag not in {t for t, _g, _n in KERNELS.values()}:
            return {"ok": False, "why": f"{name!r} is not a listed kernel",
                    "known": sorted(KERNELS)}
    have = installed()
    if have is not None and tag not in have:
        return {"ok": False, "why": f"{tag} is not installed in ollama",
                "hint": f"ollama pull {tag}"}
    try:
        os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
        tmp = CONFIG + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"kernel": tag,
                       "changed_at": time.strftime("%Y-%m-%dT%H:%M:%S")}, f, indent=2)
        # Retry, not a bare os.replace. Same Windows lesson as sophia's
        # entity.py: os.replace RAISES here if the GUI happens to be reading
        # the file, and "atomic" is a POSIX promise this platform does not make.
        last = None
        for attempt in range(5):
            try:
                os.replace(tmp, CONFIG)
                last = None
                break
            except PermissionError as e:       # WinError 32
                last = e
                time.sleep(0.1 * (2 ** attempt))
        if last is not None:
            raise last
    except Exception as e:
        return {"ok": False, "why": f"{type(e).__name__}: {e}"[:160]}
    return {"ok": True, "kernel": tag, "note": describe(tag)}


def describe(tag: str) -> str:
    for _k, (t, _g, note) in KERNELS.items():
        if t == tag:
            return note
    return "not a listed kernel"


def installed():
    """Tags ollama actually has, or None if ollama could not be asked.

    None and empty-set are DELIBERATELY different. An ollama that is down must
    not read as "you have no models", because that would block every switch
    with a wrong reason -- the model is there, the server is not.
    """
    try:
        with _req.urlopen(OLLAMA + "/api/tags", timeout=5) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        return {m.get("name", "") for m in data.get("models", [])}
    except Exception:
        return None


def menu() -> str:
    """The switcher, as text the chat window can print."""
    have = installed()
    cur = current()
    out = [f"CHAT KERNEL: {current_key()}",
           f"  {describe(cur)}", ""]
    if have is None:
        out.append("(ollama did not answer - availability unknown, not empty)")
        out.append("")
    for g in GROUPS:
        rows = [(k, v) for k, v in KERNELS.items() if v[1] == g]
        if not rows:
            continue
        out.append(g.upper())
        for k, (tag, _g, note) in sorted(rows):
            mark = "*" if tag == cur else " "
            if have is None:
                avail = "?"
            else:
                avail = " " if tag in have else "-"
            out.append(f" {mark}{avail} {k:16} {note}")
        out.append("")
    out.append("switch with:  kernel <name>")
    return "\n".join(out)


def _selftest():
    """Real checks. The config is redirected -- a test that wrote the live file
    would change which model answers Chris, from inside a test run."""
    import tempfile
    global CONFIG
    checks = {}
    old = CONFIG
    try:
        CONFIG = os.path.join(tempfile.mkdtemp(prefix="ck_"), "chat_kernel.json")
        checks["default_when_unset"] = current() == DEFAULT
        checks["default_is_installed_or_ollama_down"] = (
            (installed() is None) or (DEFAULT in installed()))
        # Unknown names are refused BEFORE the write, not after.
        bad = select("no-such-kernel-xyz")
        checks["unknown_kernel_refused"] = bad["ok"] is False
        checks["unknown_leaves_config_alone"] = current() == DEFAULT
        # A real switch round-trips.
        ok = select("tinyllama")
        if ok["ok"]:
            checks["switch_round_trips"] = current() == "tinyllama:1.1b"
            checks["switch_reports_key"] = current_key() == "tinyllama"
        else:
            # ollama down or model absent: the refusal must SAY which.
            checks["switch_round_trips"] = "not installed" in ok.get("why", "")
            checks["switch_reports_key"] = True
        # A corrupt config must not take the chat window down with it.
        with open(CONFIG, "w", encoding="utf-8") as f:
            f.write("{not json")
        checks["corrupt_config_falls_back"] = current() == DEFAULT
        # The menu must render whether or not ollama is up, and must never
        # claim zero availability when it simply could not ask.
        m = menu()
        checks["menu_renders"] = "CHAT KERNEL" in m and "switch with" in m
        checks["menu_lists_every_group"] = all(g.upper() in m for g in GROUPS)
        # No banned model may be reachable through this menu.
        #
        # The gemma check is not "no gemma" any more, because Chris named one.
        # It is "no gemma SHE DID NOT NAME" -- which is the rule she actually
        # stated, and the version that still catches gemma2:2b creeping back in.
        # Loosening this to a blanket allow would have quietly retired the rule.
        ALLOWED_GEMMA = {"aegis-gemma2-abliterated:2b-q8"}
        tags = [t for t, _g, _n in KERNELS.values()]
        joined = " ".join(tags).lower()
        checks["no_unnamed_gemma"] = all(
            ("gemma" not in t.lower()) or (t in ALLOWED_GEMMA) for t in tags)
        checks["named_gemma_is_the_default"] = DEFAULT in ALLOWED_GEMMA
        checks["no_smollm"] = "smollm" not in joined
        checks["no_phi"] = "phi" not in joined
        checks["no_embedding_model"] = "nomic-embed" not in joined
        # Every listed kernel needs a speed number, or plan() silently sizes it
        # from a guess and the menu quotes a cost nobody measured.
        checks["every_kernel_has_a_spec"] = all(k in SPEC for k in KERNELS)
        # plan() must never hand back a timeout that cannot fit its own ask.
        p = plan("aegis-gemma2-abliterated:2b-q8", 900)
        checks["default_fits_without_capping"] = (
            p["capped"] is False and p["num_predict"] == 900)
        checks["default_timeout_beats_old_180"] = p["timeout_s"] > 180
        # The slowest kernel MUST cap, and must say so rather than truncate
        # quietly -- a short answer with no explanation reads as a bad model.
        slow = plan("kiwi_kiwi/qwen3.5-abliterated:9b", 900)
        checks["slow_kernel_caps"] = slow["capped"] is True
        checks["slow_kernel_explains_the_cap"] = "capped at" in slow["note"]
        checks["slow_kernel_respects_ceiling"] = slow["timeout_s"] <= MAX_WAIT_S
        checks["cap_is_not_zero"] = slow["num_predict"] >= 64
        # An unknown tag must still plan, pessimistically, not raise.
        u = plan("some-model-nobody-listed:9b", 900)
        checks["unknown_tag_still_plans"] = u["timeout_s"] > 0
        # The classifier must not follow the chat kernel.
        checks["classifier_is_not_the_chat_kernel"] = CLASSIFIER != DEFAULT
        # Named for what it actually asserts. The first version of this check
        # was called classifier_fits_8s and tested `< 60` -- a name promising
        # one bound while the assertion held a different, useless one. That is
        # the same shape as every other bug in this codebase this week: a proxy
        # standing in for the thing, agreeing with itself.
        checks["classifier_plan_is_seconds_not_minutes"] = (
            0 < plan(CLASSIFIER, 20)["timeout_s"] <= 15)
    finally:
        CONFIG = old
    failed = sorted(k for k, v in checks.items() if not v)
    return {"ok": not failed, "failed": failed, "checks": checks,
            "count": len(checks)}


if __name__ == "__main__":
    import sys
    a = sys.argv[1:]
    if a and a[0] == "--selftest":
        print(json.dumps(_selftest(), indent=2))
    elif a and a[0] == "set" and len(a) > 1:
        print(json.dumps(select(a[1]), indent=2))
    else:
        print(menu())
