"""Aegis BDI dashboard — pure stdlib, zero deps. http://127.0.0.1:8600

Serves a live single-page app (chat + like/dislike training + self panel
+ telemetry) backed by the deterministic BDIFSMAgent. No Flask, no LLM.
"""
import json
import os
import sys
_HERE2 = os.path.dirname(os.path.abspath(__file__))
if _HERE2 not in sys.path:
    sys.path.insert(0, _HERE2)
from ascii_modules import frames_for, module_for_day
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

HERE = Path(__file__).parent
PAGE = HERE / "index.html"
# encoding is explicit on EVERY page read: read_text() defaults to the locale codec, which is
# cp1252 on the Viper host, and these pages carry em dashes. Without it the dashboard 500s before
# it serves a byte. The new fleet/ascii pages need the same treatment for the same reason.
HTML = PAGE.read_text(encoding="utf-8") if PAGE.exists() else "<h1>Aegis BDI — WebUI</h1>"
FLEET_PAGE = HERE / "fleet.html"
ASCII_PAGE = HERE / "ascii.html"
ASCII_HTML = ASCII_PAGE.read_text(encoding="utf-8") if ASCII_PAGE.exists() else "<h1>ASCII</h1>"
FLEET_HTML = FLEET_PAGE.read_text(encoding="utf-8") if FLEET_PAGE.exists() else "<h1>Fleet</h1>"

# Default state dir: the state the HIVE's agent actually writes, when that exists.
#
# It used to default to a repo-relative ./state, which is a DIFFERENT agent from the one
# bdi_cell runs every tick. The dashboard came up green and empty and looked like a working
# view of a working agent -- while showing a brain that had never made a decision. A dashboard
# pointed at the wrong state is worse than no dashboard.
_HIVE_STATE = Path(r"C:\Viper\databases\bdi_agent")
_REPO_STATE = Path(__file__).resolve().parent.parent / "state"
STATE_DIR = os.environ.get(
    "BDI_STATE_DIR", str(_HIVE_STATE if _HIVE_STATE.is_dir() else _REPO_STATE))

# Shared heartbeat updates log (written by the fleet sync, read by the UI)
UPDATES_LOG = os.environ.get("BDI_UPDATES_LOG", "/root/heartbeat_updates.jsonl")

_AGENT = None


def agent():
    global _AGENT
    if _AGENT is None:
        from bdi_fsm.agent import BDIFSMAgent
        _AGENT = BDIFSMAgent(state_dir=STATE_DIR)
    return _AGENT


def read_jsonl_tail(path, n=50):
    """Return the last n JSON lines of a .jsonl file as parsed objects."""
    p = Path(path)
    if not p.exists():
        return []
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()[-n:]
        out = []
        for ln in lines:
            try:
                out.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
        return out
    except OSError:
        return []




# ---- fleet command center --------------------------------------------------
REPOS = ["BDI_FSM_AGENT", "Sophia", "Aegis_Unified", "mind-palace", "MasterLogs",
         "Aegis_Agents", "Chrisalunlloyd2-sudo"]
DIRECTIVES = os.path.join(STATE_DIR, "directives.json")


def _git(repo, *args, timeout=6):
    import subprocess
    try:
        r = subprocess.run(["git", "-C", f"/root/{repo}", *args],
                           capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


def fleet_status():
    out = []
    for repo in REPOS:
        head = _git(repo, "rev-parse", "--short", "HEAD")
        msg = _git(repo, "log", "-1", "--format=%s")
        dirty = _git(repo, "status", "--porcelain")
        ahead = _git(repo, "rev-list", "--count", "HEAD..@{u}") or "0"
        todos = 0
        root = f"/root/{repo}"
        if os.path.isdir(root):
            for dp, dn, fn in os.walk(root):
                dn[:] = [d for d in dn if d not in (".git", "__pycache__", "dist", "build", "node_modules", ".venv")]
                for f in fn:
                    if f.endswith((".py", ".md", ".yml", ".yaml", ".js", ".html")):
                        p = os.path.join(dp, f)
                        try:
                            txt = open(p, encoding="utf-8", errors="replace").read()
                            todos += txt.count("TODO") + txt.count("FIXME")
                        except OSError:
                            pass
        out.append({"repo": repo, "head": head, "msg": (msg or "")[:60],
                    "dirty": len(dirty.splitlines()), "ahead": ahead, "todos": todos})
    return out


def planner_verdicts():
    from bdi_fsm.agent import BDIFSMAgent
    a = BDIFSMAgent(state_dir=STATE_DIR)
    audit = a.planner_audit()
    t = audit["termination"]
    reach = a.prove_exit()
    verdict = {
        "deadlock": audit["deadlock"]["holds"],
        "liveness": audit["liveness"]["holds"],
        "termination": audit["termination"]["holds"],
        "total": audit["total_correctness"]["holds"],
        "livelock_cycles": [
            " -> ".join(e["from"] for e in c) + " -> " + c[-1]["to"]
            for c in t.get("livelock_cycles", [])],
        "task_cycles": [
            " -> ".join(e["from"] for e in c) + " -> " + c[-1]["to"]
            for c in t.get("task_cycles", [])][:3],
        "exit_path": reach.get("path") or [],
        "exit_provable": reach.get("all_reachable"),
    }
    # DPLL SAT proof over the REAL FSM edges (Sophia reachability verifier)
    try:
        import sys as _sys
        for _p in ("/root/Sophia",):
            if _p not in _sys.path:
                _sys.path.insert(0, _p)
        from sophia.reach import prove_exit as _sat_exit
        from sophia.logic import parse
        fsm = a.fsm
        states = list(fsm._transitions.keys())
        edges = []
        for st, table in fsm._transitions.items():
            for ev, (nxt, guard) in table.items():
                edges.append((st, nxt, parse(guard) if isinstance(guard, str) else None))
        sat = _sat_exit(states, edges, "IDLE", ["COMMIT"], 10)
        _, bg = fsm._transitions.get("BLOCKED", {}).get("give_up", (None, None))
        verdict["dpll"] = {
            "engine": "dpll",
            "liveness": sat["all_reachable"],
            "dead": sat["dead"],
            "states": len(states),
            "edges": len(edges),
            "max_depth": sat["max_depth"],
            "retry_fix": {
                "gated": callable(bg),
                "max_retries": a.MAX_RETRIES,
                "note": "BLOCKED->give_up is N-retry gated; at exhaustion BLOCKED is a true dead-end (SAT-proven design)"
            },
        }
    except Exception as exc:
        verdict["dpll"] = {"engine": "unavailable", "error": f"{type(exc).__name__}: {exc}"}
    return verdict


def fow_status():
    """Live FOW state for the ASCII page: events, occupied cells, agents,
    seeds minted. Reads the agent-events feed the hex grid consumes."""
    ev = []
    for p in (os.path.join(STATE_DIR, "agent_events.jsonl"),
              "/root/Aegis_Unified/agent_events.jsonl"):
        if os.path.exists(p):
            for ln in open(p, encoding="utf-8", errors="replace"):
                ln = ln.strip()
                if ln:
                    try:
                        ev.append(json.loads(ln))
                    except json.JSONDecodeError:
                        pass
    ev = ev[-200:]
    agents = sorted({e.get("agent", "?") for e in ev})
    seeds = [e for e in ev if str(e.get("action", "")).startswith("seed:")]
    contracts = [e for e in ev if e.get("contract")]
    return {"events": len(ev), "agents": agents, "seed_events": len(seeds),
            "contract_events": len(contracts), "latest": ev[-8:] if ev else []}


def read_directives():
    if os.path.exists(DIRECTIVES):
        try:
            return json.loads(open(DIRECTIVES).read())
        except (OSError, json.JSONDecodeError):
            return []
    return []


def append_update(entry):
    entry.setdefault("ts", int(time.time()))
    try:
        with open(UPDATES_LOG, "a") as fh:
            fh.write(json.dumps(entry) + "\n")
    except OSError:
        pass

class Handler(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = obj if isinstance(obj, str) else json.dumps(obj)
        self.send_response(code)
        ctype = "text/html; charset=utf-8" if isinstance(obj, str) else "application/json"
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body.encode())))
        self.end_headers()
        self.wfile.write(body.encode())

    def _json_body(self):
        n = int(self.headers.get("Content-Length", 0))
        if n <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            return {}

    def _route_get(self, p):
        a = agent()
        if p == "/":
            self._send(200, HTML)
        elif p == "/api/self":
            self._send(200, a.self_summary())
        elif p == "/api/feedback":
            self._send(200, a.feedback_store.stats())
        elif p == "/api/telemetry":
            from bdi_fsm.pacing import pacing_stats
            self._send(200, {
                "dual_logger": a.dual_logger.stats(),
                "pacing": pacing_stats(),
                "entropy": a.entropy_report(),
            })
        elif p == "/api/engine_log":
            self._send(200, read_jsonl_tail(os.path.join(STATE_DIR, "engine_log.jsonl")))
        elif p == "/api/human_log":
            self._send(200, {"log": a.dual_logger.read_human_log(tail=8)})
        elif p == "/api/associations":
            self._send(200, a.feedback_store.top_associations(limit=30))
        elif p == "/api/updates":
            self._send(200, read_jsonl_tail(UPDATES_LOG, n=40))
        elif p == "/ascii":
            self._send(200, ASCII_HTML)
        elif p == "/fleet":
            self._send(200, FLEET_HTML)
        elif p == "/api/fleet":
            self._send(200, {"repos": fleet_status(),
                             "ts": int(time.time())})
        elif p == "/api/ascii/current":
            info, frames = frames_for(frames=60)
            self._send(200, {"module": info, "frames": frames})
        elif p == "/api/fow":
            self._send(200, fow_status())
        elif p == "/api/planner":
            self._send(200, planner_verdicts())
        elif p == "/api/directives":
            self._send(200, {"items": read_directives()})
        else:
            self._send(404, {"error": "not found"})

    def _route_post(self, p, d):
        a = agent()
        if p == "/api/directives/complete":
            did = d.get("id")
            items = read_directives()
            hit = None
            for it in items:
                if str(it.get("id")) == str(did) and it.get("status") != "done":
                    it["status"] = "done"
                    it["done_ts"] = int(time.time())
                    hit = it
            if hit:
                try:
                    open(DIRECTIVES, "w").write(json.dumps(items, indent=1))
                except OSError:
                    pass
                append_update({"type": "directive", "msg": f"completed: {hit.get('action', '')[:60]}"})
                self._send(200, {"ok": True, "item": hit})
            else:
                self._send(200, {"ok": False, "reason": "not found or already done"})
        elif p == "/api/actions":
            action = d.get("action")
            if action == "learning_loop":
                from bdi_fsm.learning_loop import run_learning_loop
                r = run_learning_loop(os.path.join(STATE_DIR, "code_ask_traces.jsonl"),
                                      os.path.join(STATE_DIR, "code_ask_sops.json"))
                append_update({"type": "action", "msg": f"learning loop: {r.get('traces')} traces, {r.get('promoted')} promoted, {r.get('demoted')} demoted"})
                self._send(200, {"ok": True, "result": {k: r.get(k) for k in ("traces", "promoted", "demoted")}})
            elif action == "planner_audit":
                v = planner_verdicts()
                append_update({"type": "action", "msg": f"planner audit: deadlock={v['deadlock']} liveness={v['liveness']} termination={v['termination']} livelocks={len(v['livelock_cycles'])}"})
                self._send(200, {"ok": True, "result": v})
            elif action == "workspace_scan":
                from bdi_fsm.workspace import scan_python, scan_compiler, scan_html
                broken = scan_python(STATE_DIR) + scan_compiler(STATE_DIR) + scan_html(STATE_DIR)
                append_update({"type": "action", "msg": f"workspace scan: {len(broken)} broken nodes"})
                self._send(200, {"ok": True, "broken": len(broken)})
            elif action == "dream":
                from bdi_fsm.dream_cycle import dream_cycle
                r = dream_cycle(a, email_dry_run=True)
                summary = {k: (v if not isinstance(v, dict) else
                               (v.get("error", "ok")) if "error" in v else
                               {kk: vv for kk, vv in v.items() if kk in ("archived","kept","nodes","promoted","demoted","stage","ok","reason","ran","lines","sops")}) for k, v in r.items()}
                append_update({"type": "dream", "msg": f"dream cycle: {json.dumps(summary)[:200]}"})
                self._send(200, {"ok": True, "result": r})
            elif action == "corpus_stats":
                cp = os.path.join(STATE_DIR, "corpus", "chat_corpus.jsonl")
                n = sum(1 for _ in open(cp)) if os.path.exists(cp) else 0
                append_update({"type": "action", "msg": f"corpus: {n} lines"})
                self._send(200, {"ok": True, "corpus_lines": n})
            else:
                self._send(200, {"ok": False, "reason": f"unknown action {action!r}"})
        elif p == "/api/chat":
            prompt = (d.get("prompt") or "").strip()
            if not prompt:
                self._send(200, {"reply": "(empty prompt)", "curve": []})
                return
            # Conversational prose via Markov plateau (not boolean YES/NO).
            #
            # TWO DIALS, both exposed, because the shipped defaults produce the dullest possible
            # reply and that is what made the chat look scripted:
            #
            #   entropy_cap  halts generation the moment a step gets surprising. At the default
            #                3.0 the chain stops as soon as it becomes interesting, so replies
            #                come back as four-word stubs. 7.0 lets a sentence run.
            #   surprise     chat_plateau returns the LOWEST-entropy candidate — the most
            #                coherent, which is also the most boring. Picking the highest-entropy
            #                candidate instead is what MegaHAL actually did in 1996, and it is
            #                what makes the replies worth reading.
            #
            # Defaults chosen for the conversation Chris wants; both overridable per request.
            cap = float(d.get("entropy_cap", 7.0))
            spike = float(d.get("spike_mult", 4.0))
            surprise = bool(d.get("surprise", True))
            out = a.chat_plateau(prompt, max_words=int(d.get("max_words", 60)),
                                 entropy_cap=cap, spike_mult=spike,
                                 max_candidates=int(d.get("max_candidates", 20)))
            curve = out.get("curve") or []
            best = out.get("best") or {}
            if surprise and curve:
                best = max(curve, key=lambda c: c.get("word_entropy", 0.0))
            self._send(200, {
                "reply": best.get("text", ""),
                "surprise": surprise,
                "entropy_cap": cap,
                "plateaued": out.get("plateaued", False),
                "candidates": out.get("candidates", 0),
                "plateau_entropy": best.get("word_entropy", out.get("plateau_entropy", 0.0)),
                "corpus_docs": len(a._gather_corpus_texts()),
                "curve": [{"i": c["index"], "H": c["word_entropy"]} for c in curve],
            })
        elif p == "/api/chat_plateau":
            prompt = (d.get("prompt") or "").strip()
            if not prompt:
                self._send(200, {"reply": "(empty prompt)", "curve": []})
                return
            out = a.chat_plateau(prompt, max_candidates=int(d.get("max_candidates", 20)))
            best = out.get("best") or {}
            self._send(200, {
                "reply": best.get("text", ""),
                "plateaued": out.get("plateaued", False),
                "candidates": out.get("candidates", 0),
                "plateau_entropy": out.get("plateau_entropy", 0.0),
                "curve": [{"i": c["index"], "H": c["word_entropy"]} for c in out.get("curve", [])],
            })
        elif p == "/api/feedback":
            result = a.feedback(d.get("prompt", ""), d.get("reply", ""), bool(d.get("positive", True)))
            self._send(200, result)
        else:
            self._send(404, {"error": "not found"})

    def do_GET(self):
        try:
            self._route_get(urlparse(self.path).path)
        except Exception as e:
            self._send(500, {"error": str(e)})

    def do_POST(self):
        try:
            self._route_post(urlparse(self.path).path, self._json_body())
        except Exception as e:
            self._send(500, {"error": str(e)})

    def log_message(self, *a):
        pass  # silence request logs


if __name__ == "__main__":
    port = int(os.environ.get("BDI_PORT", "8600"))
    print(f"Aegis BDI dashboard → http://127.0.0.1:{port}  (state={STATE_DIR})")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
