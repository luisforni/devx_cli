from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import json
import typer
from rich import print
from rich.table import Table
from rich.panel import Panel
from .profiler import profile_cprofile, profile_pyinstrument, rows_to_json

app = typer.Typer(help="Perf – Perfilador de rendimiento para scripts Python")

@app.command("run")
def run(
    script: Path = typer.Argument(..., exists=True, file_okay=True, dir_okay=False, readable=True, help="Script .py a ejecutar"),
    args: Optional[str] = typer.Option(None, "--args", help='Argumentos para el script (ej: --args "foo bar")'),
    limit: int = typer.Option(10, "--limit", help="Top N funciones más costosas"),
    sort_by: str = typer.Option("cumulative", "--sort", help='Orden: "cumulative" (default) o "time"'),
    use_pyinstrument: bool = typer.Option(False, "--pyinstrument/--no-pyinstrument", help="Usar pyinstrument si está disponible"),
    out: Optional[Path] = typer.Option(None, "--out", help="Guardar reporte (.json o .txt). Si es ruta simple, va a reports/perf"),
):
    print(f"[bold]⚡ perf[/bold] ejecutando: {script.resolve()}")

    script_args: List[str] = []
    if args:
        script_args = [x for x in args.split(" ") if x != ""]

    if use_pyinstrument:
        try:
            report_text = profile_pyinstrument(script, script_args)
        except Exception as e:
            print(f"[red]Error con pyinstrument:[/red] {e}")
            raise typer.Exit(code=1)

        if out:
            target = out if out.parent != Path(".") else Path("reports/perf") / out.name
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.suffix == "":
                target = target.with_suffix(".txt")
            target.write_text(report_text, encoding="utf-8")
            print(f"📝 Reporte pyinstrument guardado en: {target}")
        else:
            print(Panel(report_text, title="pyinstrument", expand=False))
        raise typer.Exit(code=0)

    try:
        rows = profile_cprofile(script, script_args, sort_by=sort_by, limit=limit)
    except Exception as e:
        print(f"[red]Error ejecutando el script:[/red] {e}")
        raise typer.Exit(code=1)

    table = Table(title=f"Top {limit} funciones (orden: {sort_by})")
    table.add_column("ncalls", justify="right")
    table.add_column("tottime", justify="right")
    table.add_column("cumtime", justify="right")
    table.add_column("location")
    table.add_column("function")

    for r in rows:
        table.add_row(
            str(r.ncalls),
            f"{r.tottime:.6f}",
            f"{r.cumtime:.6f}",
            f"{Path(r.filename).name}:{r.line}",
            r.func,
        )
    print(table)

    if out:
        target = out if out.parent != Path(".") else Path("reports/perf") / out.name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.suffix == "":
            target = target.with_suffix(".json")
        if target.suffix.lower() == ".json":
            payload = rows_to_json(rows)
            target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        else:
            content = "\n".join(
                f"{r.ncalls:>6}  tottime={r.tottime:.6f}  cumtime={r.cumtime:.6f}  {Path(r.filename).name}:{r.line}  {r.func}"
                for r in rows
            )
            target.write_text(content + "\n", encoding="utf-8")
        print(f"📝 Reporte guardado en: {target}")
