import re
import subprocess
import sys
from pathlib import Path
from devx.core.utils import iter_files

def dir_size(path: Path) -> int:
    return sum(p.stat().st_size for p in iter_files(path))

def large_files(path: Path, min_mb: int):
    for p in iter_files(path):
        try:
            sz = p.stat().st_size
            if sz >= min_mb * 1024 * 1024:
                yield p, sz
        except:
            pass

def env_usages(path: Path):
    pat = re.compile(r"os\.getenv\(['\"]([A-Za-z0-9_]+)['\"]")
    keys = set()
    for p in path.rglob("*.py"):
        try:
            keys |= set(pat.findall(p.read_text(encoding="utf-8", errors="ignore")))
        except:
            pass
    return sorted(keys)

def outdated(requirements: Path):
    if not requirements.exists():
        return []
    try:
        out = subprocess.check_output(
            [sys.executable, "-m", "pip", "list", "--outdated", "--format=freeze"],
            text=True,
        )
        outdated = {
            line.split("==")[0].lower() for line in out.splitlines() if "==" in line
        }
        req = {
            line.split("==")[0].strip().lower()
            for line in requirements.read_text().splitlines()
            if "==" in line
        }
        return sorted(req & outdated)
    except Exception:
        return []
