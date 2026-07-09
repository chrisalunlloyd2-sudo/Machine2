#!/usr/bin/env python3
"""
VIPER Global Dependency Downloader v1.0
=========================================
Global standard for all VIPER machines.
Run once to install everything needed for Machine 2.

Usage:
  python viper_dep_install.py          # Install all
  python viper_dep_install.py --check  # Check what's missing
  python viper_dep_install.py --fix    # Fix broken installs only
"""
import subprocess
import sys
import os
import importlib
import json
import datetime
from pathlib import Path

LOG = Path(r"C:\Users\viper\VIPER_JAVA_RISC\logs\dep_install.log")
PY = sys.executable


def log(msg: str, level: str = "INFO") -> None:
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] [{level}] {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def pip_install(packages: list[str], upgrade: bool = False) -> bool:
    cmd = [PY, "-m", "pip", "install", "-q", "--no-warn-script-location"]
    if upgrade:
        cmd.append("--upgrade")
    cmd.extend(packages)
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


def check_import(module: str) -> bool:
    try:
        importlib.import_module(module)
        return True
    except ImportError:
        return False


# ─── Dependency Manifest ──────────────────────────────────────────
DEPS = [
    # Core
    {"module": "flask",        "pip": "flask",         "category": "web"},
    {"module": "pypdf",        "pip": "pypdf",          "category": "docs"},
    {"module": "requests",     "pip": "requests",       "category": "http"},
    {"module": "aiohttp",      "pip": "aiohttp",        "category": "http"},
    {"module": "psutil",       "pip": "psutil",         "category": "system"},
    # Database
    {"module": "sqlite3",      "pip": None,             "category": "db"},      # stdlib
    # LLM / ML
    {"module": "transformers", "pip": "transformers",   "category": "ml"},
    {"module": "torch",        "pip": "torch --index-url https://download.pytorch.org/whl/cpu", "category": "ml"},
    {"module": "tokenizers",   "pip": "tokenizers",     "category": "ml"},
    # Karoo GP
    {"module": "karoo_gp",     "pip": "karoo-gp",       "category": "karoo"},
    {"module": "numpy",        "pip": "numpy",          "category": "ml"},
    {"module": "pandas",       "pip": "pandas",         "category": "ml"},
    # Code parsing (AST)
    {"module": "tree_sitter",  "pip": "tree-sitter",    "category": "ast"},
    # Email
    {"module": "smtplib",      "pip": None,             "category": "email"},   # stdlib
    # GitHub
    {"module": "github",       "pip": "PyGithub",       "category": "github"},
    # Monitoring
    {"module": "schedule",     "pip": "schedule",       "category": "util"},
    {"module": "watchdog",     "pip": "watchdog",       "category": "util"},
    # Optional: llama-cpp
    # {"module": "llama_cpp",  "pip": "llama-cpp-python --prefer-binary", "category": "ml"},
]

TOOL_CHECKS = [
    {"name": "git",  "cmd": ["git", "--version"]},
    {"name": "java", "cmd": ["java", "-version"]},
    {"name": "curl", "cmd": ["curl", "--version"]},
]


def check_tool(cmd: list[str]) -> bool:
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=5)
        return result.returncode == 0
    except Exception:
        return False


def run_check() -> dict:
    """Returns dict of {dep_name: bool} for all dependencies."""
    results = {}
    for dep in DEPS:
        mod = dep["module"]
        ok = check_import(mod)
        results[mod] = ok
    for tool in TOOL_CHECKS:
        ok = check_tool(tool["cmd"])
        results[tool["name"]] = ok
    return results


def install_all(skip_ml: bool = False) -> None:
    categories_skip = {"ml"} if skip_ml else set()
    failed = []
    skipped = []

    by_category: dict[str, list] = {}
    for dep in DEPS:
        cat = dep.get("category", "misc")
        by_category.setdefault(cat, []).append(dep)

    for cat, deps in by_category.items():
        if cat in categories_skip:
            log(f"Skipping category: {cat}", "SKIP")
            skipped.extend([d["module"] for d in deps])
            continue

        to_install = [d["pip"] for d in deps if d["pip"] and not check_import(d["module"])]
        if not to_install:
            log(f"[{cat}] All present ✓")
            continue

        log(f"[{cat}] Installing: {to_install}")
        for pkg in to_install:
            ok = pip_install([pkg])
            if ok:
                log(f"  ✅ {pkg}")
            else:
                log(f"  ❌ {pkg} FAILED", "ERROR")
                failed.append(pkg)

    if failed:
        log(f"\nFAILED: {failed}", "WARN")
    else:
        log("\n✅ All dependencies installed successfully!")

    if skipped:
        log(f"Skipped (ML): {skipped}")


def print_status() -> None:
    results = run_check()
    ok_count = sum(1 for v in results.values() if v)
    total = len(results)

    print(f"\n{'─'*50}")
    print(f"  VIPER Dependency Status ({ok_count}/{total} OK)")
    print(f"{'─'*50}")
    for name, ok in results.items():
        icon = "✅" if ok else "❌"
        print(f"  {icon}  {name}")
    print(f"{'─'*50}\n")


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="VIPER Global Dependency Installer")
    parser.add_argument("--check",    action="store_true", help="Check status only")
    parser.add_argument("--fix",      action="store_true", help="Install only missing")
    parser.add_argument("--no-ml",    action="store_true", help="Skip ML deps (torch, transformers)")
    args = parser.parse_args()

    log("VIPER Global Dep Installer v1.0")

    if args.check:
        print_status()
        return

    print_status()
    install_all(skip_ml=args.no_ml)
    print_status()


if __name__ == "__main__":
    main()
