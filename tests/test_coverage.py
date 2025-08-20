from __future__ import annotations
import sys
import json
import runpy
import pytest
from pathlib import Path
from typer.testing import CliRunner
from devx.services.coverage.runner import run_pytest_coverage
from devx.services.coverage.cli import app as coverage_app

def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

def _make_sample_project(root: Path) -> tuple[Path, Path]:
    pkg = root / "pkg"
    tests = root / "tests"

    _write(pkg / "__init__.py", "")
    _write(pkg / "util.py", "def add(a, b):\n    return a + b\n")

    _write(
        tests / "test_util.py",
        "from pkg.util import add\n\n"
        "def test_add():\n"
        "    assert add(2, 3) == 5\n",
    )
    return pkg, tests

def test_runner_creates_json_and_reports(tmp_path: Path):
    pkg, tests = _make_sample_project(tmp_path)

    out_dir = tmp_path / "reports"
    res = run_pytest_coverage(
        tests_path=tests,
        cov_targets=(str(pkg),),
        reports_dir=out_dir,
    )

    assert res.exit_code == 0, res.pytest_stdout or res.pytest_stderr

    assert res.json_path.exists()
    data = json.loads(res.json_path.read_text(encoding="utf-8"))
    assert "totals" in data and "files" in data
    assert res.total_percent >= 0.0

def test_cli_run_outputs_json(tmp_path: Path):
    pkg, tests = _make_sample_project(tmp_path)

    runner = CliRunner()
    out_dir = tmp_path / "out"

    result = runner.invoke(
        coverage_app,
        [
            "run",
            "--cov", str(pkg),
            "--out-dir", str(out_dir),
            "--min-total", "0",
            "--workdir", str(tmp_path),
            "--",
            str(tests),
        ],
    )
    assert result.exit_code == 0, result.output

    json_path = out_dir / "coverage.json"
    assert json_path.exists()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert "totals" in payload and "files" in payload

def test_main_module_runs_without_errors(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["devx", "--help"])
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("devx", run_name="__main__")
    assert exc.value.code == 0
