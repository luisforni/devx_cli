from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Optional

def _sh(cmd: list[str], cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, capture_output=True, text=True)

def _have(cmd: str) -> bool:
    return shutil.which(cmd) is not None

def git_is_repo(path: Path) -> bool:
    p = _sh(["git", "rev-parse", "--is-inside-work-tree"], cwd=path)
    return p.returncode == 0 and p.stdout.strip() == "true"

def git_has_uncommitted(path: Path) -> bool:
    p = _sh(["git", "status", "--porcelain"], cwd=path)
    return p.returncode == 0 and bool(p.stdout.strip())

def git_checkout_new_branch(path: Path, prefix: str = "_fix/lint-") -> Optional[str]:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = f"{prefix}{ts}"
    name = base
    idx = 1
    while True:
        p = _sh(["git", "show-ref", "--verify", f"refs/heads/{name}"], cwd=path)
        if p.returncode != 0:
            break
        idx += 1
        name = f"{base}-{idx}"
    p2 = _sh(["git", "checkout", "-b", name], cwd=path)
    return name if p2.returncode == 0 else None

def git_snapshot(path: Path, msg: str = "chore(lint): snapshot before autofix") -> bool:
    p1 = _sh(["git", "add", "-A"], cwd=path)
    if p1.returncode != 0:
        return False
    p2 = _sh(["git", "commit", "-m", msg], cwd=path)
    return p2.returncode in (0, 1)

def git_commit_all(path: Path, msg: str) -> bool:
    p1 = _sh(["git", "add", "-A"], cwd=path)
    if p1.returncode != 0:
        return False
    p2 = _sh(["git", "commit", "-m", msg], cwd=path)
    return p2.returncode == 0

def run_black(path: Path, fix: bool = False) -> Tuple[bool, str]:
    if not _have("black"):
        return False, "black no está instalado (pip install black)"
    args = ["black", str(path)]
    if not fix:
        args.insert(1, "--check")
        args.insert(2, "--diff")
    proc = _sh(args)
    ok = proc.returncode == 0
    out = (proc.stdout or "") + (("\n" + proc.stderr) if proc.stderr else "")
    return ok, out.strip()

def run_ruff(path: Path, fix: bool = False) -> Tuple[bool, List[dict], str]:
    if not _have("ruff"):
        return False, [], "ruff no está instalado (pip install ruff)"

    args = [
        "ruff", "check", str(path),
        "--output-format", "json",
        "--select", "E",
        "--select", "F",
    ]
    if fix:
        args.append("--fix")

    proc = _sh(args)
    raw = proc.stdout or "[]"

    issues: List[dict] = []
    try:
        issues = json.loads(raw)
    except json.JSONDecodeError:
        pass

    ok = proc.returncode == 0
    return ok, issues, raw

def run_radon_cc(path: Path) -> Tuple[bool, List[dict], str]:
    if not _have("radon"):
        return False, [], "radon no está instalado (pip install radon)"
    proc = _sh(["radon", "cc", "-s", "-j", str(path)])
    raw = proc.stdout or "{}"
    items: List[dict] = []
    try:
        data = json.loads(raw)
        for fname, lst in (data or {}).items():
            for entry in lst or []:
                items.append({
                    "file": fname,
                    "name": entry.get("name"),
                    "type": entry.get("type"),
                    "complexity": entry.get("complexity"),
                    "lineno": entry.get("lineno"),
                    "endline": entry.get("endline"),
                })
    except json.JSONDecodeError:
        pass
    ok = proc.returncode == 0 or bool(items)
    return ok, items, raw

@dataclass
class LintResult:
    ruff_ok: bool
    ruff_issues: List[dict]
    black_ok: bool
    black_output: str
    radon_ok: bool
    radon_items: List[dict]
    created_branch: Optional[str] = None
    committed: bool = False


def run_lint_pipeline(
    target: Path,
    fix: bool,
    only: str = "auto",
    use_git: bool = True,
    git_snapshot_before: bool = True,
    git_branch_prefix: str = "_fix/lint-",
    commit_message: str = "chore(lint): apply ruff --fix and black",
) -> LintResult:
    target = target.resolve()

    created_branch: Optional[str] = None
    committed = False

    if fix and use_git and git_is_repo(target):
        if git_has_uncommitted(target) and git_snapshot_before:
            git_snapshot(target)
        created_branch = git_checkout_new_branch(target, prefix=git_branch_prefix)

    do_ruff = (only in ("auto", "ruff"))
    do_black = (only in ("auto", "black"))
    do_cc = (only in ("auto", "cc"))

    ruff_ok, ruff_issues, _ruff_raw = (True, [], "")
    if do_ruff:
        ruff_ok, ruff_issues, _ruff_raw = run_ruff(target, fix=fix)

    black_ok, black_output = (True, "")
    if do_black:
        black_ok, black_output = run_black(target, fix=fix)

    radon_ok, radon_items, _radon_raw = (True, [], "")
    if do_cc:
        radon_ok, radon_items, _radon_raw = run_radon_cc(target)

    if fix and use_git and git_is_repo(target):
        committed = git_commit_all(target, commit_message)

    return LintResult(
        ruff_ok=ruff_ok,
        ruff_issues=ruff_issues,
        black_ok=black_ok,
        black_output=black_output,
        radon_ok=radon_ok,
        radon_items=radon_items,
        created_branch=created_branch,
        committed=committed,
    )
