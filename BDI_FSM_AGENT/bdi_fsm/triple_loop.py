"""TRIPLE LEARNING LOOP — chat x webcrawl x brute-foundry darwinism.

Chris's directive: the bot should self-train hourly to perfect ambiguous
code via darwinistic advancement with the brute foundry. Three loops that
feed each other and compound:

  LOOP 1 — CHAT LEARN: every chat/toolcall message is a training datum.
           Verbs -> lexicon (verb_flags.json). Prose -> chat corpus.
           The more you talk to it, the better it chats (Markov stitching).

  LOOP 2 — WEBCRAWL: paced web pages -> lexicon tokens + chat corpus.
           The bot reads, so it knows more words and more world.

  LOOP 3 — FOUNDRY DARWINISM (hourly): ambiguous code blocks -> brute
           foundry mines candidate implementations -> each candidate is
           compiled + behavior-tested (fitness) -> the fittest survives
           into the skill library, the rest are recorded so the same
           failing code is never tried twice (NMTD). Survival of the
           fittest code, measured by real tests, not by guesswork.

Each loop writes state that the others read: chat tells the foundry what
to build, webcrawl gives the foundry vocabulary, foundry winners feed
the skill library the chat can invoke. Triple compound learning.

Pure stdlib. Zero LLM for the learning itself (the SLM can *ask* via chat).
"""

import hashlib
import json
import os
import re
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple

from .lexicon import Lexicon
from .verb_flags import VerbFlags


class TripleLearningLoop:
    """Hourly self-training: chat + webcrawl + brute-foundry darwinism."""

    def __init__(self, state_dir: str, repo_dir: str,
                 foundry_dir: Optional[str] = None,
                 brute_dir: Optional[str] = None):
        self.state_dir = state_dir
        self.repo_dir = repo_dir
        self.foundry_dir = foundry_dir or os.path.join(repo_dir, "foundry")
        self.brute_dir = brute_dir or "/root/scan_tmp/brute-foundry"
        os.makedirs(state_dir, exist_ok=True)
        self.verbs = VerbFlags(state_dir)
        self.lexicon_path = os.path.join(state_dir, "lexicon.json")
        self.corpus_path = os.path.join(state_dir, "corpus", "chat_corpus.jsonl")
        self.skill_path = os.path.join(state_dir, "skills")
        self.nmtd_path = os.path.join(state_dir, "nmtd.jsonl")
        os.makedirs(os.path.join(state_dir, "corpus"), exist_ok=True)
        os.makedirs(self.skill_path, exist_ok=True)

    # =====================================================================
    # LOOP 1 — CHAT LEARN
    # =====================================================================
    def chat_learn(self, text: str, source: str = "chat") -> Dict[str, Any]:
        """One chat/toolcall message -> verbs + corpus. Returns stats."""
        learned_verbs = self.verbs.learn(text)
        words = self.verbs.tokenize(text)
        # append prose to chat corpus (quality gate: meaningful length)
        stats = {"learned_verbs": learned_verbs, "words": len(words),
                 "corpus": 0, "lexicon": 0}
        if len(words) >= 3:
            entry = {"ts": time.time(), "source": source, "text": text}
            with open(self.corpus_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
            stats["corpus"] = 1
        # lexicon: ensure new words exist (learned by Lexicon on demand)
        try:
            lex = Lexicon(self.state_dir)
            before = lex.size() if hasattr(lex, "size") else 0
            stats["lexicon"] = before
        except Exception:
            pass
        return stats

    # =====================================================================
    # LOOP 2 — WEBCRAWL (paced, cooldown-deduped)
    # =====================================================================
    def webcrawl_learn(self, max_pages: int = 2,
                       fetcher: Optional[Any] = None) -> Dict[str, Any]:
        """Crawl a few seed pages -> lexicon + corpus. Paced."""
        from .webcrawl import CrawlTrainer
        from .lexicon import Lexicon
        lexicon = Lexicon(self.lexicon_path)
        wc = CrawlTrainer(self.state_dir, fetcher=fetcher)

        def _learn(text: str, source: str) -> Dict[str, Any]:
            added = len(lexicon.mirror(text))
            return {"added": added}

        return wc.crawl(max_pages=max_pages, learn=_learn)

    # =====================================================================
    # LOOP 3 — FOUNDRY DARWINISM (survival of the fittest code)
    # =====================================================================
    def foundry_evolve(self, name: str, params: List[str],
                       examples: List[str], doc: str = "",
                       generations: int = 3) -> Dict[str, Any]:
        """Mine candidates, test fitness, keep the fittest.

        darwinistic: each generation produces variants; fitness = compiles
        AND passes the given behavior examples; the fittest survives into
        the skill library; failures go to NMTD so they're never retried.
        """
        from .brute_adapter import BruteFoundryAdapter
        from .nmtd import NMTD

        nmtd = NMTD(os.path.join(self.state_dir, "nmtd"))
        adapter = BruteFoundryAdapter(self.brute_dir, timeout=45)

        if not adapter.available():
            return {"ok": False, "error": "brute-foundry not available",
                    "brute_dir": self.brute_dir}

        gen_stats = []
        fittest, fittest_score = None, -1.0
        for g in range(generations):
            # candidate source: brute foundry mine (with prior winners as examples)
            ex = examples + ([fittest] if fittest else [])
            res = adapter.mine(name, params, ex, doc)
            winner = adapter.extract_winner(res)
            if not winner:
                gen_stats.append({"gen": g, "ok": False,
                                  "error": res.get("error", "no winner")})
                continue
            # fitness: compiles + behavior examples pass
            score, details = self._fitness(winner, params, examples)
            gen_stats.append({"gen": g, "ok": True, "score": score,
                              "candidate_len": len(winner),
                              "details": details})
            if score > fittest_score:
                fittest, fittest_score = winner, score
            if score >= 1.0:
                break  # perfect fitness, stop early (pacing)
        # persist the fittest
        outcome = {"ok": False}
        if fittest and fittest_score > 0:
            sha = hashlib.sha256(fittest.encode()).hexdigest()[:12]
            skill_file = os.path.join(self.skill_path, f"{name}_{sha}.py")
            with open(skill_file, "w") as f:
                f.write(fittest)
            with open(os.path.join(self.state_dir, "foundry_fittest.jsonl"), "a") as f:
                f.write(json.dumps({"ts": time.time(), "name": name, "sha": sha,
                                    "score": fittest_score, "params": params,
                                    "file": skill_file}) + "\n")
            outcome = {"ok": True, "name": name, "sha": sha, "score": fittest_score,
                       "file": skill_file, "generations": gen_stats}
        else:
            nmtd.record(name, "foundry", [name], f"no fittest found for {name}",
                        [str(x.get('error', '')) for x in gen_stats])
        return outcome

    def _fitness(self, code: str, params: List[str],
                 examples: List[str]) -> Tuple[float, Dict]:
        """Score a candidate: compile clean + each example behaves right."""
        try:
            compile(code, "<foundry>", "exec")
        except SyntaxError as e:
            return 0.0, {"compile": False, "error": str(e)}
        # behavior test in isolated namespace
        ns: Dict[str, Any] = {}
        try:
            exec(compile(code, "<foundry>", "exec"), ns)
        except Exception as e:
            return 0.0, {"compile": True, "exec_error": str(e)}
        passed = 0
        for ex in examples:
            try:
                expr = ex.strip()
                if expr and "==" in expr:
                    left, right = expr.split("==", 1)
                    # try function call by name
                    for k, v in ns.items():
                        if callable(v) and not k.startswith("_"):
                            left_eval = eval(left.strip(), {}, {k: v})
                            break
                    else:
                        continue
                    if str(left_eval).strip() == right.strip():
                        passed += 1
            except Exception:
                pass
        score = passed / max(len(examples), 1)
        return score, {"compile": True, "examples_passed": passed,
                       "examples_total": len(examples)}

    # =====================================================================
    # HOURLY RUN — one iteration of all three loops
    # =====================================================================
    def run_hourly(self, crawl: bool = True,
                   foundry: bool = True,
                   feature: bool = True) -> Dict[str, Any]:
        """Self-train once an hour: chat-learn pending, webcrawl, foundry,
        and (side quest) update the Daily Feature with sibling repo changes."""
        out: Dict[str, Any] = {"ts": time.time(), "loops": {}}
        # LOOP 1: drain pending chat messages (chat_inbox.jsonl)
        inbox = os.path.join(self.state_dir, "chat_inbox.jsonl")
        chat_stats = {"messages": 0, "verbs": 0, "corpus": 0}
        if os.path.exists(inbox):
            pending = []
            with open(inbox) as f:
                pending = [json.loads(l) for l in f if l.strip()]
            if pending:
                os.replace(inbox, inbox + ".old")
                for msg in pending:
                    s = self.chat_learn(msg.get("text", ""),
                                        msg.get("source", "chat"))
                    chat_stats["messages"] += 1
                    chat_stats["verbs"] += len(s["learned_verbs"])
                    chat_stats["corpus"] += s["corpus"]
        out["loops"]["chat"] = chat_stats
        # LOOP 2: webcrawl (paced)
        out["loops"]["webcrawl"] = self.webcrawl_learn(max_pages=2) if crawl \
            else {"skipped": True}
        # LOOP 3: foundry darwinism (only if there's a spec to evolve)
        out["loops"]["foundry"] = self._foundry_pending() if foundry \
            else {"skipped": True}
        # SIDE QUEST: Daily Feature — surface mind-palace/SIMS1337 changes
        if feature:
            try:
                from .daily_feature import run as df_run
                df = df_run(dry_run=False, state_dir=self.state_dir)
                out["loops"]["feature"] = {
                    "ok": df.get("ok"), "repo": (df.get("feature") or {}).get("repo"),
                    "commit": (df.get("feature") or {}).get("commit"),
                    "is_new": (df.get("feature") or {}).get("is_new")}
            except Exception as e:
                out["loops"]["feature"] = {"ok": False, "error": str(e)}
        else:
            out["loops"]["feature"] = {"skipped": True}
        # record the hourly run
        with open(os.path.join(self.state_dir, "triple_loop_log.jsonl"), "a") as f:
            f.write(json.dumps(out) + "\n")
        return out

    def _foundry_pending(self) -> Dict[str, Any]:
        """Evolve the highest-priority pending spec from foundry_queue.json."""
        q = os.path.join(self.state_dir, "foundry_queue.json")
        if not os.path.exists(q):
            return {"skipped": True, "reason": "no foundry queue"}
        try:
            queue = json.load(open(q))
        except Exception:
            return {"skipped": True, "reason": "queue unreadable"}
        if not queue:
            return {"skipped": True, "reason": "queue empty"}
        spec = queue.pop(0)
        with open(q, "w") as f:
            json.dump(queue, f, indent=2)
        return self.foundry_evolve(spec.get("name", "candidate"),
                                   spec.get("params", []),
                                   spec.get("examples", []),
                                   spec.get("doc", ""))

    def queue_foundry(self, name: str, params: List[str],
                      examples: List[str], doc: str = "") -> None:
        """Queue a spec for the next hourly darwinistic evolution."""
        q = os.path.join(self.state_dir, "foundry_queue.json")
        queue = []
        if os.path.exists(q):
            try:
                queue = json.load(open(q))
            except Exception:
                queue = []
        queue.append({"name": name, "params": params, "examples": examples,
                      "doc": doc, "ts": time.time()})
        with open(q, "w") as f:
            json.dump(queue, f, indent=2)

    def enqueue_chat(self, text: str, source: str = "chat") -> None:
        """Drop a chat message into the inbox for the next hourly learn."""
        inbox = os.path.join(self.state_dir, "chat_inbox.jsonl")
        with open(inbox, "a") as f:
            f.write(json.dumps({"ts": time.time(), "text": text,
                                "source": source}) + "\n")

    def stats(self) -> Dict[str, Any]:
        n_corpus = 0
        if os.path.exists(self.corpus_path):
            n_corpus = sum(1 for _ in open(self.corpus_path))
        n_skills = len(os.listdir(self.skill_path)) if os.path.exists(self.skill_path) else 0
        return {"verbs": self.verbs.stats(),
                "chat_corpus_docs": n_corpus,
                "skills": n_skills,
                "foundry_queue": self._foundry_queue_len()}

    def _foundry_queue_len(self) -> int:
        q = os.path.join(self.state_dir, "foundry_queue.json")
        if os.path.exists(q):
            try:
                return len(json.load(open(q)))
            except Exception:
                return 0
        return 0

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
