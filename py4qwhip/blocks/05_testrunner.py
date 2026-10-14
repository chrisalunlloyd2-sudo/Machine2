"""py4qwhip block 05 — test runner (battery-over-receipts).

Selftest isolation doctrine: every block runs in a FRESH PY311 subprocess;
verdict GREEN only when ALL blocks pass. Report written to
blocks\last_battery.json (artifact, not receipt).

Design notes (Chris, verbatim): "harden all to be local no cloud use this
should tie things together" — no network, no model calls, local files only.
"""

import json, subprocess, sys, os
PY311 = r"C:\Users\viper\AppData\Local\Programs\Python\Python311\python.exe"
BLOCKS = [
    ("01_bytespace", r"C:\Viper\projects\py4qwhip\blocks\01_bytespace.py"),
    ("02_karaka",    r"C:\Viper\projects\py4qwhip\blocks\02_karaka.py"),
    ("03_synthesize", r"C:\Viper\projects\py4qwhip\blocks\03_synthesize.py"),
    ("04_vm",        r"C:\Viper\projects\py4qwhip\blocks\04_vm.py"),
]
results = []
for name, path in BLOCKS:
    r = subprocess.run([PY311, path], capture_output=True, text=True, timeout=120)
    try:
        payload = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        payload = {"ok": False, "raw": r.stdout[-200:]}
    results.append({
        "block": name, "exit": r.returncode, "ok": bool(payload.get("ok")),
        "checks": payload.get("checks", {})})
report = {
    "runner": "py4qwhip test block05",
    "blocks": results,
    "passed": sum(1 for r in results if r["ok"]),
    "total": len(results),
    "verdict": "GREEN" if all(r["ok"] for r in results) else "RED",
}
with open(r"C:\Viper\projects\py4qwhip\blocks\last_battery.json", "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)
print(json.dumps({"verdict": report["verdict"], "passed": report["passed"],
                  "total": report["total"],
                  "blocks": {r["block"]: r["ok"] for r in results}}))
