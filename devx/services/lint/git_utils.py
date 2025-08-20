import subprocess
import datetime
import os


def run_git(args, cwd):
    return subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
    )

def git_is_repo(path: str) -> bool:
    result = run_git(["rev-parse", "--is-inside-work-tree"], path)
    return result.returncode == 0

def git_has_changes(path: str) -> bool:
    result = run_git(["status", "--porcelain"], path)
    return bool(result.stdout.strip())

def git_snapshot(path: str) -> None:
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    branch = f"_snapshot/{ts}"
    run_git(["checkout", "-b", branch], path)
    run_git(["add", "-A"], path)
    run_git(["commit", "-m", f"snapshot before lint --fix ({ts})"], path)
    run_git(["checkout", "-"], path)

def git_create_branch(path: str, prefix: str = "_fix/lint") -> str:
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    branch = f"{prefix}-{ts}"
    run_git(["checkout", "-b", branch], path)
    return branch

def git_commit_all(path: str, message: str) -> None:
    run_git(["add", "-A"], path)
    run_git(["commit", "-m", message], path)
