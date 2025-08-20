from devx.services.health import scanner

def test_dir_size_and_large_files(temp_project):
    total = scanner.dir_size(temp_project)
    assert total > 1_000_000

    large = list(scanner.large_files(temp_project, min_mb=1))  # >=1MB
    assert any(p.name == "big.bin" for p, _ in large)

def test_env_usages_detects_vars(temp_project):
    keys = scanner.env_usages(temp_project)
    assert "API_URL" in keys
    assert "MISSING_VAR" in keys

def test_outdated_handles_missing_file(tmp_path):
    out = scanner.outdated(tmp_path / "requirements.txt")
    assert isinstance(out, list)
