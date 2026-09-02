"""Telemetry + stabilization tests — performance monitoring, thresholds, trends."""
import os
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bdi_fsm.telemetry import Telemetry

# _server_health() probes REAL localhost ports (:5000/healthz, :5001/health).
# A unit test must never depend on whether a live server happens to be up in the
# current sandbox, so any test exercising stabilize()/snapshot() pins it via mock.
HEALTHY = {"5000": 200, "5001": 200}


def test_snapshot_shape():
    t = Telemetry(tempfile.mkdtemp(prefix="bdi_tel_"))
    with patch.object(t, "_server_health", return_value=HEALTHY):
        s = t.snapshot()
    assert "ts" in s
    assert "mem" in s
    assert "disk" in s
    assert "servers" in s
    assert "span_err_rate" in s
    assert s["disk"]["total_gb"] > 0


def test_stabilize_dry_run_no_actions_on_healthy():
    t = Telemetry(tempfile.mkdtemp(prefix="bdi_tel2_"))
    with patch.object(t, "_server_health", return_value=HEALTHY):
        r = t.stabilize(dry_run=True)
    assert "actions" in r
    assert "trend" in r
    # healthy sandbox (servers up, mem/disk nominal) should need nothing
    assert all(a["action"] != "restart_server" for a in r["actions"])


def test_trend_needs_two_samples():
    t = Telemetry(tempfile.mkdtemp(prefix="bdi_tel3_"))
    with patch.object(t, "_server_health", return_value=HEALTHY):
        t.snapshot()          # one sample
    tr = t.trend()
    assert tr["samples"] == 1
    assert "note" in tr   # need >= 2 samples for deltas


def test_trend_two_samples_gives_deltas():
    t = Telemetry(tempfile.mkdtemp(prefix="bdi_tel4_"))
    with patch.object(t, "_server_health", return_value=HEALTHY):
        t.snapshot()
        t.snapshot()
    tr = t.trend()
    assert tr["samples"] == 2
    assert "span_hours" in tr
