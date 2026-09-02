"""BDI_FSM_AGENT — non-LLM tool-calling super agent.

1990s foundational paradigms: Subsumption Architecture (Brooks),
Blackboard Systems (BB1/Hearsay-II), Belief-Desire-Intention (PRS/AgentSpeak),
and Finite State Machine behavior trees.

Zero LLM/SLM. Fully deterministic, explainable, controllable by Aegis.
v0.4.0: ask_engine, code_ask (HTML block grammar), deterministic compiler,
learning_loop SOP promotion, HDC/topology, realms, asymptotic dream-cycle,
law guardrail, self-resilience substrate.
"""

__version__ = "0.4.0"

_LAZY = [
    "agent", "arch_regimes", "arch_vectors", "ask_engine", "asymptotic",
    "ban", "bayes_engine", "bdi", "blackboard", "boolean_chat", "brute_adapter",
    "btree", "calc", "capabilities", "cell", "certainty", "chatbot90", "clock",
    "code_ask", "code_patcher", "comparative_matrix", "controllers", "corpus_seed",
    "daemon", "dag_backup", "daily_feature", "delete_gate", "differential", "digest",
    "dom", "dream_cycle", "dream_prune", "emotion", "energy", "english_dag",
    "english_render", "enigma_lock", "fsm", "fuzzy", "github_corpus", "gmail_bridge",
    "hdc", "hex_grid", "hooks", "infotheory", "intent", "journal", "kqml", "lang_db",
    "langdetect", "law", "layout", "learning", "learning_loop", "markov_chat",
    "markov_plateau", "meaning", "mesh", "metaplan", "nmct", "nmtd", "pacing",
    "plateau", "pos_db", "realm", "rotor_codec", "rotor_codec_html", "rotor_codec_java",
    "scheduler", "search_fallback", "skill_library", "task_pool", "telemetry",
    "tool_observer", "topology", "triple_loop", "verb_flags", "webcrawl", "world_model",
]

__all__ = list(_LAZY) + ["__version__"]


def __getattr__(name):
    if name in _LAZY:
        import importlib
        mod = importlib.import_module(f".{name}", __name__)
        globals()[name] = mod
        return mod
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
