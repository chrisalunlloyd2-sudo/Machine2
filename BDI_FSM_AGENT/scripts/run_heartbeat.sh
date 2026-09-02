#!/bin/sh
# One heartbeat pass: needs + orientation + FOW + proposals
cd "$(dirname "$0")/.."
python3 -m bdi_fsm.agent --heartbeat
