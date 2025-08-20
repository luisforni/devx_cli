from __future__ import annotations

from datetime import datetime
try:
    from datetime import UTC
except ImportError:
    from datetime import timezone
    UTC = timezone.utc
import re
import socket
import ssl
import time
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse

import httpx
import tldextract
from bs4 import BeautifulSoup

META_SEC_HEADERS = {
    "content-security-policy": "Content-Security-Policy",
    "referrer-policy": "Referrer-Policy",
}

def analyze_meta_http_equiv(html: str) -> Dict[str, str]:
    results: Dict[str, str] = {}
    if not html:
        return results
    try:
        soup = BeautifulSoup(html, "html.parser")
        for meta in soup.find_all("meta"):
            hev = (
                (meta.get("http-equiv") or meta.get("http_equiv") or "").strip().lower()
            )
            if hev in META_SEC_HEADERS:
                val = meta.get("content")
                if isinstance(val, str):
                    results[META_SEC_HEADERS[hev]] = val.strip()
    except Exception:
        pass
    return results


try:
    H2_AVAILABLE = True
except Exception:
    H2_AVAILABLE = False

SEC_HEADERS_REQUIRED: List[str] = [
    "Content-Security-Policy",
    "X-Frame-Options",
    "X-Content-Type-Options",
    "Referrer-Policy",
    "Strict-Transport-Security",
    "Permissions-Policy",
    "Cross-Origin-Opener-Policy",
]

COMMON_WEB_PORTS: List[int] = [80, 443, 8080, 8443, 8000, 3000]

TECH_FINGERPRINT_PATTERNS: Dict[str, re.Pattern[str]] = {
    "Cloudflare": re.compile(r"cloudflare", re.I),
    "nginx": re.compile(r"nginx", re.I),
    "Apache": re.compile(r"apache", re.I),
    "Microsoft-IIS": re.compile(r"microsoft-iis", re.I),
    "Vercel": re.compile(r"vercel", re.I),
    "Netlify": re.compile(r"netlify", re.I),
    "Express": re.compile(r"express", re.I),
    "FastAPI": re.compile(r"fastapi", re.I),
}

def normalize_url(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        return "https://" + url
    return url

def target_host(url: str) -> str:
    u = urlparse(url)
    host = u.hostname or url
    ext = tldextract.extract(host)
    return ".".join(part for part in [ext.subdomain, ext.domain, ext.suffix] if part)

def fetch_headers(
    url: str,
    timeout: float = 10.0,
    retries: int = 3,
    force_http1: bool = False,
    verify: bool = True,
    fetch_body: bool = False,
) -> Tuple[int, httpx.Headers, str | None]:
    u = urlparse(url)
    if not u.path:
        url = url.rstrip("/") + "/"

    ua = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
    base_headers = {
        "User-Agent": ua,
        "Accept": "*/*",
        "Accept-Language": "en,es;q=0.9",
        "Connection": "close",
    }

    def _attempt(http2: bool) -> Tuple[int, httpx.Headers, str | None]:
        if http2 and not H2_AVAILABLE:
            http2 = False
        transport = httpx.HTTPTransport(retries=0)
        with httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            verify=verify,
            headers=base_headers,
            http2=http2,
            transport=transport,
        ) as client:
            try:
                r = client.head(url)
                if r.status_code >= 400 or not r.headers or fetch_body:
                    r = client.get(url)
            except Exception:
                r = client.get(url)
            return r.status_code, r.headers, (r.text if fetch_body else None)

    last_exc: Exception | None = None
    http2_plans = [False] if (force_http1 or not H2_AVAILABLE) else [True, False]

    for http2_flag in http2_plans:
        for i in range(max(1, retries)):
            try:
                return _attempt(http2=http2_flag)
            except Exception as e:
                last_exc = e
                time.sleep(min(0.25 * (i + 1), 1.0))

    try:
        with httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            verify=verify,
            headers=base_headers,
            http2=False,
        ) as client:
            r = client.get(url)
            return r.status_code, r.headers, (r.text if fetch_body else None)
    except Exception as e:
        last_exc = e

    raise last_exc if last_exc else RuntimeError("Unknown HTTP error")

def analyze_headers(url: str, headers: httpx.Headers) -> List[Tuple[str, str, str]]:
    issues: List[Tuple[str, str, str]] = []
    present = {h for h in headers.keys()}

    for h in SEC_HEADERS_REQUIRED:
        if h not in present:
            if h == "Strict-Transport-Security" and not url.lower().startswith(
                "https://"
            ):
                continue
            issues.append(("missing", h, "Header ausente"))

    xcto = headers.get("X-Content-Type-Options")
    if xcto is not None and xcto.lower() != "nosniff":
        issues.append(
            (
                "weak",
                "X-Content-Type-Options",
                f"Valor '{xcto or 'N/A'}' (recomendado: nosniff)",
            )
        )

    xfo = headers.get("X-Frame-Options")
    if xfo is not None and xfo.lower() not in ("deny", "sameorigin"):
        issues.append(
            (
                "weak",
                "X-Frame-Options",
                f"Valor '{xfo}' (recomendado: DENY o SAMEORIGIN)",
            )
        )

    csp = headers.get("Content-Security-Policy")
    if csp:
        if "unsafe-inline" in csp or "'unsafe-inline'" in csp:
            issues.append(("weak", "Content-Security-Policy", "Contiene unsafe-inline"))
        if "*" in csp and "script-src" in csp:
            issues.append(
                ("weak", "Content-Security-Policy", "script-src demasiado permisivo")
            )

    return issues

def analyze_cookies(headers: httpx.Headers) -> List[Tuple[str, str, str]]:
    issues: List[Tuple[str, str, str]] = []
    raw_list = headers.get_list("set-cookie") if hasattr(headers, "get_list") else []
    if not raw_list:
        raw = headers.get("set-cookie")
        if raw:
            raw_list = [line.strip() for line in str(raw).split("\n") if line.strip()]
    for ck in raw_list:
        name = ck.split("=", 1)[0].strip()
        flags = ck.lower()
        if "secure" not in flags:
            issues.append(
                ("weak", f"Set-Cookie {name}", "Falta flag Secure (solo sobre HTTPS)")
            )
        if "httponly" not in flags:
            issues.append(("weak", f"Set-Cookie {name}", "Falta flag HttpOnly"))
        if "samesite" not in flags:
            issues.append(
                ("weak", f"Set-Cookie {name}", "Falta flag SameSite (Lax/Strict)")
            )
    return issues

def tls_info(host: str, port: int = 443, timeout: float = 5.0) -> Dict[str, Any]:
    ctx = ssl.create_default_context()
    sock = socket.create_connection((host, port), timeout=timeout)
    try:
        ssock = ctx.wrap_socket(sock, server_hostname=host)
        try:
            cert = ssock.getpeercert()
            cipher = ssock.cipher()
            version = ssock.version()
        finally:
            try:
                ssock.close()
            except Exception:
                pass
    finally:
        try:
            sock.close()
        except Exception:
            pass
    not_after = cert.get("notAfter")
    exp = None
    if not_after is not None:
        parsed = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
        exp = parsed.replace(tzinfo=UTC)
    return {"version": version, "cipher": cipher, "expires_at": exp}

def analyze_tls(info: Dict[str, Any]) -> List[Tuple[str, str, str]]:
    issues: List[Tuple[str, str, str]] = []
    version = info.get("version", "")
    cipher = info.get("cipher", ("", "", 0))
    exp: datetime | None = info.get("expires_at")
    if version in ("TLSv1", "TLSv1.1", "SSLv3"):
        issues.append(("weak", "TLS", f"Protocolo {version} obsoleto."))
    if exp:
        days = (exp - datetime.now(UTC)).days
        if days <= 0:
            issues.append(("critical", "TLS Cert", "Certificado expirado"))
        elif days < 30:
            issues.append(("warn", "TLS Cert", f"Certificado expira en {days} días"))
    cipher_name = (cipher[0] or "").upper()
    if any(bad in cipher_name for bad in ("RC4", "3DES")):
        issues.append(("weak", "Cipher", f"Suite débil {cipher[0]}"))
    return issues

def scan_ports(
    host: str, ports: List[int] = COMMON_WEB_PORTS, timeout: float = 0.3
) -> List[int]:
    open_ports: List[int] = []
    for p in ports:
        s = socket.socket()
        try:
            s.settimeout(timeout)
            s.connect((host, p))
            open_ports.append(p)
        except Exception:
            pass
        finally:
            try:
                s.close()
            except Exception:
                pass
    return open_ports

def fingerprint(headers: httpx.Headers) -> Tuple[List[str], List[Tuple[str, str]]]:
    server = headers.get("Server", "") or ""
    x_powered = headers.get("X-Powered-By", "") or ""
    combined = f"{server} {x_powered}"
    techs = set()
    for name, pat in TECH_FINGERPRINT_PATTERNS.items():
        if pat.search(combined):
            techs.add(name)
    leaks: List[Tuple[str, str]] = []
    for k in ("Server", "X-Powered-By"):
        v = headers.get(k, "") or ""
        if re.search(r"\d+\.\d+(\.\d+)?", v):
            leaks.append((k, v))
    return sorted(techs), leaks
