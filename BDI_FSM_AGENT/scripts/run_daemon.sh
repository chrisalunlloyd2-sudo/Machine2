#!/bin/sh
# Live production loop against a workspace. Usage: ./scripts/run_daemon.sh <workspace> [testcmd] [max]
cd "$(dirname "$0")/.."
WS="${1:?usage: run_daemon.sh <workspace> [testcmd] [max]}"
TEST="${2:-python3 -m py_compile}"
MAX="${3:-3}"
python3 -m bdi_fsm.daemon --workspace "$WS" --test "$TEST" --max "$MAX"
