from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

@dataclass
class CoverageFile:
    path: str
    statements: int
    missing: int
    percent: float

@dataclass
class CoverageResult:
    total_percent: float
    files: List[CoverageFile]
    json_path: Path
    pytest_stdout: str
    pytest_stderr: str
    exit_code: int

def _run(cmd: list[str], cwd: Optional[Path] = None, env: Optional[dict] = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        env=env or os.environ.copy(),
    )

def run_pytest_coverage(
    tests_path: str | Path = "tests",
    cov_targets: Tuple[str, ...] = (".",),
    reports_dir: Optional[Path] = None,
    extra_pytest_args: Optional[List[str]] = None,
    workdir: Optional[Path] = None,
) -> CoverageResult:
    repo_root = Path(__file__).resolve().parents[3]
    tp = Path(tests_path)

    if workdir is not None:
        base = Path(workdir).resolve()
    elif tp.exists():
        # si tests_path es ".../tmpdir/tests" -> cwd = ".../tmpdir"
        base = tp.resolve().parent
    else:
        base = repo_root

    if reports_dir is None:
        reports = base / "reports" / "coverage"
    else:
        reports = Path(reports_dir)
        if not reports.is_absolute():
            reports = (base / reports).resolve()
    reports.mkdir(parents=True, exist_ok=True)
    json_path = reports / "coverage.json"

    cmd = ["pytest", str(tp if tp.is_absolute() else str(tp)), "--maxfail=1", "--disable-warnings", "-q"]
    for target in cov_targets:
        cmd += ["--cov", target]
    cmd += ["--cov-report=term-missing:skip-covered", f"--cov-report=json:{json_path}"]
    if extra_pytest_args:
        cmd += extra_pytest_args

    env = os.environ.copy()
    py_path = [str(base)]
    if env.get("PYTHONPATH"):
        py_path.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(py_path)

    proc = _run(cmd, cwd=base, env=env)
    stdout, stderr, code = proc.stdout or "", proc.stderr or "", proc.returncode

    files: List[CoverageFile] = []
    total_percent = 0.0
    if json_path.exists():
        data = json.loads(json_path.read_text(encoding="utf-8"))
        totals = data.get("totals") or {}
        if "percent_covered" in totals:
            total_percent = float(totals["percent_covered"])
        else:
            total_percent = float(str(totals.get("percent_covered_display", "0")).rstrip("%") or 0)
        for fpath, info in (data.get("files") or {}).items():
            summary = info.get("summary") or {}
            pct = summary.get("percent_covered")
            if pct is None:
                pct = float(str(summary.get("percent_covered_display", "0")).rstrip("%") or 0)
            files.append(
                CoverageFile(
                    path=fpath,
                    statements=int(summary.get("num_statements", 0)),
                    missing=int(summary.get("missing_lines", 0)),
                    percent=float(pct),
                )
            )
        files.sort(key=lambda x: (x.percent, -x.statements))

    return CoverageResult(
        total_percent=total_percent,
        files=files,
        json_path=json_path,
        pytest_stdout=stdout.strip(),
        pytest_stderr=stderr.strip(),
        exit_code=code,
    )
