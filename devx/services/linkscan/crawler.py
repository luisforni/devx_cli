from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup
from collections import deque

def same_host(a: str, b: str) -> bool:
    return urlparse(a).netloc == urlparse(b).netloc

def crawl(url: str, limit=100, timeout=10.0):
    seen, queue, broken = set(), deque([url]), []
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        while queue and len(seen) < limit:
            current = queue.popleft()
            if current in seen:
                continue
            seen.add(current)
            try:
                r = client.get(current)
                if r.status_code >= 400:
                    broken.append((current, r.status_code))
                    continue
                soup = BeautifulSoup(r.text, "html.parser")
                for a in soup.select("a[href]"):
                    link = urljoin(current, a["href"])
                    if (
                        same_host(url, link)
                        and link.startswith(("http://", "https://"))
                        and link not in seen
                    ):
                        queue.append(link)
            except Exception:
                broken.append((current, "ERR"))
    return broken
