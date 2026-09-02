"""Dream cycle (nightly maintenance) orchestration tests."""
import datetime as dt

from bdi_fsm.dream_cycle import DREAM_CRON, dream_cycle, nightly


class FakeAgent:
    def __init__(self):
        self.calls = []

    def dream(self, dry_run=False):
        self.calls.append("dream")
        return {"archived": 3, "dry_run": dry_run}

    def harvest_self_emails(self, dry_run=True):
        self.calls.append("email")
        return {"self_sent_fetched": 0, "dry_run": dry_run}

    def triple_learn_hourly(self, crawl=True, foundry=True, feature=True):
        self.calls.append("self_train")
        return {"crawl": crawl, "foundry": foundry}


def test_dream_cycle_runs_all_stages():
    a = FakeAgent()
    r = dream_cycle(a, gc=False)
    assert r["done"] is True
    assert set(a.calls) == {"dream", "email", "self_train"}
    assert r["dream"]["archived"] == 3


def test_dream_cycle_failure_isolation():
    class Broken(FakeAgent):
        def dream(self, dry_run=False):
            raise RuntimeError("boom")
    a = Broken()
    r = dream_cycle(a, gc=False)
    assert "dream" in r and "error" in r["dream"]
    # email + self_train still ran despite the dream failure
    assert "email" in a.calls and "self_train" in a.calls


def test_nightly_runs_at_night_skips_day():
    a = FakeAgent()
    night = dt.datetime(2024, 1, 1, 3, 0)
    day = dt.datetime(2024, 1, 1, 12, 0)
    r_night = nightly(a, now=night, gc=False)
    r_day = nightly(a, now=day, gc=False)
    assert r_night["ran"] is True and r_night["done"] is True
    assert r_day["ran"] is False and r_day["reason"] == "not nighttime"


def test_dream_cron_is_3am():
    from bdi_fsm.scheduler import cron_match
    assert cron_match(DREAM_CRON, dt.datetime(2024, 1, 1, 3, 0)) is True
    assert cron_match(DREAM_CRON, dt.datetime(2024, 1, 1, 3, 30)) is False
