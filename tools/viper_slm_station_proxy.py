#!/usr/bin/env python3
"""
VIPER SLM Station Proxy v2.0 - Port 8765
============================================
True OpenAI-compatible /v1/chat/completions endpoint.

Backend priority (auto-detected):
  1. LM Studio    — http://127.0.0.1:1234/v1/chat/completions  (OpenAI-compat)
  2. House Engine — http://127.0.0.1:11435/api/generate        (house format)
  3. Stub         — Returns a synthetic response so picoclaw never hard-crashes

Used by picoclaw, sovereign loop, and other VIPER SLM agents.
"""
import json
import time
import datetime
import socket
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = 8765

LM_STUDIO_URL     = "http://127.0.0.1:1234/v1/chat/completions"
LM_STUDIO_MODELS  = "http://127.0.0.1:1234/v1/models"
HOUSE_ENGINE_URL  = "http://127.0.0.1:11435/api/generate"

# Best LM Studio model preference (from your installed models)
PREFERRED_MODELS = [
    "lmstudio-community/LFM2.5-1.2B-Instruct-GGUF/LFM2.5-1.2B-Instruct-Q8_0.gguf",
    "lmstudio-community/granite-3.1-8b-instruct-GGUF/granite-3.1-8b-instruct-Q4_K_M.gguf",
    "QuantFactory/LFM2-1.2B-Tool-GGUF/LFM2-1.2B-Tool.Q8_0.gguf",
    "mradermacher/alpha-triton-grpo-1.7b-GGUF/alpha-triton-grpo-1.7b.Q8_0.gguf",
]

_cached_lm_model = None
_last_backend_check = 0.0
_active_backend = None  # "lmstudio" | "house" | "stub"


def now_iso():
    return datetime.datetime.utcnow().isoformat() + "Z"


def port_alive(host: str, port: int, timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def detect_active_lm_model() -> str | None:
    """Ask LM Studio which model is currently loaded."""
    global _cached_lm_model
    try:
        req = urllib.request.Request(LM_STUDIO_MODELS, method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = [m.get("id", "") for m in data.get("data", [])]
            if models:
                _cached_lm_model = models[0]
                return _cached_lm_model
    except Exception:
        pass
    return None


def get_backend() -> str:
    global _last_backend_check, _active_backend
    now = time.monotonic()
    if now - _last_backend_check < 15.0 and _active_backend:
        return _active_backend

    _last_backend_check = now
    if port_alive("127.0.0.1", 1234):
        _active_backend = "lmstudio"
    elif port_alive("127.0.0.1", 11435):
        _active_backend = "house"
    else:
        _active_backend = "stub"

    print(f"[PROXY] Backend: {_active_backend}", flush=True)
    return _active_backend


def _openai_response(content: str, model: str = "viper-proxy", prompt_tokens: int = 0, comp_tokens: int = 0) -> dict:
    return {
        "id": f"chatcmpl-viper-{int(time.time())}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": content},
            "finish_reason": "stop",
        }],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": comp_tokens,
            "total_tokens": prompt_tokens + comp_tokens,
        },
    }


def _call_lmstudio(messages: list, max_tokens: int, temperature: float, model_override: str | None) -> dict:
    model = model_override or detect_active_lm_model() or PREFERRED_MODELS[0]
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        LM_STUDIO_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _call_house(messages: list, max_tokens: int, temperature: float) -> dict:
    # Convert messages to simple prompt for house engine
    parts = []
    sys_txt = ""
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role == "system":
            sys_txt = content
        elif role == "assistant":
            parts.append(f"Assistant: {content}")
        else:
            parts.append(f"User: {content}")
    prompt = "\n".join(parts) + "\nAssistant:"

    payload = json.dumps({
        "prompt": prompt,
        "system": sys_txt,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "route": "chat",
    }).encode("utf-8")
    req = urllib.request.Request(
        HOUSE_ENGINE_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        text = data.get("response", data.get("text", data.get("output", "[no response]")))
        return _openai_response(text, "house-engine")


class ProxyHandler(BaseHTTPRequestHandler):

    def _send(self, code: int, body: bytes, ct: str = "application/json") -> None:
        self.send_response(code)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, payload: dict) -> None:
        self._send(code, json.dumps(payload, indent=2).encode("utf-8"))

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length).decode("utf-8", errors="replace") if length else "{}"
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def do_OPTIONS(self) -> None:
        self._send(204, b"")

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        backend = get_backend()
        if path in ("/", "/health"):
            self._json(200, {
                "status": "ok",
                "proxy": "viper_slm_station_proxy",
                "version": "2.0",
                "backend": backend,
                "timestamp": now_iso(),
            })
        elif path == "/v1/models":
            if backend == "lmstudio":
                # Transparent pass-through
                try:
                    req = urllib.request.Request(LM_STUDIO_MODELS, method="GET")
                    with urllib.request.urlopen(req, timeout=5) as resp:
                        body = resp.read()
                    self._send(200, body, "application/json")
                    return
                except Exception:
                    pass
            # Fallback model list
            self._json(200, {
                "object": "list",
                "data": [{"id": "smollm2-360m-gguf", "object": "model", "created": int(time.time())}]
            })
        else:
            self._json(404, {"error": "not_found", "path": path})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        payload = self._read_body()

        if path not in ("/v1/chat/completions",):
            self._json(404, {"error": "not_found", "path": path})
            return

        messages = payload.get("messages", [])
        max_tokens = int(payload.get("max_tokens", 512))
        temperature = float(payload.get("temperature", 0.7))
        model_req = payload.get("model")
        stream = payload.get("stream", False)

        backend = get_backend()
        started = time.time()
        result = None
        error_txt = None

        try:
            if backend == "lmstudio":
                result = _call_lmstudio(messages, max_tokens, temperature, model_req)
            elif backend == "house":
                result = _call_house(messages, max_tokens, temperature)
            else:
                # STUB — never crash picoclaw
                last_msg = messages[-1].get("content", "") if messages else ""
                result = _openai_response(
                    f"[VIPER-STUB] No inference backend available. Your message: {last_msg[:80]}",
                    "viper-stub"
                )
        except Exception as e:
            error_txt = str(e)
            # Try fallback to house engine if lmstudio failed
            if backend == "lmstudio":
                try:
                    result = _call_house(messages, max_tokens, temperature)
                    error_txt = None
                except Exception as e2:
                    result = _openai_response(
                        f"[VIPER-ERROR] All backends failed. LMStudio: {error_txt} House: {e2}",
                        "viper-fallback"
                    )
            else:
                result = _openai_response(
                    f"[VIPER-ERROR] Backend error: {error_txt}",
                    "viper-error"
                )

        elapsed = int((time.time() - started) * 1000)
        if result:
            result.setdefault("viper_meta", {})
            result["viper_meta"] = {"backend": backend, "elapsed_ms": elapsed}

        if stream:
            # Fake streaming — send full response as single chunk
            content = ""
            try:
                content = result["choices"][0]["message"]["content"]
            except Exception:
                pass
            chunk = {
                "id": result.get("id", "chatcmpl-stream"),
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": result.get("model", backend),
                "choices": [{"index": 0, "delta": {"role": "assistant", "content": content}, "finish_reason": None}],
            }
            done_chunk = {**chunk, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
            body = f"data: {json.dumps(chunk)}\n\ndata: {json.dumps(done_chunk)}\n\ndata: [DONE]\n\n".encode("utf-8")
            self._send(200, body, "text/event-stream")
        else:
            self._json(200, result)

    def log_message(self, format: str, *args) -> None:
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] PROXY {format % args}", flush=True)


def run():
    server = ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), ProxyHandler)
    print(f"VIPER SLM Station Proxy v2.0 listening on http://{LISTEN_HOST}:{LISTEN_PORT}", flush=True)
    print(f"Backend auto-detection: LM Studio (1234) > House Engine (11435) > Stub", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    run()
