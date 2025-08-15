from pathlib import Path

def bytes_to_mb(n: int) -> float:
    return n / 1024 / 1024

def iter_files(root: Path):
    for p in root.rglob("*"):
        if p.is_file():
            yield p
