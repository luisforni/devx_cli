import os
import shutil
import subprocess
import tempfile
from pathlib import Path
import pytest
from devx.services.lint.runner import run_lint_pipeline, git_is_repo

@pytest.fixture
def temp_project(tmp_path: Path) -> Path:
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "bad.py").write_text("import os\n\ndef add(x,y):return x+y\n")
    return proj

def test_lint_detects_issues(temp_project: Path):
    result = run_lint_pipeline(temp_project, fix=False, only="auto", use_git=False)
    assert result.ruff_issues, "Ruff debería reportar issues (p.ej. F401)"
    assert result.black_ok is False

def test_lint_fix_modifies_file(temp_project):
    bad_file = temp_project / "bad.py"
    original = bad_file.read_text()

    result = run_lint_pipeline(temp_project, fix=True, only="auto", use_git=False)
    fixed = bad_file.read_text()

    assert fixed != original
    assert result.black_ok

def test_lint_with_git_branch_and_commit(temp_project):
    subprocess.run(["git", "init"], cwd=temp_project, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=temp_project, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=temp_project, check=True)
    subprocess.run(["git", "add", "-A"], cwd=temp_project, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=temp_project, check=True)

    assert git_is_repo(temp_project)

    result = run_lint_pipeline(temp_project, fix=True, use_git=True)

    assert result.created_branch is not None
    assert result.committed
