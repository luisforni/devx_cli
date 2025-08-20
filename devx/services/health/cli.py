from pathlib import Path
import typer
from rich.table import Table
from rich import print
from devx.core import logging as log
from .scanner import dir_size, large_files, env_usages, outdated
from dotenv import dotenv_values

app = typer.Typer()

@app.command("run")
def run(
    path: Path = typer.Argument(".", help="Project path"),
    large_mb: int = typer.Option(25, help="Large file threshold"),
):
    logger = log.setup()
    path = path.resolve()
    print(f"[bold]🔎 Health @[/bold] {path}")

    size_mb = dir_size(path) / 1024 / 1024
    print(f"• Project size: [bold]{size_mb:.2f} MB[/bold]")

    table = Table(title=f"Files ≥ {large_mb} MB")
    table.add_column("File")
    table.add_column("MB", justify="right")
    any_large = False
    for p, sz in large_files(path, large_mb):
        table.add_row(str(p.relative_to(path)), f"{sz/1024/1024:.2f}")
        any_large = True
    print(table if any_large else "• No large files found.")

    used = env_usages(path)
    env_file = path / ".env"
    provided = set(dotenv_values(env_file).keys()) if env_file.exists() else set()
    missing = [k for k in used if k not in provided]
    if used:
        print(f"• Env vars in code: {', '.join(used)}")
        print(
            "• .env coverage: "
            + (
                "✅ OK"
                if not missing
                else f"[yellow]missing[/yellow] → {', '.join(missing)}"
            )
        )

    out = outdated(path / "requirements.txt")
    print(
        "• Outdated deps: "
        + ("✅ none" if not out else f"[yellow]{', '.join(out)}[/yellow]")
    )
