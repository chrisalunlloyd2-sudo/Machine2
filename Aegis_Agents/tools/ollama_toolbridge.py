#!/usr/bin/env python3
"""
ollama_toolbridge.py -- native tool-calling bridge for the local hive.

2026-10-11 caretaker: recon found ZERO swarm components send a native
"tools" array to Ollama (:11434); every "tool call" is prompt-regex markup
(ds_executor DSML) or client-side ADK. This bridge closes that gap:

  model -> tool_calls JSON -> bridge executes via dispatch map
        -> tool results fed back -> model's final answer printed.

Tools are deterministic, local and read-only. GPU LAW: every request passes
options.num_gpu = 0 (GEMMA-family never touches GPU either).
Usage:
  python ollama_toolbridge.py            # demo loop against live Ollama
  python ollama_toolbridge.py --selftest # registry/schemas only, no model
"""
import json
import socket
import subprocess
import sys
import urllib.request

OLLAMA = "http://127.0.0.1:11434"
GPU_LAW = {"num_gpu": 0}  # NEVER let Ollama auto-offload; box freezes otherwise


# ---------------- deterministic local tools (read-only) ----------------

def t_port_status(port: int) -> dict:
    """Check whether a local service port is accepting connections."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2)
    rc = s.connect_ex(("127.0.0.1", int(port)))
    s.close()
    return {"port": int(port), "up": rc == 0}


def t_log_tail(path: str, n: int = 5) -> dict:
    """Return the last n lines of a local log file (read-only)."""
    with open(path, encoding="cp1252", errors="replace") as f:
        return {"path": path, "lines": f.read().splitlines()[-max(1, int(n)):]}


def t_git_status(repo: str) -> dict:
    """git status --porcelain line count for a local repo (read-only)."""
    r = subprocess.run(
        ["git", "-C", repo, "status", "--porcelain"],
        capture_output=True, text=True, timeout=30)
    lines = [l for l in r.stdout.splitlines() if l.strip()]
    return {"repo": repo, "dirty_files": len(lines),
            "sample": lines[:5], "rc": r.returncode}


TOOLS = {
    "port_status": {
        "fn": t_port_status,
        "schema": {
            "type": "function",
            "function": {
                "name": "port_status",
                "description": "Check if a local TCP port on 127.0.0.1 is up.",
                "parameters": {
                    "type": "object",
                    "properties": {"port": {"type": "integer",
                                            "description": "TCP port number"}},
                    "required": ["port"],
                },
            },
        },
    },
    "log_tail": {
        "fn": t_log_tail,
        "schema": {
            "type": "function",
            "function": {
                "name": "log_tail",
                "description": "Read the last N lines of a local log file.",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"},
                                   "n": {"type": "integer"}},
                    "required": ["path"],
                },
            },
        },
    },
    "git_status": {
        "fn": t_git_status,
        "schema": {
            "type": "function",
            "function": {
                "name": "git_status",
                "description": "Count dirty files in a local git repository.",
                "parameters": {
                    "type": "object",
                    "properties": {"repo": {"type": "string"}},
                    "required": ["repo"],
                },
            },
        },
    },
}


def _chat(messages):
    body = {
        "model": "qwen2.5-coder:3b",
        "messages": messages,
        "stream": False,
        "tools": [v["schema"] for v in TOOLS.values()],
        "options": {"num_gpu": 0, "temperature": 0.1, "num_ctx": 4096,
                    "num_predict": 700, **GPU_LAW},
    }
    req = urllib.request.Request(
        OLLAMA + "/api/chat", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=600).read().decode())


def _flatten(args: dict) -> dict:
    """Small models nest args like {"port": {"port": 8765}}; unwrap."""
    out = {}
    for k, v in (args or {}).items():
        while isinstance(v, dict) and list(v) == [k]:
            v = v[k]
        out[k] = v
    return out


def _extract_calls(msg) -> list:
    """Native tool_calls field first; else JSON markup in content
    (small models often emit calls as text). Returns [(name, args)]."""
    calls = msg.get("tool_calls") or []
    out = []
    for c in calls:
        out.append((c.get("function", {}).get("name"),
                    _flatten(c.get("function", {}).get("arguments"))))
    import re
    if not out:
        content = msg.get("content") or ""

        def _balanced(s, i):  # index of '}' matching s[i]=='{', else -1
            d = 0
            for j in range(i, len(s)):
                if s[j] == "{":
                    d += 1
                elif s[j] == "}":
                    d -= 1
                    if d == 0:
                        return j
            return -1

        for m in re.finditer(r'"name"\s*:\s*"(\w+)"\s*,\s*"arguments"\s*:\s*',
                             content):
            i = m.end()
            while i < len(content) and content[i] != "{":
                i += 1
            j = _balanced(content, i)
            if j == -1:
                continue
            try:
                out.append((m.group(1), _flatten(json.loads(content[i:j + 1]))))
            except json.JSONDecodeError:
                continue
    return [c for c in out if c[0]]


def run_loop(user_prompt: str) -> str:
    """One full tool-calling loop; returns the model's final text."""
    messages = [{"role": "user", "content": user_prompt}]
    for _ in range(3):  # bounded: prompt -> tools -> answer
        resp = _chat(messages)
        msg = resp.get("message", {})
        calls = _extract_calls(msg)
        if not calls:
            return msg.get("content", "")
        messages.append({"role": "assistant",
                         "content": msg.get("content", ""),
                         **({"tool_calls": msg.get("tool_calls")}
                            if msg.get("tool_calls") else {})})
        for name, args in calls:
            if name in TOOLS:
                try:
                    out = TOOLS[name]["fn"](**args)
                except Exception as e:  # tool errors go back to the model
                    out = {"error": str(e)[:200]}
            else:
                out = {"error": "unknown tool %s" % name}
            messages.append({"role": "tool", "name": name,
                             "content": json.dumps(out)})
    return "(loop bound reached: 3 hops)"


def selftest() -> int:
    assert "port_status" in TOOLS and "log_tail" in TOOLS
    assert t_port_status(11434)["up"] is True, "ollama port must be up here"
    assert t_port_status(1)["up"] is False
    ok = t_log_tail(__file__, 2)["lines"]
    assert len(ok) == 2 and all(isinstance(l, str) for l in ok)
    assert t_git_status(r"C:\Viper\projects\ViperCli-v2")["rc"] == 0
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    prompt = ("Use the tools to check whether local ports 8765 and 7766 "
              "are up, then report which are up in one short sentence.")
    print("PROMPT:", prompt)
    print("ANSWER:", run_loop(prompt))