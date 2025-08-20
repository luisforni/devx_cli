from __future__ import annotations

from pathlib import Path
from typer.testing import CliRunner
from devx.services.dockercheck.analyzer import analyze_dockerfile
from devx.services.dockercheck.cli import app as docker_app
from devx.services.dockercheck import runner as docker_runner

def _write(p: Path, content: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")

def test_analyzer_static_rules(tmp_path: Path):
    dockerfile = tmp_path / "Dockerfile"
    _write(dockerfile, """
        FROM python:3.11-slim
        RUN apt-get update
        RUN pip install flask
        COPY . .
        CMD ["python","app.py"]
    """)
    report = analyze_dockerfile(dockerfile)
    codes = {f.code for f in report.findings}
    assert "DKR001" in codes
    assert "DKR002" in codes
    assert "DKR004" in codes
    assert "DKR005" in codes
    assert "DKR006" in codes

def test_cli_static_only_no_docker(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(docker_runner, "_docker_available", lambda: False)

    dockerfile = (tmp_path / "Dockerfile")
    _write(dockerfile, """
        FROM python:3.11-slim
        RUN pip install --no-cache-dir flask
        USER app
        COPY . .
    """)

    runner = CliRunner()
    out_dir = (tmp_path / "out").resolve()

    result = runner.invoke(
        docker_app,
        [
            str(dockerfile.resolve()),
            "--no-build",
            "--json-out", str(out_dir),
            "--workdir", str(tmp_path.resolve()),
        ],
    )

    assert result.exit_code in (0, 2), result.output

    expected = out_dir / "dockercheck.json"
    if not expected.exists():
        json_line = next((l for l in result.output.splitlines() if l.startswith("💾 JSON:")), "")
        assert json_line, f"No se encontró línea de JSON en salida:\n{result.output}"
        expected = Path(json_line.split("💾 JSON:", 1)[1].strip())

    assert expected.exists(), f"No existe JSON en {expected}\nSalida:\n{result.output}"
