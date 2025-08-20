import asyncio
import types
from devx.services.loadtest.engine import run_load

class DummyResponse:
    def __init__(self, status_code=200):
        self.status_code = status_code

class DummyAsyncClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def request(self, method, url, headers=None, json=None, content=None):
        if "fail" in url:
            return DummyResponse(500)
        return DummyResponse(200)

def test_run_load_ok(monkeypatch):
    import devx.services.loadtest.engine as eng

    monkeypatch.setattr(
        eng, "httpx", types.SimpleNamespace(AsyncClient=DummyAsyncClient)
    )

    lat, codes, errors = asyncio.run(
        run_load(
            url="https://service.ok",
            rps=5,
            duration=1,
            method="GET",
            timeout=5.0,
            headers={},
            body=None,
            verify_ssl=True,
        )
    )
    assert len(codes) == 5
    assert all(200 <= c < 300 for c in codes)
    assert errors == 0

def test_run_load_with_errors(monkeypatch):
    import devx.services.loadtest.engine as eng

    monkeypatch.setattr(
        eng, "httpx", types.SimpleNamespace(AsyncClient=DummyAsyncClient)
    )

    lat, codes, errors = asyncio.run(
        run_load(
            url="https://service.fail",
            rps=3,
            duration=1,
            method="GET",
            timeout=5.0,
            headers={},
            body=None,
            verify_ssl=True,
        )
    )
    assert len(codes) == 3
    assert all(c == 500 for c in codes)
    assert errors == 0
