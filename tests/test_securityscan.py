import json
from datetime import datetime, timedelta
try:
    from datetime import UTC
except ImportError:
    from datetime import timezone
    UTC = timezone.utc

import respx
import httpx
from typer.testing import CliRunner

from devx.services.securityscan import analyzer as an
from devx.services.securityscan import cli as cli_mod

TEST_URL = "https://example.com"

def test_analyze_headers_missing_and_weak():
    headers = httpx.Headers({"X-Content-Type-Options": "invalid"})
    issues = an.analyze_headers(TEST_URL, headers)
    kinds = {(t, h) for (t, h, _d) in issues}
    assert ("weak", "X-Content-Type-Options") in kinds
    assert ("missing", "Content-Security-Policy") in kinds
    assert ("missing", "Strict-Transport-Security") in kinds
    assert ("missing", "Referrer-Policy") in kinds
    assert ("missing", "Cross-Origin-Opener-Policy") in kinds
    assert ("missing", "Permissions-Policy") in kinds
    assert ("missing", "X-Frame-Options") in kinds

def test_analyze_cookies_flags():
    headers = httpx.Headers({"Set-Cookie": "sessionid=abc; Path=/; Secure"})
    issues = an.analyze_cookies(headers)
    texts = [d for (_t, _c, d) in issues]
    assert any("HttpOnly" in x for x in texts)
    assert any("SameSite" in x for x in texts)
    assert not any("Secure (solo sobre HTTPS)" in x for x in texts)

def test_analyze_meta_http_equiv_detects():
    html = """
    <html><head>
      <meta http-equiv="Content-Security-Policy" content="default-src 'self'">
      <meta http-equiv="Referrer-Policy" content="no-referrer">
    </head><body></body></html>
    """
    meta = an.analyze_meta_http_equiv(html)
    assert meta["Content-Security-Policy"] == "default-src 'self'"
    assert meta["Referrer-Policy"] == "no-referrer"

def test_fingerprint_detects_and_leaks():
    headers = httpx.Headers({"Server": "nginx/1.23.4", "X-Powered-By": "Express"})
    techs, leaks = an.fingerprint(headers)
    assert "nginx" in [t.lower() for t in techs]
    assert any(k == "Server" for k, _ in leaks)

@respx.mock
def test_fetch_headers_http1_fallback():
    respx.head(f"{TEST_URL}/").mock(return_value=httpx.Response(405))
    respx.get(f"{TEST_URL}/").mock(
        return_value=httpx.Response(200, headers={"Server": "Apache"})
    )
    status, headers, body = an.fetch_headers(
        TEST_URL,
        timeout=5.0,
        retries=1,
        force_http1=True,
        verify=True,
        fetch_body=False,
    )
    assert status == 200
    assert headers.get("Server") == "Apache"

def test_tls_info_and_analyze_tls(monkeypatch):
    class FakeSSock:
        def getpeercert(self):
            exp = (datetime.now(UTC) + timedelta(days=45)).strftime("%b %d %H:%M:%S %Y GMT")
            return {"notAfter": exp}

        def cipher(self):
            return ("TLS_AES_256_GCM_SHA384", "TLSv1.3", 256)

        def version(self):
            return "TLSv1.3"

        def close(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

    class FakeCtx:
        def wrap_socket(self, sock, server_hostname=None):
            return FakeSSock()

    class DummySock:
        def close(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

    monkeypatch.setattr(an.ssl, "create_default_context", lambda: FakeCtx())
    monkeypatch.setattr(an.socket, "create_connection", lambda *a, **k: DummySock())

    info = an.tls_info("example.com")
    assert info["version"] == "TLSv1.3"
    issues = an.analyze_tls(info)
    assert not issues

@respx.mock
def test_cli_run_writes_json(tmp_path, monkeypatch):
    respx.head(f"{TEST_URL}/").mock(return_value=httpx.Response(405))
    respx.get(f"{TEST_URL}/").mock(
        return_value=httpx.Response(
            200,
            headers={"Server": "nginx"},
            text="<html><head><meta http-equiv='Referrer-Policy' content='no-referrer'></head></html>",
        )
    )
    monkeypatch.setattr(cli_mod, "scan_ports", lambda host: [80, 443])
    fake_info = {
        "version": "TLSv1.3",
        "cipher": ("TLS_AES_256_GCM_SHA384", "", 256),
        "expires_at": None,
    }
    monkeypatch.setattr(cli_mod, "tls_info", lambda host, port: fake_info)
    monkeypatch.setattr(cli_mod, "analyze_tls", lambda info: [])

    runner = CliRunner()
    out_dir = tmp_path / "reportsdir"
    result = runner.invoke(
        cli_mod.app,
        ["run", TEST_URL, "--out-dir", str(out_dir), "--fetch-html", "--force-http1"],
    )
    assert result.exit_code in (0, 1, 2)
    files = list(out_dir.glob("*.json"))
    if result.exit_code in (0, 1):
        assert files
        payload = json.loads(files[0].read_text(encoding="utf-8"))
        assert payload["target"] == TEST_URL
        assert "findings" in payload and isinstance(payload["findings"], list)
