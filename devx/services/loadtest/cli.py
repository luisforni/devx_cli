import asyncio
import json
import typer
from rich import print
from rich.table import Table
from devx.core import logging as log
from .engine import run_load

app = typer.Typer()

@app.command("run")
def run(
    url: str = typer.Argument(..., help="Endpoint"),
    rps: int = typer.Option(10, help="Requests per second"),
    duration: int = typer.Option(10, help="Seconds"),
    method: str = typer.Option("GET"),
    timeout: float = typer.Option(10.0),
    data: str = typer.Option(None, help="Raw body or JSON"),
    headers: str = typer.Option(None, help="JSON headers"),
    verify_ssl: bool = typer.Option(True, help="Verify TLS"),
):
    _ = log.setup()
    hdrs = json.loads(headers) if headers else {}
    body = json.loads(data) if data and data.strip().startswith("{") else data

    print(f"[bold]🚀 Load test[/bold] {url} | {method} | {rps} rps x {duration}s")
    lat, codes, errors = asyncio.run(
        run_load(url, rps, duration, method, timeout, hdrs, body, verify_ssl)
    )

    total = rps * duration
    ok = sum(1 for c in codes if 200 <= c < 400)
    table = Table(title="Results")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Total", str(total))
    table.add_row("Success (2xx/3xx)", str(ok))
    table.add_row("Errors", str(errors + (total - ok - errors)))
    if lat:
        from statistics import mean, quantiles

        table.add_row("Mean (s)", f"{mean(lat):.4f}")
        table.add_row("P95 (s)", f"{quantiles(lat, n=20)[18]:.4f}")
        table.add_row("Max (s)", f"{max(lat):.4f}")
    print(table)
