import json
from pathlib import Path
from typer.testing import CliRunner
from devx.services.depgraph.cli import app

def write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

def test_cli_json_goes_to_reports_when_no_dir_given(tmp_path: Path, monkeypatch):
    pkg = tmp_path / "proj" / "devx"
    write(pkg / "__init__.py", "")
    write(pkg / "mod.py", "import sys\n")

    monkeypatch.chdir(tmp_path / "proj")

    runner = CliRunner()
    result = runner.invoke(app, ["--out", "deps.json", "--no-include-externals"])
    assert result.exit_code == 0, result.output

    target = Path("reports/depgraph/deps.json")
    assert target.exists(), "El JSON no se guardó en reports/depgraph/deps.json"
    data = json.loads(target.read_text(encoding="utf-8"))
    assert "nodes" in data and "edges" in data and "cycles" in data
    assert any(n == "devx.mod" or n.startswith("devx.mod") for n in data["nodes"])

def test_cli_ignore_option(tmp_path: Path, monkeypatch):
    root = tmp_path / "workspace"
    write(root / "pkg" / "__init__.py", "")
    write(root / "pkg" / "a.py", "import pkg.b\n")
    write(root / "pkg" / "b.py", "pass\n")
    write(root / "node_modules" / "foo.py", "import os\n")
    write(root / "build" / "bar.py", "import sys\n")

    monkeypatch.chdir(root)

    runner = CliRunner()
    args = ["--out", "deps.json", "--ignore", "node_modules", "--ignore", "build", "--no-include-externals"]
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output

    data = json.loads(Path("reports/depgraph/deps.json").read_text(encoding="utf-8"))
    assert not any("node_modules" in n for n in data["nodes"])
    assert not any("build" in n for n in data["nodes"])
    assert any(n == "pkg.a" or n.startswith("pkg.a") for n in data["nodes"])
    assert any(n == "pkg.b" or n.startswith("pkg.b") for n in data["nodes"])
