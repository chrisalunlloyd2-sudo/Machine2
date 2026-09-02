#!/bin/sh
# BDI_FSM_AGENT setup — verify environment + run self-tests. Zero install.
set -e
cd "$(dirname "$0")/.."
echo "[1/2] checking python..."
python3 --version
echo "[2/2] running deterministic self-test suite (zero LLM)..."
python3 tests/test_all.py
echo "SETUP OK — 58/58 green, no dependencies, no model."
