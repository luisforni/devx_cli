import typer
from rich.table import Table
from rich import print
from devx.core import logging as log
from .crawler import crawl

app = typer.Typer()

@app.command("run")
def run(
    url: str = typer.Argument(...),
    limit: int = typer.Option(100),
    timeout: float = typer.Option(10.0),
):
    _ = log.setup()
    broken = crawl(url, limit=limit, timeout=timeout)
    if not broken:
        print("✅ No broken links.")
        return
    table = Table(title="Broken / problematic links")
    table.add_column("URL")
    table.add_column("Status", justify="right")
    for u, s in broken:
        table.add_row(u, str(s))
    print(table)
