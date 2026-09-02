from bdi_fsm.hooks import HookDispatcher, normalize_direction


def test_normalize_direction_forms():
    assert normalize_direction("ask_github") == "ask_github"
    assert normalize_direction("run ask_github") == "ask_github"
    assert normalize_direction("terminal: run ask_github") == "ask_github"
    assert normalize_direction("DO echo hello") == "hello"
    assert normalize_direction("") == ""


def test_dispatch_runs_bound_fn():
    d = HookDispatcher()
    d.bind("echo", lambda **c: {"result": c.get("text", ""), "quality": 0.9})
    r = d.run("run echo", text="hello")
    assert r["ok"] is True and r["result"] == "hello" and r["quality"] == 0.9


def test_unknown_hook_is_low_quality():
    d = HookDispatcher()
    r = d.run("nope")
    assert r["ok"] is False and r["quality"] == 0.0


def test_exception_caught():
    d = HookDispatcher()
    def boom(**c):
        raise RuntimeError("x")
    d.bind("boom", boom)
    r = d.run("boom")
    assert r["ok"] is False and "RuntimeError" in r["result"]


def test_bind_as_decorator():
    d = HookDispatcher()

    @d.bind("ping")
    def ping(**c):
        return {"result": "pong"}

    assert d.run("ping")["result"] == "pong"
    assert "ping" in d.names()
