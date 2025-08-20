from pathlib import Path
from devx.services.sbom.builder import parse_requirements, build_cyclonedx, build_spdx

def test_parse_requirements(tmp_path: Path):
    p = tmp_path / "requirements.txt"
    p.write_text("fastapi==0.111.0\nuvicorn>=0.30\n# comment\n", encoding="utf-8")
    pkgs = parse_requirements(p)
    assert any(x["name"] == "fastapi" for x in pkgs)
    assert any(x["name"] == "uvicorn" for x in pkgs)

def test_build_cyclonedx_and_spdx():
    pkgs = [{"name": "fastapi", "version": "0.111.0"}]
    cdx = build_cyclonedx(pkgs)
    spdx = build_spdx(pkgs)
    assert cdx["bomFormat"] == "CycloneDX"
    assert spdx["spdxVersion"].startswith("SPDX-")
