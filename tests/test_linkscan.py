import types
from devx.services.linkscan.crawler import crawl

class DummyResp:
    def __init__(self, text="", status_code=200):
        self.text = text
        self.status_code = status_code

class DummyClient:
    def __init__(self, *args, **kwargs):
        self.pages = {
            "https://site.test": '<a href="/ok">ok</a> <a href="/broken">broken</a>',
            "https://site.test/ok": "<html><body>OK</body></html>",
            "https://site.test/broken": None,
        }

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get(self, url):
        page = self.pages.get(url)
        if page is None:
            return DummyResp("", 500)
        return DummyResp(page, 200)

def test_crawl_collects_broken(monkeypatch):
    import devx.services.linkscan.crawler as cr

    monkeypatch.setattr(cr, "httpx", types.SimpleNamespace(Client=DummyClient))
    broken = crawl("https://site.test", limit=10, timeout=2.0)
    assert any(url.endswith("/broken") and status == 500 for url, status in broken)
