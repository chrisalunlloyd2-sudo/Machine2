from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Iterable, Tuple


BRIDGE = "http://127.0.0.1:8080"
SHIPPER = "http://127.0.0.1:18081"
HOUSE = "http://127.0.0.1:11435"


def _request(method: str, url: str, payload: Dict[str, Any] | None = None, timeout: float = 10.0) -> Tuple[int, Dict[str, Any]]:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            data = {"raw": raw[:500]}
        return response.status, data


def _log(test_name: str, layer: str, status: str, details: str, evidence: Dict[str, Any]) -> Dict[str, Any]:
    try:
        _, result = _request(
            "POST",
            f"{BRIDGE}/api/system/tests",
            {
                "test_name": test_name,
                "layer": layer,
                "status": status,
                "details": details,
                "evidence": evidence,
            },
            timeout=5,
        )
        return result
    except Exception as exc:
        return {"status": "log_failed", "error": str(exc)}


def run_check(name: str, layer: str, method: str, url: str, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    start = time.perf_counter()
    try:
        code, data = _request(method, url, payload, timeout=15)
        ms = round((time.perf_counter() - start) * 1000, 2)
        passed = 200 <= code < 300
        details = f"HTTP {code} in {ms}ms"
        evidence = {"url": url, "http_status": code, "elapsed_ms": ms, "keys": sorted(data.keys())[:12]}
        log_result = _log(name, layer, "pass" if passed else "fail", details, evidence)
        return {"test_name": name, "layer": layer, "status": "pass" if passed else "fail", "details": details, "log": log_result}
    except Exception as exc:
        ms = round((time.perf_counter() - start) * 1000, 2)
        details = f"{type(exc).__name__}: {exc}"
        log_result = _log(name, layer, "fail", details, {"url": url, "elapsed_ms": ms})
        return {"test_name": name, "layer": layer, "status": "fail", "details": details, "log": log_result}


def checks(include_house: bool) -> Iterable[Dict[str, Any]]:
    yield run_check("bridge_datapoints", "java_gui_bridge", "GET", f"{BRIDGE}/api/datapoints")
    yield run_check("rolling_recursive", "rolling_kernel", "GET", f"{BRIDGE}/api/rolling")
    yield run_check("system_test_readback", "system_test_log", "GET", f"{BRIDGE}/api/system/tests?limit=5")
    yield run_check("logic_shipper_health", "sha256_logic_shipper", "GET", f"{SHIPPER}/health")
    if include_house:
        yield run_check(
            "house_tiny_generation",
            "house_llama_cpp",
            "POST",
            f"{HOUSE}/api/generate",
            {"prompt": "Reply with PASS only.", "max_tokens": 8},
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="VIPER system layer smoke test logger")
    parser.add_argument("--include-house", action="store_true", help="Also perform a tiny local model generation test.")
    args = parser.parse_args()
    results = list(checks(args.include_house))
    print(json.dumps({"results": results}, indent=2))
    return 0 if all(item["status"] == "pass" for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
