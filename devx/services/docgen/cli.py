from pathlib import Path
import typer
from rich import print
from devx.core import logging as log
from .generator import extract

app = typer.Typer()

@app.command("run")
def run(
    path: Path = typer.Argument(".", help="Project root"),
    out: Path = typer.Option(Path("DOCS.md"), help="Output file"),
):
    _ = log.setup()
    path = path.resolve()
    chunks = []
    for p in path.rglob("*.py"):
        try:
            chunks.append(extract(p))
        except Exception:
            pass
    content = ("\n\n---\n\n".join(chunks)).strip() or "# Documentation\n\nEmpty."
    out.write_text(content, encoding="utf-8")
    print(f"📄 Docs generated at {out}")
