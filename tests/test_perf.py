from pathlib import Path
import json
import textwrap
from typer.testing import CliRunner
from devx.services.perf.cli import app

def write(p: Path, content: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")

def test_perf_cprofile_saves_json(tmp_path):
    script = tmp_path / "work" / "script.py"
    code = textwrap.dedent("""\
        import math

        def busy(n):
            s = 0
            for i in range(n):
                s += math.sqrt(i)
            return s

        if __name__ == "__main__":
            busy(20000)
    """)
    write(script, code)

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(
            app,
            [str(script), "--limit", "5", "--out", "perf.json"]
        )
        assert result.exit_code == 0, result.output

        target = Path("reports") / "perf" / "perf.json"
        assert target.exists(), f"No se generó {target}"

        data = json.loads(target.read_text(encoding="utf-8"))
        assert isinstance(data, list) and len(data) > 0

        row = data[0]
        assert "function" in row
        assert ("calls" in row) or ("ncalls" in row)
        assert ("time" in row) or ("tottime" in row) or ("cumtime" in row)

        if "calls" in row:
            assert isinstance(row["calls"], int)
        if "ncalls" in row:
            assert isinstance(row["ncalls"], int)
        for k in ("time", "tottime", "cumtime"):
            if k in row:
                assert isinstance(row[k], (int, float))
