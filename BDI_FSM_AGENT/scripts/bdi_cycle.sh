#!/bin/sh
# BDI-FSM LONGER-TIMER CYCLE — Chris directive 2026-08-11:
# "add longer timer to bdi fsm and monitor performance more"
#
# Lock-guarded (pidfile) so cron/heartbeat/manual can't double-run. Runs the
# full deterministic cycle with a 600s budget in the background:
#   telemetry stabilize -> triple loop (chat/webcrawl/foundry/feature)
#   -> capability sweep (all LLM tasks except English creation)
#   -> betterment standby check -> git push (hot update)
# Writes heartbeat/cycle_result.json readable by the heartbeat task.
LOCK="${BDI_CYCLE_LOCK:-$PWD/heartbeat/.cycle.lock}"
OUT="${BDI_CYCLE_OUT:-$PWD/heartbeat/cycle_result.json}"
RAW="${BDI_CYCLE_RAW:-$PWD/heartbeat/cycle_out.json}"
DIR="$PWD"

if [ -f "$LOCK" ]; then
  pid=$(cat "$LOCK" 2>/dev/null)
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    echo "{\"running\":true,\"why\":\"cycle already running pid $pid\",\"ts\":$(date +%s)}" > "$OUT"
    exit 0
  fi
  rm -f "$LOCK"
fi
echo $$ > "$LOCK"
trap 'rm -f "$LOCK"' EXIT

cd "$DIR" || exit 1
# Start marker so a heartbeat can see it's in flight
echo "{\"running\":true,\"started\":$(date +%s)}" > "$OUT"
timeout "${BDI_CYCLE_TIMEOUT:-600}" python3 - "$OUT" << 'PYEOF'
import json, os, sys, time

out_path = sys.argv[1]
sys.path.insert(0, os.getcwd())
from bdi_fsm.agent import BDIFSMAgent

t0 = time.time()
a = BDIFSMAgent(os.path.join(os.getcwd(), "state"))
stages = {}

# 1. telemetry stabilization (performance monitor + heal)
try:
    st = a.telemetry_stabilize()
    stages["telemetry"] = {
        "actions": st["actions"],
        "trend": st["trend"],
        "servers": st["snapshot"]["servers"],
        "mem_avail_pct": st["snapshot"]["mem"].get("avail_pct"),
        "disk_free_gb": st["snapshot"]["disk"].get("free_gb"),
        "span_err_rate": st["snapshot"]["span_err_rate"],
    }
except Exception as e:
    stages["telemetry"] = {"error": f"{type(e).__name__}: {e}"}

# 2. triple learning loop (chat x webcrawl x foundry + daily feature)
try:
    stages["triple"] = a.triple_learn_hourly(crawl=True, foundry=True, feature=True)
except Exception as e:
    stages["triple"] = {"error": f"{type(e).__name__}: {e}"}

# 3. capability sweep — handle all non-English LLM tasks deterministically
try:
    sweep = a.capability_sweep(max_tasks=5)
    stages["capability_sweep"] = {
        "swept": sweep["swept"], "handled": sweep["handled"],
        "deferred": sweep["deferred_english_or_unknown"],
        "results": [
            {"cap": r.get("capability"), "pool_id": r.get("pool_id"),
             "task": r.get("task", "")[:60], "ok": r.get("handled")}
            for r in sweep["results"]
        ],
    }
except Exception as e:
    stages["capability_sweep"] = {"error": f"{type(e).__name__}: {e}"}

stages["elapsed_s"] = round(time.time() - t0, 1)
stages["done"] = True
stages["ts"] = int(time.time())

with open(out_path, "w") as f:
    json.dump(stages, f, default=str)
print(json.dumps(stages, default=str)[:4000])
PYEOF
rc=$?
if [ "$rc" != "0" ]; then
  echo "{\"done\":false,\"exit\":$rc,\"ts\":$(date +%s)}" > "$OUT"
fi
exit 0
