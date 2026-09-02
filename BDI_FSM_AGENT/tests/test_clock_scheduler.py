"""Clock (atomic epoch) + scheduler (time-aware loop) tests. No network."""
import datetime as dt

from bdi_fsm.clock import Clock, sync
from bdi_fsm.scheduler import Scheduler, cron_match, is_nighttime


def test_sync_computes_drift():
    r = sync(fetch_fn=lambda timeout: 1700000000.0)
    assert r["ok"] is True
    assert r["atomic_epoch"] == 1700000000.0
    assert abs(r["drift_seconds"] - (r["local_epoch"] - 1700000000.0)) < 1e-6


def test_sync_failure_is_explicit():
    r = sync(fetch_fn=lambda timeout: (_ for _ in ()).throw(RuntimeError("down")))
    assert r["ok"] is False
    assert r["atomic_epoch"] is None


def test_clock_now_is_drift_corrected():
    c = Clock(fetch_fn=lambda timeout: 1700000000.0)
    c.sync()
    import time
    # now() should be ~atomic, not ~local (local is far in the future here)
    assert abs((c.now() - 1700000000.0)) < 5.0


def test_cron_match_basic():
    assert cron_match("0 3 * * *", dt.datetime(2024, 1, 1, 3, 0)) is True
    assert cron_match("0 3 * * *", dt.datetime(2024, 1, 1, 4, 0)) is False
    assert cron_match("*/15 * * * *", dt.datetime(2024, 1, 1, 0, 45)) is True
    assert cron_match("*/15 * * * *", dt.datetime(2024, 1, 1, 0, 30)) is True
    assert cron_match("*/15 * * * *", dt.datetime(2024, 1, 1, 0, 20)) is False


def test_cron_match_ranges_and_lists():
    assert cron_match("0 2-4 * * *", dt.datetime(2024, 1, 1, 3, 0)) is True
    assert cron_match("0 2-4 * * *", dt.datetime(2024, 1, 1, 5, 0)) is False
    assert cron_match("0 1,3,5 * * *", dt.datetime(2024, 1, 1, 5, 0)) is True


def test_cron_match_rejects_bad_expr():
    try:
        cron_match("0 3", dt.datetime(2024, 1, 1, 3, 0))
        assert False, "should have raised"
    except ValueError:
        pass


def test_is_nighttime():
    assert is_nighttime(dt.datetime(2024, 1, 1, 3, 0)) is True
    assert is_nighttime(dt.datetime(2024, 1, 1, 0, 0)) is True
    assert is_nighttime(dt.datetime(2024, 1, 1, 6, 0)) is False
    assert is_nighttime(dt.datetime(2024, 1, 1, 12, 0)) is False


def test_scheduler_due():
    calls = []
    s = Scheduler()
    s.every("dream", "0 3 * * *", lambda: calls.append("dream"))
    s.every("learn", "0 * * * *", lambda: calls.append("learn"))
    at_3am = s.due(dt.datetime(2024, 1, 1, 3, 0))
    at_noon = s.due(dt.datetime(2024, 1, 1, 12, 0))
    assert [e["name"] for e in at_3am] == ["dream", "learn"]
    assert [e["name"] for e in at_noon] == ["learn"]
