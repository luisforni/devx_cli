import re
from pathlib import Path
import typer
from rich.table import Table
from rich import print
from devx.core import logging as log
from .rules import PATTERNS

app = typer.Typer()

@app.command("run")
def run(
    path: Path = typer.Argument(".", help="Repository path"),
    ignore: str = typer.Option(
        r"\.(png|jpg|jpeg|gif|pdf|zip|gz|tar|ico|lock|bin)$", help="Ignore regex"
    ),
):
    _ = log.setup()
    path = path.resolve()
    compiled_ignore = re.compile(ignore)
    findings = []

    for p in path.rglob("*"):
        if p.is_dir():
            continue
        if compiled_ignore.search(p.suffix or ""):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for name, pat in PATTERNS.items():
            for m in re.finditer(pat, text):
                val = m.group(0)
                snippet = (val[:60] + "…") if len(val) > 60 else val
                findings.append((name, str(p.relative_to(path)), snippet))

    if not findings:
        print("✅ No potential secrets found.")
        return

    table = Table(title="Potential secrets")
    table.add_column("Type")
    table.add_column("File")
    table.add_column("Match")
    for t, f, s in findings:
        table.add_row(t, f, s)
    print(table)
