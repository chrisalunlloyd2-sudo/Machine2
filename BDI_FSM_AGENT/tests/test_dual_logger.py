"""Dual-stream logger tests — JSON-L engine log + human progress cards."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bdi_fsm.dual_logger import DualStreamLogger


def test_log_cycle_writes_jsonl():
    d = tempfile.mkdtemp(prefix="bdi_dl_")
    logger = DualStreamLogger(d)
    entry = logger.log_cycle(
        cycle=1,
        beliefs={"mem_mb": 14.2, "lat_ms": 1.2},
        desire="reduce_latency",
        intention="unroll_loop_v4",
        nash=0.94,
        status="RUNNING"
    )
    assert entry["cycle"] == 1
    assert entry["nash"] == 0.94
    assert entry["status"] == "RUNNING"
    assert os.path.exists(logger.engine_log_path)
    with open(logger.engine_log_path) as f:
        lines = f.readlines()
    assert len(lines) == 1
    assert '"cycle": 1' in lines[0]


def test_error_rate_tracking():
    d = tempfile.mkdtemp(prefix="bdi_dl_")
    logger = DualStreamLogger(d)
    assert logger.error_rate() == 0.0
    logger.log_error(1, "type_error", "bad cast")
    assert logger.error_rate() == 1.0
    logger.log_ok(2)
    assert logger.error_rate() == 0.5


def test_human_card_periodic_trigger():
    d = tempfile.mkdtemp(prefix="bdi_dl_")
    logger = DualStreamLogger(d, human_interval=3)
    # First 2 cycles: no human card
    card = logger.maybe_format_human(1, "RUNNING", {}, "goal", "intent", 0.5)
    assert card is None
    card = logger.maybe_format_human(2, "RUNNING", {}, "goal", "intent", 0.5)
    assert card is None
    # 3rd cycle: periodic trigger fires
    card = logger.maybe_format_human(3, "RUNNING", {}, "goal", "intent", 0.5)
    assert card is not None
    assert "STATUS: [RUNNING]" in card
    assert "Cycle: #3" in card
    assert "[BELIEFS]" in card
    assert "[DESIRES]" in card
    assert "[CURRENT INTENTION]" in card


def test_human_card_fills_nash():
    d = tempfile.mkdtemp(prefix="bdi_dl_")
    logger = DualStreamLogger(d, human_interval=1)
    card = logger.maybe_format_human(1, "RUNNING", {"mem": "14.2"},
                                     "optimize", "unroll", 0.94)
    assert "Nash Score: 0.94/1.00" in card


def test_human_card_beliefs_rendered():
    d = tempfile.mkdtemp(prefix="bdi_dl_")
    logger = DualStreamLogger(d, human_interval=1)
    card = logger.maybe_format_human(5, "VERIFY", {"mem_mb": 14.2, "lat_ms": 1.2},
                                     "reduce_latency", "unroll_loop", 0.85)
    assert "- lat_ms: 1.2" in card
    assert "- mem_mb: 14.2" in card


def test_human_card_writes_to_log_file():
    d = tempfile.mkdtemp(prefix="bdi_dl_")
    logger = DualStreamLogger(d, human_interval=1)
    logger.maybe_format_human(1, "RUNNING", {}, "goal", "intent", 0.5)
    assert os.path.exists(logger.human_log_path)
    content = open(logger.human_log_path).read()
    assert "Cycle #1" in content


def test_stats():
    d = tempfile.mkdtemp(prefix="bdi_dl_")
    logger = DualStreamLogger(d)
    logger.log_cycle(1, {}, "d", "i", 0.5)
    logger.log_cycle(2, {}, "d", "i", 0.5)
    stats = logger.stats()
    assert stats["cycles"] == 2
    assert stats["errors"] == 0
    assert stats["engine_log_bytes"] > 0


def test_prune_engine_log():
    d = tempfile.mkdtemp(prefix="bdi_dl_")
    logger = DualStreamLogger(d, max_engine_lines=3)
    for i in range(10):
        logger.log_cycle(i, {}, "d", "i", 0.5)
    with open(logger.engine_log_path) as f:
        lines = f.readlines()
    assert len(lines) <= 3


def test_read_human_log():
    d = tempfile.mkdtemp(prefix="bdi_dl_")
    logger = DualStreamLogger(d, human_interval=1)
    logger.maybe_format_human(1, "RUNNING", {}, "d", "i", 0.5)
    logger.maybe_format_human(2, "COMMIT", {}, "d2", "i2", 0.99)
    log = logger.read_human_log(tail=2)
    assert "Cycle #1" in log
    assert "Cycle #2" in log
    assert "COMMIT" in log


def test_force_human_always_writes():
    d = tempfile.mkdtemp(prefix="bdi_dl_")
    logger = DualStreamLogger(d, human_interval=1000)
    card = logger.force_human(42, "DONE", {"result": "pass"},
                              "complete", "push_to_main", 1.0,
                              hash_sig="abc123def456")
    assert card is not None
    assert "STATUS: [DONE]" in card
    assert "Hash: abc123de" in card
    assert "Nash Score: 1.00/1.00" in card
