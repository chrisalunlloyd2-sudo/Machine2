"""CS-BUDDY '90 — a 1990s-style chat bot that TOOLCALLS WITHOUT AN LLM and LEARNS.

Deterministic conversation engine in the spirit of the FSM agent family:
* ELIZA-style pattern rules as the conversational backbone
* confidence-scored intent routing (rule weight x keyword hits)
* tool dispatch with NO LLM — intents map to registered deterministic tools
* FIVE learning loops, all deterministic:
    1. WORD learning    — unseen tokens auto-added to the lexicon w/ context
    2. PATTERN learning — unmatched input -> teach flow -> new rule saved
    3. WEIGHT learning  — confirmations strengthen, denials weaken rules
    4. FACT learning    - "my name is X" -> facts store, recalled on demand
    5. HIT learning     - per-intent hit counts steer future priority
* 90s wrapper: banner, LOADING bar, ">" prompt, HELP/MEM/TOOLS/LEARN/FACTS,
  state persisted to chatbot.mem so it survives restarts and learns across
  sessions. Pure stdlib, zero LLM, zero cloud — runs anywhere Python runs.
"""

import json
import os
import random
import re
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from .lexicon import Lexicon

MOTD = r"""
  ____ ____        ____  _   _ ____  ____  ____
 / ___| __ )      |  _ \| | | |  _ \|  _ \| __ )
 \___ \  _ \ _____| | | | | | | | | | | | |  _ \
  ___) | |_) |_____| |_| | |_| | |_| | |_| | |_) |
 |____/|____/      |____/ \___/|____/|____/|____/
   CS-BUDDY v0.90  (C) 1990 FSM SOFTWARE
   deterministic chat. no llm. learns.
"""

HELP_TEXT = """CS-BUDDY '90 commands:
  help            this text
  mem             show learned facts
  tools           list available tools (intent -> tool)
  learn           show learning stats + recent words
  status          system status report
  exit            save state and quit
Talk normally too: ask the time, ask what it can do,
teach it new phrases, tell it your name."""


class Chatbot90:
    """Deterministic 90s chat bot: pattern -> intent -> tool, with learning."""

    def __init__(self, lexicon: Optional[Lexicon] = None,
                 state_path: Optional[str] = None):
        self.lexicon = lexicon or Lexicon()
        self.lexicon.ensure_min()
        self.state_path = state_path or "chatbot.mem"
        self._tools: Dict[str, Callable] = {}
        self._tool_desc: Dict[str, str] = {}
        self.rules: List[Dict[str, Any]] = []      # learned + builtin rules
        self.weights: Dict[str, float] = {}         # intent -> weight
        self.hits: Dict[str, int] = {}              # intent -> hit count
        self.facts: Dict[str, str] = {}
        self.unknowns: List[str] = []               # unmatched phrases
        self.pending_teach: Optional[str] = None    # awaiting teach confirmation
        self.history: List[Dict[str, Any]] = []     # full conversation journal
        self.turns: List[Dict[str, Any]] = []       # recent (text, intent) pairs
        self.max_turns = 20
        self._load()
        self._seed_builtin_rules()

    # ------------------------------------------------------------------ #
    # rule table: (regex, intent, base_weight) — ELIZA-style patterns
    # ------------------------------------------------------------------ #
    def _seed_builtin_rules(self) -> None:
        builtin = [
            (r"\b(hi|hello|hey|yo|greetings|howdy)\b", "greet", 3.0),
            (r"\b(how are you|hows it going|how's it going|whats up)\b",
             "howareyou", 4.0),
            (r"\b(my name is|call me|i am|i'm)\s+([a-zA-Z]+)", "learn_name", 5.0),
            (r"\b(what('| i)?s my name|who am i|do you know me)\b", "recall_name", 4.0),
            (r"\b(remember|don't forget|note that|keep in mind)\b", "learn_fact", 4.0),
            (r"\b(what do you know|whats my|my favorite|my likes?)\b", "recall_fact", 4.0),
            (r"\b(what time|the time|time is it|current time)\b", "time", 5.0),
            (r"\b(what date|today's date|what day|todays date)\b", "date", 5.0),
            (r"\b(where are you|your position|your hex|what hex)\b", "hex", 4.0),
            (r"\b(what can you do|your skills|abilities|capabilities)\b", "skills", 4.0),
            (r"\b(tasks?|todo|whats pending|open tasks|what's pending)\b", "tasks", 4.0),
            (r"\b(define|what does|what is|whats)\s+([a-zA-Z]+)", "define", 3.5),
            (r"\b(status|report|state|system status)\b", "status", 4.0),
            (r"\b(joke|funny|something funny|make me laugh)\b", "joke", 3.0),
            (r"\b(thank|thanks|thx|appreciate)\b", "thanks", 3.0),
            (r"\b(bye|goodbye|see you|farewell|exit|quit)\b", "bye", 3.0),
            (r"\b(help|commands|options|what do you do)\b", "help", 3.0),
        ]
        # merge with any learned rules from disk (learned rules win by weight)
        known = {r["regex"] for r in self.rules}
        for regex, intent, w in builtin:
            if regex not in known:
                self.rules.append({"regex": regex, "intent": intent,
                                   "weight": w, "source": "builtin"})
        self.rules.sort(key=lambda r: r["weight"], reverse=True)

    # ------------------------------------------------------------------ #
    # tools — deterministic functions the bot can call
    # ------------------------------------------------------------------ #
    def register_tool(self, intent: str, fn: Callable, desc: str) -> None:
        self._tools[intent] = fn
        self._tool_desc[intent] = desc

    def _default_tools(self) -> None:
        self.register_tool("time", lambda: time.strftime("%H:%M:%S"),
                           "current local time")
        self.register_tool("date", lambda: time.strftime("%Y-%m-%d (%A)"),
                           "current date and weekday")
        self.register_tool("hex", self._tool_hex, "agent hex coordinate")
        self.register_tool("skills", self._tool_skills, "list capabilities")
        self.register_tool("tasks", self._tool_tasks, "open fleet tasks")
        self.register_tool("define", self._tool_define, "lexicon definition")
        self.register_tool("status", self._tool_status, "system status")
        self.register_tool("joke", self._tool_joke, "a 90s programmer joke")
        self.register_tool("help", lambda: HELP_TEXT, "command help")

    def _tool_hex(self) -> str:
        return "fsm-agent cell anchored at hex (2,0) — one hop visibility"

    def _tool_skills(self) -> str:
        names = ", ".join(f"{i}->{d}" for i, d in sorted(self._tool_desc.items()))
        return f"{len(self._tools)} tools online: {names}"

    def _tool_tasks(self) -> str:
        try:
            with open("task_pool.json") as f:
                pool = json.load(f)
            open_n = sum(1 for t in pool if not t.get("done"))
            return f"fleet task pool: {open_n} open / {len(pool)} total"
        except Exception:
            return "task pool not readable from here"

    def _tool_define(self, word: str = "") -> str:
        if not word:
            return "define what? tell me a word."
        tok = self.lexicon.lookup_tool(word)
        if tok:
            return f"'{word}' binds to tool: {tok}"
        return f"'{word}' not in lexicon yet — say it again and I'll learn it."

    def _tool_status(self) -> str:
        return (f"CS-BUDDY '90 online — {len(self.rules)} rules, "
                f"{self.lexicon.size()} lexicon tokens, "
                f"{len(self.facts)} facts, {sum(self.hits.values())} intents served")

    def _tool_joke(self) -> str:
        jokes = [
            "Why do programmers prefer dark mode? Because light attracts bugs.",
            "There are 10 kinds of people: those who understand binary and those who don't.",
            "A SQL query walks into a bar, walks up to two tables and asks: 'Mind if I JOIN you?'",
            "I would tell you a UDP joke, but you might not get it.",
            "Hardware: the parts you can kick. Software: the parts you can only curse at.",
        ]
        return random.choice(jokes)

    # ------------------------------------------------------------------ #
    # intent scoring — pure deterministic
    # ------------------------------------------------------------------ #
    def _score(self, text: str) -> List[Tuple[str, float, str]]:
        """Score every rule against the input; return (intent, score, regex)."""
        scored: List[Tuple[str, float, str]] = []
        low = text.lower()
        for rule in self.rules:
            m = re.search(rule["regex"], low)
            if not m:
                continue
            score = rule["weight"]
            # keyword hits reinforce: count distinct matched words
            score += min(2.0, 0.5 * len(set(m.groups())))
            w = self.weights.get(rule["intent"], 1.0)
            score *= w
            scored.append((rule["intent"], score, rule["regex"]))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    # ------------------------------------------------------------------ #
    # main entry — chat one line, get a reply
    # ------------------------------------------------------------------ #
    def respond(self, text: str) -> str:
        text = (text or "").strip()
        if not text:
            return "> ..."

        # pending teach confirmation flow takes priority
        if self.pending_teach is not None:
            return self._finish_teach(text)

        text = self._resolve_anaphora(text)
        self._learn_words(text)
        self.history.append({"in": text, "ts": time.time()})
        recall = self._recall(text)
        if recall is not None:
            self._bump("recall")
            self.history[-1]["out"] = recall
            return recall

        # explicit commands first (deterministic, no pattern needed)
        cmd = self._try_command(text)
        if cmd is not None:
            self._bump(cmd)
            reply = self._run(cmd, text)
            self.history[-1]["out"] = reply
            return reply

        scored = self._score(text)
        # margin routing: accept top only if clearly ahead of runner-up
        # (absolute threshold OR decisive lead) — smarter disambiguation
        if scored:
            top, second = scored[0], (scored[1] if len(scored) > 1 else None)
            if top[1] >= 2.5 and (second is None or top[1] - second[1] >= 1.0 or top[1] >= 4.0):
                intent, score, _ = top
                self._bump(intent)
                self._remember(text, intent)
                reply = self._run(intent, text)
                self.history[-1]["out"] = reply
                self.history[-1]["intent"] = intent
                return reply
            if second is not None and top[1] - second[1] < 1.0 and top[1] < 5.0:
                # tie or near-tie: ask to disambiguate (learns from the answer)
                return self._disambiguate(text, scored[:2])
        return self._fallback_teach(text)

    # ---- command dispatch (HELP/MEM/TOOLS/LEARN/STATUS/EXIT) ---------- #
    def _try_command(self, text: str) -> Optional[str]:
        low = text.lower().strip()
        if low in ("help", "?"):
            return "help"
        if low == "mem":
            return "mem"
        if low in ("tools", "tool"):
            return "tools"
        if low in ("learn", "learning"):
            return "learn"
        if low == "status":
            return "status"
        if low in ("exit", "quit", "bye"):
            return "bye"
        m = re.match(r"forget\s+([a-zA-Z_]+)", low)
        if m:
            return f"forget:{m.group(1)}"
        return None

    def _run(self, intent: str, text: str) -> str:
        if intent.startswith("forget:"):
            name = intent.split(":", 1)[1]
            before = len(self.rules)
            self.rules = [r for r in self.rules if not (r["intent"] == name and r["source"] == "learned")]
            self.weights.pop(name, None)
            self.save()
            return f"forgot learned rules for '{name}' ({before - len(self.rules)} removed)."
        if intent == "help":
            return HELP_TEXT
        if intent == "mem":
            if not self.facts:
                return "no facts learned yet. tell me: 'my name is X' or 'remember that I like Y'."
            return "facts: " + "; ".join(f"{k}={v}" for k, v in self.facts.items())
        if intent == "tools":
            return self._tool_skills()
        if intent == "learn":
            return (f"learning stats: {len(self.rules)} rules ({sum(1 for r in self.rules if r['source']=='learned')} learned), "
                    f"{self.lexicon.size()} tokens, {len(self.unknowns)} unknowns pending, "
                    f"top intents: {self._top_intents()}")
        if intent == "bye":
            self.save()
            return "saving state... goodbye. (c) 1990 FSM SOFTWARE"
        if intent == "greet":
            return "Hey! CS-BUDDY '90 at your service. Type HELP for commands, or just talk."
        if intent == "howareyou":
            return (f"All systems nominal — {len(self.rules)} rules loaded, "
                    f"no LLM in sight, learning as we speak. How about you?")
        if intent == "thanks":
            return "You're welcome! That's what I'm here for — 100% deterministic."
        if intent == "learn_name":
            m = re.search(r"\b(my name is|call me|i am|i'm)\s+([a-zA-Z]+)", text, re.I)
            if m:
                name = m.group(2).capitalize()
                self.facts["name"] = name
                self.save()
                return f"Nice to meet you, {name}. I'll remember that."
            return "what's your name?"
        if intent == "recall_name":
            return (f"Your name is {self.facts['name']}." if "name" in self.facts
                    else "I don't know your name yet — tell me: 'my name is X'.")
        if intent == "learn_fact":
            # "remember that I like X" / "remember X"
            m = re.search(r"\b(?:remember|note that|keep in mind)[:,]?\s*(?:that\s+)?(?:i\s+(?:like|love|hate|prefer)\s+)?(.+)", text, re.I)
            if m:
                fact = m.group(1).strip(" .,!?")
                if len(fact) > 2 and "my name is" not in fact:
                    self.facts[f"note_{len(self.facts)}"] = fact
                    self.save()
                    return f"Got it — noted: '{fact}'."
            return "What should I remember?"
        if intent == "recall_fact":
            return (self._tool_status() + " | facts: " +
                    "; ".join(f"{k}={v}" for k, v in self.facts.items())
                    if self.facts else self._tool_status())
        if intent == "define":
            m = re.search(r"\b(?:define|what does|what is|whats)\s+([a-zA-Z]+)", text, re.I)
            return self._tool_define(m.group(1) if m else "")
        if intent in self._tools:
            return self._tools[intent]()
        return "I don't have a tool for that yet — teach me!"

    def _top_intents(self) -> str:
        top = sorted(self.hits.items(), key=lambda kv: -kv[1])[:3]
        return ", ".join(f"{k}x{v}" for k, v in top) or "none yet"

    # ------------------------------------------------------------------ #
    # FIVE learning loops
    # ------------------------------------------------------------------ #
    def _learn_words(self, text: str) -> None:
        """LOOP 1 — unseen tokens auto-enter the lexicon via mirror() (context)."""
        added = self.lexicon.mirror(text)
        if added:
            self._log("learn", f"+{len(added)} words from: {text[:40]}")

    def _disambiguate(self, text: str, cands) -> str:
        """Near-tie between intents: ask, and learn from the answer."""
        # include every candidate within 1.0 of the top score
        top_s = cands[0][1]
        all_c = [c for c in self._score(text) if c[1] >= top_s - 1.0]
        self.pending_teach = text
        self._pending_cands = [c[0] for c in all_c]
        menu = ", ".join(f"{i + 1}={c[0]}" for i, c in enumerate(all_c))
        return (f"Not sure — did you mean {menu}? "
                f"(reply a number, or 'teach <intent>')")

    def _fallback_teach(self, text: str) -> str:
        """LOOP 2 + 3 — no confident match: start the teach flow."""
        self.unknowns.append(text)
        scored = self._score(text)
        closest = scored[0][0] if scored else None
        self.pending_teach = text
        if closest:
            return (f"Hmm, I don't quite get that. Did you mean '{closest}'? "
                    f"(yes/no — or say 'teach <intent>' to bind it)")
        return ("I don't know that one yet. Teach me: reply with an intent name "
                "like 'teach greet' or 'teach status', or tell me what it should do.")

    def _finish_teach(self, reply: str) -> str:
        """Resolve the pending teach: yes/no confirms or re-binds intent."""
        original = self.pending_teach
        self.pending_teach = None
        low = reply.lower().strip()

        m = re.match(r"teach\s+([a-zA-Z_]+)", low)
        if m:
            intent = m.group(1)
            return self._save_rule(original, intent)

        if (hasattr(self, "_pending_cands") and low.isdigit()
                and 1 <= int(low) <= len(self._pending_cands)):
            intent = self._pending_cands[int(low) - 1]
            self._pending_cands = None
            self.weights[intent] = self.weights.get(intent, 1.0) + 0.3
            self._save_rule(original, intent)
            self._log("reinforce", f"disambiguated -> {intent}")
            return f"Got it — '{original[:40]}' means '{intent}'."

        if low in ("yes", "yep", "yeah", "y"):
            scored = self._score(original)
            if scored:
                intent = scored[0][0]
                # LOOP 3 — confirmation strengthens the winning rule
                self.weights[intent] = self.weights.get(intent, 1.0) + 0.2
                self._log("reinforce", f"{intent} weight -> {self.weights[intent]:.2f}")
                self.save()
                return f"Got it — I'll treat that as '{intent}' next time."
            return "ok, noted."
        if low in ("no", "nope", "n", "not that", "wrong"):
            # record a negative so we never over-guess this phrase
            self._log("negative", f"NOT {original[:50]}")
            self._dampen(original)
            return "Fair enough — I've dampened that guess. Say 'teach <intent>' to bind it properly."

        # free-form: treat as the intended meaning and save as new rule
        return self._save_rule(original, self._slug(reply))

    def _save_rule(self, phrase: str, intent: str) -> str:
        """LOOP 2 — persist a learned pattern rule."""
        if not intent or intent in ("yes", "no"):
            return "I need a real intent name — try 'teach greet'."
        if not re.fullmatch(r"[a-z][a-z_]{1,23}", intent):
            return (f"'{intent[:24]}' is not a valid intent name. "
                    f"Use one word, lowercase: 'teach status', 'teach greet', ...")
        words = re.findall(r"[a-zA-Z]{3,}", phrase.lower())
        if not words:
            return "that phrase is too short to learn."
        # build a tolerant regex from the phrase's content words
        core = "|".join(sorted(set(words), key=len, reverse=True)[:4])
        regex = rf"\b({core})\b"
        if any(r["regex"] == regex for r in self.rules):
            self.weights[intent] = self.weights.get(intent, 1.0) + 0.3
            self.save()
            return f"Already know that pattern — reinforced '{intent}'."
        self.rules.append({"regex": regex, "intent": intent,
                           "weight": 3.0, "source": "learned"})
        self.rules.sort(key=lambda r: r["weight"], reverse=True)
        self._log("teach", f"'{phrase[:40]}' -> {intent}")
        self.save()
        return f"Learned! '{phrase[:40]}' now routes to '{intent}'."

    def _dampen(self, phrase: str) -> None:
        """Reduce weight of whatever rule weakly matched a denied phrase."""
        scored = self._score(phrase)
        if scored:
            intent = scored[0][0]
            self.weights[intent] = max(0.3, self.weights.get(intent, 1.0) - 0.2)
            self._log("dampen", f"{intent} weight -> {self.weights[intent]:.2f}")
            self.save()

    def _slug(self, s: str) -> str:
        s = re.sub(r"[^a-zA-Z]+", "_", s.lower()).strip("_")
        return s[:24] or "custom"

    # ------------------------------------------------------------------ #
    # persistence + stats
    # ------------------------------------------------------------------ #
    def _bump(self, intent: str) -> None:
        """LOOP 5 — hit counting."""
        self.hits[intent] = self.hits.get(intent, 0) + 1

    def _remember(self, text: str, intent: str) -> None:
        """Multi-turn memory: keep recent (text, intent) for anaphora + recall."""
        self.turns.append({"in": text, "intent": intent})
        if len(self.turns) > self.max_turns:
            self.turns = self.turns[-self.max_turns:]

    def _resolve_anaphora(self, text: str) -> str:
        """'it / that / this / the thing' refers to the last non-command topic."""
        if not re.search(r"\b(it|that|this|the thing)\b", text.lower()):
            return text
        for t in reversed(self.turns):
            if t["intent"] not in ("greet", "thanks", "bye", "help"):
                return f"{text} ({t['in']})"
        return text

    def _recall(self, text: str) -> Optional[str]:
        """Recall recent conversation when asked."""
        low = text.lower()
        if re.search(r"what did i (say|just say|ask)|recall|what were we talking", low):
            if not self.turns:
                return "we haven't talked much yet — say something first!"
            lines = " | ".join(f"[{t['intent']}] {t['in'][:40]}" for t in self.turns[-5:])
            return f"recent turns: {lines}"
        if re.search(r"what (did|do) you (hear|learn)|show (me )?your memory", low):
            return self._run("learn", text)
        return None

    def _log(self, kind: str, detail: str) -> None:
        self.history.append({"kind": kind, "detail": detail, "ts": time.time()})

    def save(self) -> None:
        data = {
            "rules": self.rules, "weights": self.weights, "hits": self.hits,
            "facts": self.facts, "unknowns": self.unknowns[-50:],
        }
        try:
            with open(self.state_path, "w") as f:
                json.dump(data, f, indent=1)
        except OSError:
            pass  # read-only env — learning stays in memory for the session

    def _load(self) -> None:
        if not os.path.exists(self.state_path):
            return
        try:
            with open(self.state_path) as f:
                data = json.load(f)
            self.rules = data.get("rules", [])
            self.weights = data.get("weights", {})
            self.hits = data.get("hits", {})
            self.facts = data.get("facts", {})
            self.unknowns = data.get("unknowns", [])
        except (OSError, json.JSONDecodeError):
            pass

    def stats(self) -> Dict[str, Any]:
        return {
            "rules": len(self.rules),
            "learned_rules": sum(1 for r in self.rules if r["source"] == "learned"),
            "tokens": self.lexicon.size(),
            "facts": len(self.facts),
            "hits": dict(self.hits),
            "unknowns_pending": len(self.unknowns),
        }


def demo_loop() -> None:
    """90s-style interactive session."""
    bot = Chatbot90()
    bot._default_tools()
    print(MOTD)
    print("LOADING KNOWLEDGE BASE" + "." * 8)
    time.sleep(0.3)
    print(f"> {bot._tool_status()}\n")
    while True:
        try:
            line = input("> ")
        except (EOFError, KeyboardInterrupt):
            break
        if not line.strip():
            continue
        print(bot.respond(line))
        if line.strip().lower() in ("exit", "quit", "bye"):
            break
    print("\nstate saved to", bot.state_path)


if __name__ == "__main__":
    demo_loop()


# ------------------------------------------------------------------ #
# fleet-aware tool layer — the 90s bot talks about the real fleet
# ------------------------------------------------------------------ #
def fleet_tools(bot: "Chatbot90", error_learn_path: str = "/root/hexgame/error_learn.jsonl",
                state_dir: Optional[str] = None) -> None:
    """Register tools that read real fleet state. All deterministic, no LLM."""
    import json as _json

    def _read_json(path, default):
        try:
            with open(path) as f:
                raw = f.read().strip()
            if not raw:
                return default
            if raw.startswith("["):
                return _json.loads(raw)
            out = []
            for line in raw.splitlines():
                line = line.strip()
                if line:
                    out.append(_json.loads(line))
            return out
        except Exception:
            return default

    def tool_error_suggest(text: str = "") -> str:
        """Suggest a correction for an error string from error_learn.jsonl."""
        data = _read_json(error_learn_path, [])
        if not isinstance(data, list) or not data:
            return "error_learn store empty or unreadable."
        q = (text or "").lower()
        if not q:
            return f"error_learn store: {len(data)} corrections. Tell me an error to match."
        for entry in data:
            blob = " ".join(str(v) for v in entry.values()).lower()
            if q[:8] and q[:8] in blob:
                return f"match: {entry.get('class', '?')} -> {entry.get('correction', '?')}"
        return f"no match in {len(data)} corrections — teach me and I'll remember."

    def tool_hex_state() -> str:
        """Agent's hex + FOW visibility."""
        return "fsm-agent anchored at hex (2,0); FOW 1-hop visibility on the 4D hex grid."

    def tool_pool() -> str:
        """Fleet task pool status."""
        path = state_dir or "task_pool.json"
        pool = _read_json(path, [])
        if not isinstance(pool, list) or not pool:
            return "task pool not readable here."
        open_n = sum(1 for t in pool if not t.get("done"))
        return f"fleet pool: {open_n} open / {len(pool)} total tasks."

    def tool_learn_stats() -> str:
        s = bot.stats()
        return (f"rules={s['rules']} (learned {s['learned_rules']}), "
                f"tokens={s['tokens']}, facts={s['facts']}, "
                f"unknowns pending={s['unknowns_pending']}, "
                f"top: {bot._top_intents()}")

    bot.register_tool("error", tool_error_suggest, "suggest correction from error_learn")
    bot.register_tool("hex", tool_hex_state, "agent hex + FOW visibility")
    bot.register_tool("pool", tool_pool, "fleet task pool status")
    bot.register_tool("learn", tool_learn_stats, "learning stats")

    # RULES so plain words route to fleet tools (score() matches rules)
    fleet_rules = [
        (r"\b(error|bug|crash|fail|fix|broken|correction)\b", "error", 3.5),
        (r"\b(pool|tasks|todo|pending|workload)\b", "pool", 3.5),
        (r"\b(hex|position|where are you|coordinates)\b", "hex", 3.5),
        (r"\b(learning|stats|learned|memory stats)\b", "learn", 3.0),
    ]
    known = {r["regex"] for r in bot.rules}
    for regex, intent, w in fleet_rules:
        if regex not in known:
            bot.rules.append({"regex": regex, "intent": intent,
                              "weight": w, "source": "fleet"})
    bot.rules.sort(key=lambda r: r["weight"], reverse=True)

    # lexicon bindings for the boolean decide() path
    for w in ("error", "bug", "crash", "fix"):
        bot.lexicon.bind(w, "error")
    for w in ("hex", "position", "where"):
        bot.lexicon.bind(w, "hex")
    for w in ("pool", "tasks", "todo"):
        bot.lexicon.bind(w, "pool")

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
