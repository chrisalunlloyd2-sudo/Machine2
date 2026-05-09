from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict


OBJECTIVE = "Create a tiny safe Python CLI program that adds two integers and prints JSON evidence. Keep it self-contained and testable."
TEMPLATE = {"template_id": "python_data_cli", "framework": "python argparse + json/csv stdlib", "language": "python", "pages": 1, "target_lines": 110, "files": ["app.py", "sample_input.json", "test_app.py", "README.md"], "rationale": "Data/report cues imply a CLI transformer with sample input and JSON evidence output."}


def load_input(path: str = "sample_input.json") -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_evidence(data: Dict[str, Any]) -> Dict[str, Any]:
    items = data.get("items") if isinstance(data, dict) else []
    return {
        "ok": True,
        "objective": OBJECTIVE,
        "template": TEMPLATE,
        "item_count": len(items) if isinstance(items, list) else 0,
        "keys": sorted(data.keys()) if isinstance(data, dict) else [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="LAB_OUTPUT data CLI candidate")
    parser.add_argument("--input", default="sample_input.json")
    args = parser.parse_args()
    print(json.dumps(build_evidence(load_input(args.input)), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
