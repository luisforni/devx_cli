from __future__ import annotations
from pathlib import Path
import typer
from rich import print
from rich.table import Table
from devx.core import logging as log
from .runner import run_lint_pipeline

app = typer.Typer(help="Lint + formateo + complejidad con rama Git opcional")

@app.command("run")
def run(
    path: Path = typer.Argument(".", help="Ruta del proyecto a analizar"),
    fix: bool = typer.Option(False, "--fix", help="Aplica autofix (ruff --fix + black)"),
    only: str = typer.Option("auto", "--only", help="auto|ruff|black|cc"),
    max_complexity: int = typer.Option(10, "--max-complexity", help="Umbral para resaltar complejidad"),
    git: bool = typer.Option(True, "--git/--no-git", help="Si --fix, crear rama y commitear cambios"),
    git_prefix: str = typer.Option("_fix/lint-", "--git-prefix", help="Prefijo para la rama de autofix"),
    git_snapshot: bool = typer.Option(True, "--git-snapshot/--no-git-snapshot", help="Commit snapshot previo si hay cambios sin confirmar"),
):
    _ = log.setup()
    path = path.resolve()

    print(f"[bold]🧹 Lint @[/bold] {path}")

    res = run_lint_pipeline(
        target=path,
        fix=fix,
        only=only,
        use_git=git,
        git_snapshot_before=git_snapshot,
        git_branch_prefix=git_prefix,
    )

    if only in ("auto", "ruff"):
        if res.ruff_issues:
            table = Table(title="Ruff issues")
            table.add_column("File")
            table.add_column("Line:Col", justify="right")
            table.add_column("Code")
            table.add_column("Message")
            for it in res.ruff_issues:
                fn = it.get("filename", "?")
                loc = it.get("location") or {}
                linecol = f"{loc.get('row','?')}:{loc.get('column','?')}"
                code = it.get("code", "")
                msg = it.get("message", "")
                table.add_row(fn, linecol, code, msg)
            print(table)
        else:
            print("✅ Ruff: sin hallazgos." if res.ruff_ok else "⚠ Ruff: problemas sin salida parseable.")

    if only in ("auto", "black"):
        if fix:
            print("🖊️  Black: aplicado formateo." if res.black_ok else f"⚠ Black: {res.black_output}")
        else:
            if res.black_ok:
                print("✅ Black: formato correcto.")
            else:
                print("⚠ Black: archivos sin formatear.\n")
                if res.black_output:
                    print(res.black_output)

    if only in ("auto", "cc"):
        items = res.radon_items or []
        if items:
            flagged = [i for i in items if (i.get("complexity") or 0) > max_complexity]
            table = Table(title=f"Complejidad ciclomática (umbral > {max_complexity})")
            table.add_column("File"); table.add_column("Name"); table.add_column("Type")
            table.add_column("Complexity", justify="right"); table.add_column("Line(s)", justify="right")
            for i in flagged or items[:10]:
                lines = f"{i.get('lineno')}–{i.get('endline')}"
                table.add_row(i.get("file","?"), i.get("name","?"), i.get("type","?"),
                              str(i.get("complexity","?")), lines)
            print(table)
        else:
            print("✅ Radon: sin elementos o complejidad baja.")

    if fix and git:
        if res.created_branch:
            print(f"🌿 Git: rama creada → [bold]{res.created_branch}[/]")
        if res.committed:
            print("✅ Git: cambios de lint/formateo commiteados.")
        else:
            print("ℹ️  Git: no hubo cambios para commitear (o no es repo).")

    any_issue = False
    if (only in ("auto", "ruff") and res.ruff_issues) or \
       (only in ("auto", "black") and not res.black_ok) or \
       (only in ("auto", "cc") and any((i.get('complexity') or 0) > max_complexity for i in res.radon_items)):
        any_issue = True

    if any_issue and not fix:
        raise typer.Exit(code=1)
