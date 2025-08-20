import sys
from pathlib import Path
import asyncio
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_project(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "module").mkdir()
    (proj / ".env").write_text(
        "API_URL=https://example.com\nSECRET_KEY=abc\n", encoding="utf-8"
    )
    (proj / "requirements.txt").write_text(
        "typer==0.12.3\nrich==13.7.1\n", encoding="utf-8"
    )
    (proj / "module" / "app.py").write_text(
        "import os\nAPI=os.getenv('API_URL')\nX=os.getenv('MISSING_VAR')\n",
        encoding="utf-8",
    )
    big = proj / "big.bin"
    big.write_bytes(b"0" * (1150 * 1024))  # ~1.1MB
    return proj
