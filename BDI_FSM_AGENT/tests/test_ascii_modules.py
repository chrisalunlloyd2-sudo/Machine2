"""Daily ASCII module registry: deterministic rotation + every module renders."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "webui"))
from ascii_modules import module_for_day, frames_for, module_names
from datetime import date


def test_registry_has_five_modules():
    names = module_names()
    assert "sine_wave" in names and "warp_drive" in names
    assert len(names) >= 5


def test_day_zero_is_sine_wave():
    info = module_for_day(date(2026, 8, 16))
    assert info["name"] == "sine_wave"
    assert info["slot"] == 0


def test_rotation_advances_daily():
    d1 = module_for_day(date(2026, 8, 16))
    d2 = module_for_day(date(2026, 8, 17))
    d3 = module_for_day(date(2026, 8, 18))
    assert d2["name"] == "warp_drive"
    assert d3["name"] == "galaxy"
    assert d1["name"] != d2["name"] != d3["name"]


def test_rotation_cycles_without_dropping():
    names = module_names()
    for i in range(len(names) * 2):
        info = module_for_day(date(2026, 8, 16 + i))
        assert info["name"] in names


def test_every_module_renders_frames():
    for name in module_names():
        info, frames = frames_for(frames=6)
        assert len(frames) == 6
        for f in frames:
            assert isinstance(f, str) and len(f) > 50
            assert not f.startswith("# render error")


def test_warp_drive_has_starfield():
    info, frames = frames_for(date(2026, 8, 17), frames=3)
    assert info["name"] == "warp_drive"
    assert any("@" in f for f in frames)  # the center marker
