import json
import os
import re
import threading
import time
from pathlib import Path


HOME = Path(os.environ.get("USERPROFILE", r"C:\Users\viper"))
ROOT = HOME / "VIPER_JAVA_RISC"
DEFAULT_QWEN = ROOT / "models" / "tiny" / "qwen2_5_0_5b_instruct" / "qwen2.5-0.5b-instruct-q4_k_m.gguf"
DEFAULT_SMOL = ROOT / "models" / "tiny" / "smollm2_360m_instruct" / "SmolLM2-360M-Instruct-Q4_K_M.gguf"
DEFAULT_H2O = ROOT / "models" / "tiny" / "h2o_danube3_500m_chat_fallback" / "h2o-danube3-500m-chat-Q4_K_M.gguf"

CHOOSER_MODEL_PATH = Path(os.environ.get("VIPER_TINY_CHOOSER_MODEL", str(DEFAULT_QWEN)))
RETRIEVAL_MODEL_PATH = Path(os.environ.get("VIPER_RETRIEVAL_MATCHER_MODEL", str(DEFAULT_SMOL)))
RETRIEVAL_FALLBACK_MODEL_PATH = Path(os.environ.get("VIPER_RETRIEVAL_FALLBACK_MODEL", str(DEFAULT_H2O)))

TINY_ENABLED = os.environ.get("VIPER_TINY_MODELS_ENABLED", "1").lower() not in {"0", "false", "no"}
TINY_THREADS = max(2, int(os.environ.get("VIPER_TINY_THREADS", str(max(2, (os.cpu_count() or 4) // 2)))))
CHOOSER_CTX = int(os.environ.get("VIPER_TINY_CHOOSER_CTX", "4096"))
RETRIEVAL_CTX = int(os.environ.get("VIPER_RETRIEVAL_MATCHER_CTX", "4096"))
MAX_TINY_INPUT_CHARS = int(os.environ.get("VIPER_TINY_MAX_INPUT_CHARS", "10000"))

try:
    from llama_cpp import Llama

    HAS_LLAMA_CPP = True
except Exception:
    Llama = None
    HAS_LLAMA_CPP = False


_MODEL_CACHE = {}
_MODEL_LOCKS = {
    "chooser": threading.Lock(),
    "retrieval": threading.Lock(),
    "retrieval_fallback": threading.Lock(),
}


def _compact_spaces(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def word_limit(text, limit):
    words = re.findall(r"\S+", str(text or ""))
    return " ".join(words[:limit])


def _load_model(kind):
    if not TINY_ENABLED:
        return None, {"status": "disabled", "kind": kind}
    if not HAS_LLAMA_CPP:
        return None, {"status": "missing_llama_cpp", "kind": kind}
    if kind == "chooser":
        path = CHOOSER_MODEL_PATH
        ctx = CHOOSER_CTX
    elif kind == "retrieval_fallback":
        path = RETRIEVAL_FALLBACK_MODEL_PATH
        ctx = RETRIEVAL_CTX
    else:
        path = RETRIEVAL_MODEL_PATH
        ctx = RETRIEVAL_CTX
    if not path.exists():
        return None, {"status": "missing_model", "kind": kind, "model_path": str(path)}
    cached = _MODEL_CACHE.get(kind)
    if cached is not None:
        return cached, {"status": "cached", "kind": kind, "model_path": str(path)}
    with _MODEL_LOCKS[kind]:
        cached = _MODEL_CACHE.get(kind)
        if cached is not None:
            return cached, {"status": "cached", "kind": kind, "model_path": str(path)}
        model = Llama(
            model_path=str(path),
            n_ctx=ctx,
            n_threads=TINY_THREADS,
            verbose=False,
        )
        _MODEL_CACHE[kind] = model
        return model, {"status": "loaded", "kind": kind, "model_path": str(path), "n_ctx": ctx}


def tiny_generate(kind, system, prompt, max_tokens=160, temperature=0.15, top_p=0.85):
    started = time.time()
    model, load_meta = _load_model(kind)
    meta = {
        "kind": kind,
        "load": load_meta,
        "duration_ms": 0,
        "max_tokens": max_tokens,
    }
    if model is None:
        meta["duration_ms"] = int((time.time() - started) * 1000)
        return {"ok": False, "text": "", "meta": meta}
    prompt = str(prompt or "")
    system = str(system or "")
    if len(prompt) + len(system) > MAX_TINY_INPUT_CHARS:
        overflow = len(prompt) + len(system)
        prompt = prompt[: MAX_TINY_INPUT_CHARS // 2] + "\n[...VIPER_TINY_INPUT_REDUCED...]\n" + prompt[-MAX_TINY_INPUT_CHARS // 2 :]
        meta["input_reduced_from_chars"] = overflow
    try:
        with _MODEL_LOCKS[kind]:
            output = model.create_chat_completion(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                repeat_penalty=1.08,
            )
        text = output["choices"][0]["message"]["content"].strip()
        meta["duration_ms"] = int((time.time() - started) * 1000)
        return {"ok": True, "text": text, "meta": meta}
    except Exception as exc:
        meta["duration_ms"] = int((time.time() - started) * 1000)
        meta["error"] = str(exc)
        return {"ok": False, "text": "", "meta": meta}


def build_candidate_packet(candidates, max_items=8, max_chars=2400):
    lines = []
    for index, item in enumerate((candidates or [])[:max_items], start=1):
        card = item.get("card", {}) if isinstance(item, dict) else {}
        source = item.get("source", "unknown") if isinstance(item, dict) else "unknown"
        score = item.get("compound_score", item.get("score", 0)) if isinstance(item, dict) else 0
        sha = str(item.get("sha256", ""))[:12] if isinstance(item, dict) else ""
        card_text = _humanize_card_text(card.get("card_15", ""), source)
        line = (
            f"C{index} source={source} score={score} sha={sha} "
            f"card={word_limit(card_text, 18)} "
            f"use={word_limit(card.get('applicability', ''), 12)} "
            f"risk={word_limit(card.get('risk', ''), 10)}"
        )
        lines.append(line)
    text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n[...candidate_packet_reduced...]"
    return text


def _candidate_summary_from_choice(text, candidates):
    match = re.search(r"\bC(\d+)\b", str(text or ""), re.IGNORECASE)
    if not match:
        return ""
    index = int(match.group(1)) - 1
    if index < 0 or index >= len(candidates or []):
        return ""
    item = candidates[index] if isinstance(candidates[index], dict) else {}
    card = item.get("card", {}) if isinstance(item, dict) else {}
    source = item.get("source", "unknown")
    score = item.get("compound_score", item.get("score", 0))
    card_15 = _humanize_card_text(card.get("card_15") or card.get("summary") or "", source)
    applicability = _compact_spaces(card.get("applicability") or "")
    risk = _compact_spaces(card.get("risk") or "")
    parts = [
        f"Source: {source}; score {score}.",
        f"Match: {card_15 or 'closest stored logic/code card.'}",
    ]
    if applicability:
        parts.append(f"Use: {applicability}.")
    if risk:
        parts.append(f"Risk: {risk}.")
    return word_limit(" ".join(parts), 50)


def _fallback_candidate_summary(candidates):
    if not candidates:
        return "Source: none; Match: no strong database row found for this ask."
    item = candidates[0] if isinstance(candidates[0], dict) else {}
    card = item.get("card", {}) if isinstance(item, dict) else {}
    source = item.get("source", "unknown")
    score = item.get("compound_score", item.get("score", 0))
    text = _humanize_card_text(card.get("card_15") or card.get("summary") or "", source)
    return word_limit(f"Source: {source}; score {score}. Match: {text or 'closest stored logic/code card.'}", 50)


def _humanize_card_text(text, source):
    text = _compact_spaces(text)
    text = re.sub(r"\b[\w-]*(?:sha256|hash|id)=\S+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bsource_queue_id=\S+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bcreated_at=\S+", "", text, flags=re.IGNORECASE)
    text = _compact_spaces(text.replace("|", " "))
    if len(text) < 20 or text.count("=") > 1:
        if "CODE_BLOCKCHAIN" in str(source):
            return "Stored successful ledger code or logic block selected as the closest reusable precedent."
        return "Stored logic row selected as the closest reusable precedent."
    return text


def axiomatic_retrieval_match(ask, route, purpose, candidates):
    candidate_packet = build_candidate_packet(candidates, max_items=5, max_chars=1800)
    oversized = len(candidate_packet) + len(str(ask or "")) > MAX_TINY_INPUT_CHARS
    if oversized:
        return {
            "text": _fallback_candidate_summary(candidates),
            "status": "too_large_shipped_to_abliterated",
            "meta": {
                "reason": "tiny matcher input exceeded safe local context",
                "candidate_count": len(candidates or []),
                "large_payload_policy": "send reduced full packet to abliterated/house",
            },
        }
    system = (
        "You are VIPER's real retrieval matcher. Pick the single closest candidate "
        "to the user ask. Return at most 50 words. Format: Source: <name>; Match: "
        "<why this row helps>. Do not quote JSON. Do not answer the user."
    )
    prompt = (
        f"Route: {route}\n"
        f"Purpose: {purpose.get('purpose') if isinstance(purpose, dict) else purpose}\n"
        f"User ask:\n{ask}\n\n"
        f"Candidate DB rows:\n{candidate_packet}"
    )
    result = tiny_generate("retrieval", system, prompt, max_tokens=96, temperature=0.05)
    if not result["ok"]:
        fallback = tiny_generate("retrieval_fallback", system, prompt, max_tokens=96, temperature=0.05)
        if fallback["ok"]:
            cleaned = _candidate_summary_from_choice(fallback["text"], candidates) or word_limit(fallback["text"], 50)
            return {"text": cleaned or _fallback_candidate_summary(candidates), "status": "matched_by_h2o_fallback", "meta": fallback["meta"]}
        return {"text": _fallback_candidate_summary(candidates), "status": "deterministic_guardrail_fallback", "meta": result["meta"]}
    cleaned = _candidate_summary_from_choice(result["text"], candidates) or word_limit(result["text"], 50)
    if not cleaned:
        cleaned = _fallback_candidate_summary(candidates)
        result["meta"]["empty_text_guardrail"] = True
    return {"text": cleaned, "status": "matched_by_smollm2", "meta": result["meta"]}


def qwen_choose_lens(ask, route, fabric_layer, token_limit, purpose, retrieval_match, sources, code_sources, web_plan, user_profile=None):
    source_packet = build_candidate_packet((code_sources or []) + (sources or []), max_items=5, max_chars=1800)
    profile_text = json.dumps(user_profile or {}, ensure_ascii=True, sort_keys=True)[:600]
    system = (
        "You are VIPER's Qwen tiny chooser. Write the ACTIVE LENS only. "
        "Return 4-6 bullets, 100 words maximum. Must include: purpose, fabric layer, "
        "DB retrieval result, exact response/action instruction, safety gate. "
        "Use real retrieved data, but summarize candidates; do not quote raw candidate lines. "
        "Do not expose hidden chain-of-thought."
    )
    prompt = (
        f"Fabric layer: {fabric_layer}\n"
        f"Route: {route}\n"
        f"Token limit: {token_limit}\n"
        f"Purpose: {purpose.get('purpose') if isinstance(purpose, dict) else purpose}\n"
        f"50-word retrieval match: {word_limit(retrieval_match.get('text', ''), 50)}\n"
        f"User topology: {profile_text}\n"
        f"Web plan: {json.dumps(web_plan, ensure_ascii=True)[:800]}\n"
        f"Top retrieved DB/code rows:\n{source_packet}\n\n"
        f"User ask:\n{ask}\n\n"
        "Now write the lens as bullets, <=100 words."
    )
    result = tiny_generate("chooser", system, prompt, max_tokens=180, temperature=0.12)
    if not result["ok"] or not result["text"].strip():
        fallback = (
            f"- Purpose: {purpose.get('purpose') if isinstance(purpose, dict) else 'answer the ask'}\n"
            f"- Fabric: {fabric_layer}; route {route}; token budget {token_limit}.\n"
            f"- DB: {word_limit(retrieval_match.get('text', 'No strong match.'), 25)}\n"
            "- Act: answer directly or perform the smallest safe task step.\n"
            "- Gate: preserve GUI; log proof; Karoo proposals stay approval-gated."
        )
        return {"text": word_limit(fallback, 100), "status": "deterministic_guardrail_fallback", "meta": result["meta"]}
    return {"text": word_limit(result["text"], 100), "status": "chosen_by_qwen2_5", "meta": result["meta"]}


def qwen_rolling_triplet_card(ask, route, chooser_lens, retrieval_match):
    system = (
        "You are the tiny rolling recursive controller. Return a compact control card "
        "for the next agents. Include chooser, retriever, Karoo, abliterated summary, "
        "and tail-continuation rule. 90 words maximum."
    )
    prompt = (
        f"Route: {route}\n"
        f"Ask: {ask[:1200]}\n"
        f"Chooser lens: {word_limit(chooser_lens.get('text', ''), 80)}\n"
        f"Retrieval match: {word_limit(retrieval_match.get('text', ''), 50)}\n"
    )
    result = tiny_generate("chooser", system, prompt, max_tokens=140, temperature=0.15)
    if not result["ok"] or not result["text"].strip():
        fallback = (
            "Qwen chooser selects route and lens; SmolLM provides 50-word DB match; "
            "Karoo compares proposals; abliterated summarizes final answer. If cut off, "
            "emit TAIL_CONTINUE with next section."
        )
        return {"text": fallback, "status": "deterministic_guardrail_fallback", "meta": result["meta"]}
    return {"text": word_limit(result["text"], 90), "status": "rolling_card_by_qwen2_5", "meta": result["meta"]}


def model_status():
    return {
        "enabled": TINY_ENABLED,
        "has_llama_cpp": HAS_LLAMA_CPP,
        "chooser_model": str(CHOOSER_MODEL_PATH),
        "chooser_exists": CHOOSER_MODEL_PATH.exists(),
        "retrieval_model": str(RETRIEVAL_MODEL_PATH),
        "retrieval_exists": RETRIEVAL_MODEL_PATH.exists(),
        "retrieval_fallback_model": str(RETRIEVAL_FALLBACK_MODEL_PATH),
        "retrieval_fallback_exists": RETRIEVAL_FALLBACK_MODEL_PATH.exists(),
        "threads": TINY_THREADS,
        "max_input_chars": MAX_TINY_INPUT_CHARS,
    }


def self_test():
    status = model_status()
    chooser = tiny_generate(
        "chooser",
        "Return exactly one short status line.",
        "Say VIPER_QWEN_READY and mention chooser.",
        max_tokens=32,
        temperature=0.0,
    )
    retrieval = tiny_generate(
        "retrieval",
        "Return exactly one short status line.",
        "Say VIPER_SMOL_READY and mention retrieval.",
        max_tokens=32,
        temperature=0.0,
    )
    return {"status": status, "chooser": chooser, "retrieval": retrieval}


if __name__ == "__main__":
    print(json.dumps(self_test(), ensure_ascii=True, indent=2))
