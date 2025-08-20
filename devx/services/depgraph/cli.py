from pathlib import Path
import json
from typing import List
import typer
from rich import print
from rich.table import Table
from .analyzer import analyze, to_dot, to_json, extend_ignored

app = typer.Typer(help="Dependency graph (imports) generator")

@app.command("run")
def run(
    path: Path = typer.Argument(
        Path("."),
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        help="Project root to analyze",
    ),
    out: Path = typer.Option("deps.json", "--out", help="Output file (.png/.svg/.dot/.json)"),
    include_externals: bool = typer.Option(
        True,
        "--include-externals/--no-include-externals",
        help="Include edges to external packages (default: true)",
    ),
    rankdir: str = typer.Option("LR", "--rankdir", help="Graph direction: LR / TB"),
    ignore: List[str] = typer.Option(
        None,
        "--ignore",
        help="Extra folders to ignore (repeatable, e.g. --ignore build --ignore dist)",
    ),
):
    path = path.resolve()
    print(f"[bold]🧭 DepGraph[/bold] scanning: {path}")

    if ignore:
        extend_ignored(ignore)

    nodes, edges, cycles = analyze(path, include_externals=include_externals)

    suffix = Path(out).suffix.lower()
    target = (
        out if Path(out).parent != Path(".") else Path("reports/depgraph") / Path(out).name
    )
    target.parent.mkdir(parents=True, exist_ok=True)

    if suffix in {".png", ".svg", ".dot"}:
        dot = to_dot(nodes, edges, rankdir=rankdir)
        if suffix == ".dot":
            target.write_text(dot, encoding="utf-8")
            print(f"📄 DOT written to {target}")
        else:
            try:
                from graphviz import Source
                src = Source(dot)
                src.format = "png" if suffix == ".png" else "svg"
                src.render(target.with_suffix(""), cleanup=True)
                final = target if target.exists() else target.with_suffix(suffix)
                print(f"📈 Graph written to {final}")
            except Exception:
                fallback = target.with_suffix(".dot")
                fallback.write_text(dot, encoding="utf-8")
                print(f"[yellow]Graphviz not available.[/yellow] DOT saved to {fallback}")

    elif suffix == ".json":
        data = to_json(nodes, edges, cycles)
        target.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"📄 JSON written to {target}")

    else:
        raise typer.BadParameter("Use .png, .svg, .dot, or .json")

    if cycles:
        table = Table(title="🔁 Dependency cycles found")
        table.add_column("#", justify="right")
        table.add_column("Cycle (modules)")
        for i, cyc in enumerate(cycles, 1):
            table.add_row(str(i), " → ".join(cyc + [cyc[0]]))
        print(table)
    else:
        print("✅ No dependency cycles detected.")
