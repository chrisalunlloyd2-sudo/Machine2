"""Workspace heuristics + auto-repair of broken AST/type nodes."""
import sys, os, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bdi_fsm.workspace import (scan_python, scan_compiler, scan_html,
                               repair_python_source, repair_compiler_source,
                               repair_html_tags, auto_repair_workspace)


def test_scan_python_finds_syntax_error(tmp_path):
    bad = tmp_path / "bad.py"
    bad.write_text("def f(:\n    pass\n")
    r = scan_python(str(tmp_path))
    assert len(r) == 1 and r[0]["kind"] == "python-ast"
    assert "bad.py" in r[0]["file"]


def test_scan_python_skips_git_and_caches(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / ".git" / "broken.py").write_text("def f(:\n")
    (tmp_path / "__pycache__" / "broken.py").write_text("def f(:\n")
    (tmp_path / "ok.py").write_text("x = 1\n")
    assert scan_python(str(tmp_path)) == []


def test_repair_compiler_missing_semi():
    r = repair_compiler_source("x = 1 + 2 * 3")
    assert r["fixed"] and ";" in r["source"]


def test_repair_compiler_valid_untouched():
    r = repair_compiler_source("x = 1 + 2 * 3;")
    assert not r["fixed"] and r["source"].endswith(";")


def test_repair_compiler_undeclared_refused():
    r = repair_compiler_source("y = z + 1;")
    assert not r["fixed"]
    assert "no safe" in r["reason"]


def test_repair_python_balance():
    r = repair_python_source("x = [1, 2, 3")
    assert r["fixed"] and r["source"].endswith("]")


def test_repair_python_valid_untouched():
    r = repair_python_source("def f(a):\n    return a\n")
    assert not r["fixed"]


def test_repair_html_closes_tags():
    r = repair_html_tags("<div><p>hello</div>")
    assert r["fixed"] and r["source"].endswith("</p></div>")


def test_repair_html_script_content_ignored():
    # '<' inside JS is not a tag; script is raw content
    r = repair_html_tags("<script>if (a < b) {}</script><div></div>")
    assert not r["fixed"]


def test_auto_repair_writes_orig_backup(tmp_path):
    f = tmp_path / "broken.basm"
    f.write_text("x = 1 + 2 * 3")
    report = auto_repair_workspace(str(tmp_path), dry_run=False)
    assert len(report["repaired"]) == 1
    assert f.with_suffix(".basm.orig").exists()
    assert f.read_text().endswith(";")


def test_auto_repair_dry_run_writes_nothing(tmp_path):
    f = tmp_path / "broken.basm"
    f.write_text("x = 1 + 2 * 3")
    report = auto_repair_workspace(str(tmp_path), dry_run=True)
    assert len(report["repaired"]) == 1
    assert not f.with_suffix(".basm.orig").exists()
    assert f.read_text() == "x = 1 + 2 * 3"
