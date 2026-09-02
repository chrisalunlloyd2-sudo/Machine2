import os
from bdi_fsm.delete_gate import allow_delete


def test_default_disabled():
    os.environ.pop("BDI_ALLOW_DELETE", None)
    assert allow_delete() is False


def test_enabled_when_set():
    os.environ["BDI_ALLOW_DELETE"] = "1"
    try:
        assert allow_delete() is True
    finally:
        os.environ.pop("BDI_ALLOW_DELETE", None)


def test_gate_importable():
    from bdi_fsm.delete_gate import allow_delete as f
    assert f() in (True, False)
