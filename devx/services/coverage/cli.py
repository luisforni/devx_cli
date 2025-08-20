from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, List
import typer
from rich import print
from rich.table import Table
from rich.panel import Panel

from devx.core import logging as log
from .runner import run_pytest_coverage

app = typer.Typer(help="Ejecuta pytest con cobertura y muestra tabla por archivo.")

@app.command("run")
def run(
    tests_args: Optional[List[str]] = typer.Argument(
        None,
        metavar="TESTS",
        help="Ruta(s) a tests (carpeta/archivo). Si se omite, usa 'tests'.",
        show_default=False,
    ),
    cov: list[str] = typer.Option(["."], "--cov", help="Módulo/ruta a medir (repetible)"),
    out_dir: Path | None = typer.Option(None, "--out-dir", help="Directorio para guardar JSON"),
    min_total: float = typer.Option(0.0, "--min-total", help="Falla si el total < umbral"),
    top: int = typer.Option(0, "--top", help="Mostrar solo los N archivos con menor cobertura (0 = todos)"),
    workdir: Path | None = typer.Option(None, "--workdir", help="CWD donde correr pytest"),
    show_external: bool = typer.Option(  # <-- NUEVO
        False, "--show-external",
        help="Mostrar también archivos fuera del proyecto (e.g. /tmp/pytest-*)."
    ),
):
    _ = log.setup()

    tests = (tests_args[-1] if tests_args else "tests")

    print(Panel.fit(
        f"[bold]🧪 Coverage[/bold]\nTests: {tests}\nTargets: {', '.join(cov)}",
        border_style="magenta",
    ))

    res = run_pytest_coverage(
        tests_path=tests,
        cov_targets=tuple(cov),
        reports_dir=out_dir,
        workdir=workdir,
    )

    def _in_project(path_str: str) -> bool:
        try:
            return Path(path_str).resolve().is_relative_to(Path.cwd().resolve())
        except Exception:
            return True

    rows = res.files if top <= 0 else res.files[:top]
    if not show_external:
        rows = [f for f in rows if _in_project(f.path)]

    if rows:
        table = Table(title="Cobertura por archivo")
        table.add_column("File")
        table.add_column("Stmts", justify="right")
        table.add_column("Miss", justify="right")
        table.add_column("Cover %", justify="right")
        for f in rows:
            table.add_row(f.path, str(f.statements), str(f.missing), f"{f.percent:.1f}")
        print(table)
    else:
        print("ℹ️ No se encontraron archivos con cobertura (¿targets correctos?).")

    print(f"📊 Total: [bold]{res.total_percent:.1f}%[/bold]")
    print(f"💾 JSON: {res.json_path}")

    if res.exit_code != 0 and (res.pytest_stdout or res.pytest_stderr):
        print("\n[red]Pytest output (resumen):[/red]")
        if res.pytest_stdout:
            print(res.pytest_stdout)
        if res.pytest_stderr:
            print(res.pytest_stderr)

    if res.exit_code != 0:
        raise typer.Exit(code=1)
    if min_total > 0 and res.total_percent < min_total:
        print(f"[yellow]⚠ Umbral no alcanzado ({res.total_percent:.1f}% < {min_total:.1f}%)")
        raise typer.Exit(code=2)

    res = run_pytest_coverage(
        tests_path=tests,
        cov_targets=tuple(cov),
        reports_dir=out_dir,
        workdir=workdir,
    )

    coverage_file = Path(".coverage")
    if coverage_file.exists():
        try:
            os.remove(coverage_file)
        except Exception as e:
            print(f"[yellow]⚠ No se pudo borrar .coverage: {e}")
            