from __future__ import annotations
from pathlib import Path
import typer
from rich import print
from rich.table import Table
from rich.panel import Panel
from rich.box import HEAVY
from devx.core import logging as log
from .runner import run_dockercheck

app = typer.Typer(help="Audita Dockerfile e imágenes (best practices, tamaño, capas).")

@app.command("run")
def run(
    dockerfile: Path = typer.Argument(..., exists=True, dir_okay=False, help="Ruta al Dockerfile"),
    image: str | None = typer.Option(None, "--image", help="Tag para construir/inspeccionar"),
    max_size: str | None = typer.Option(None, "--max-size", help="Falla si supera este tamaño (ej. 500MB)"),
    no_build: bool = typer.Option(False, "--no-build", help="No construir imagen, solo auditoría estática"),
    workdir: Path | None = typer.Option(None, "--workdir", help="Directorio de contexto para build"),
    json_out: Path | None = typer.Option(None, "--json-out", help="Directorio para guardar dockercheck.json"),
):
    _ = log.setup()

    dockerfile = dockerfile.resolve()
    workdir = workdir.resolve() if workdir else None
    json_out = json_out.resolve() if json_out else None

    print(Panel.fit(f"[bold]🐳 DockerCheck[/bold]\nDockerfile: {dockerfile}", border_style="cyan"))

    res = run_dockercheck(
        dockerfile=dockerfile,
        image_tag=image,
        do_build=not no_build,
        workdir=workdir,
        json_out_dir=json_out,
    )

    table = Table(title="Hallazgos (estático)", box=HEAVY)
    table.add_column("Nivel"); table.add_column("Código"); table.add_column("Mensaje"); table.add_column("Sugerencia")
    for f in res.static.findings:
        table.add_row(f.level, f.code, f.message, f.advice)
    if res.static.findings: print(table)
    else: print("✅ Sin hallazgos estáticos relevantes.")

    if res.build.image:
        size_mb = (res.build.image_size_bytes or 0) / 1_000_000
        print(f"\n📦 Imagen: [bold]{res.build.image}[/bold]  |  Tamaño: [bold]{size_mb:.1f} MB[/bold]")
    else:
        print("ℹ️ Build deshabilitado o Docker no disponible; solo auditoría estática.")

    print(f"💾 JSON: {res.json_path}")

    exit_code = 0
    if any(f.level == "ERROR" for f in res.static.findings):
        exit_code = 1

    if max_size and res.build.image_size_bytes:
        def parse_limit(s: str) -> int:
            s = s.strip().upper()
            if s.endswith("GB"): return int(float(s[:-2]) * 1_000_000_000)
            if s.endswith("MB"): return int(float(s[:-2]) * 1_000_000)
            if s.endswith("KB"): return int(float(s[:-2]) * 1_000)
            return int(s)
        limit = parse_limit(max_size)
        if res.build.image_size_bytes > limit:
            print(f"[yellow]⚠ Tamaño {res.build.image_size_bytes/1_000_000:.1f} MB supera límite {limit/1_000_000:.1f} MB")
            exit_code = max(exit_code, 2)

    raise typer.Exit(code=exit_code)
