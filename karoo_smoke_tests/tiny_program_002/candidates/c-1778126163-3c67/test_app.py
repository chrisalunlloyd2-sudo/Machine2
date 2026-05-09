from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import app


def test_sample_input_exists() -> None:
    assert Path("sample_input.json").exists()


def test_build_evidence() -> None:
    payload = app.build_evidence(app.load_input())
    assert payload["ok"] is True
    assert payload["template"]["template_id"] == "python_data_cli"
    assert payload["item_count"] == 2


def test_cli_outputs_json() -> None:
    completed = subprocess.run([sys.executable, "app.py"], capture_output=True, text=True, timeout=10)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["ok"] is True


if __name__ == "__main__":
    test_sample_input_exists()
    test_build_evidence()
    test_cli_outputs_json()
    print("PASS")
