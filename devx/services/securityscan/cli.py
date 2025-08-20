import json
import logging
import datetime
from pathlib import Path
import typer
from rich import print
from rich.table import Table
from rich.panel import Panel

from devx.core import logging as log
from devx.core.config import ROOT, get as cfg_get
from .analyzer import (
    normalize_url,
    fetch_headers,
    analyze_headers,
    analyze_cookies,
    analyze_meta_http_equiv,
    tls_info,
    analyze_tls,
    target_host,
    scan_ports,
    fingerprint,
    H2_AVAILABLE,
)

app = typer.Typer(help="Scan basic web vulnerabilities (headers, cookies, TLS, ports).")

def _severity_for(item_type: str, header_or_area: str) -> str:
    if item_type == "critical":
        return "critical"
    if header_or_area in ("TLS Cert",):
        return "warn"
    if item_type == "missing":
        return "medium"
    if item_type == "weak":
        return "low"
    return "info"

def _resolve_reports_dir(out_dir_opt: str | None) -> Path:
    if out_dir_opt:
        base = Path(out_dir_opt)
    else:
        env_dir = cfg_get("DEVX_REPORTS_DIR")
        if env_dir:
            base = Path(env_dir) / "securityscan"
        else:
            base = Path(ROOT) / "reports" / "securityscan"
    base.mkdir(parents=True, exist_ok=True)
    return base

def _compose_output_path(
    reports_dir: Path, host: str, json_out_opt: str | None
) -> Path:
    if json_out_opt:
        p = Path(json_out_opt)
        if p.is_absolute():
            return p
        name = p.name if p.suffix == ".json" else f"{p.name}.json"
        return reports_dir / name
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    host_slug = host.replace(".", "_")
    return reports_dir / f"{host_slug}_{ts}.json"

@app.command("run")
def run(
    url: str = typer.Argument(..., help="Target site (https://example.com)"),
    timeout: float = typer.Option(10.0, help="HTTP timeout seconds"),
    quick: bool = typer.Option(False, help="Skip port scan & TLS check (HTTP-only)"),
    retries: int = typer.Option(3, help="HTTP retries/backoff"),
    force_http1: bool = typer.Option(False, help="Force HTTP/1.1 (disable HTTP/2)"),
    no_verify: bool = typer.Option(False, help="Disable TLS verify (testing only)"),
    json_out: str = typer.Option(
        None, "--json", help="Output JSON file name or absolute path"
    ),
    out_dir: str = typer.Option(
        None,
        "--out-dir",
        help="Directory to store reports (overrides DEVX_REPORTS_DIR)",
    ),
    fetch_html: bool = typer.Option(
        False,
        "--fetch-html",
        help="Fetch HTML and detect <meta http-equiv> CSP/Referrer-Policy",
    ),
):
    logger = log.setup()
    logging.getLogger("httpx").setLevel(logging.WARNING)

    url = normalize_url(url)
    host = target_host(url)
    reports_dir = _resolve_reports_dir(out_dir)
    out_path = _compose_output_path(reports_dir, host, json_out)

    findings = []
    wrote = False

    http_proto_note = (
        "(HTTP/1.1)" if (force_http1 or not H2_AVAILABLE) else "(HTTP/2→1.1 fallback)"
    )
    print(
        Panel.fit(
            f"[bold]🛡️ Security Scan[/bold] {http_proto_note}\n{url}",
            border_style="cyan",
        )
    )

    try:
        try:
            status, headers, html = fetch_headers(
                url,
                timeout=timeout,
                retries=retries,
                force_http1=force_http1,
                verify=(not no_verify),
                fetch_body=fetch_html,
            )
        except Exception as e:
            print(f"[red]✗ Error HTTP[/red]: {e}")
            payload = {
                "target": url,
                "http_version": "1.1" if (force_http1 or not H2_AVAILABLE) else "2.0",
                "error": str(e),
                "findings": [],
            }
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            print(f"💾 Reporte JSON guardado en: {out_path}")
            wrote = True
            raise typer.Exit(code=1)

        header_issues = analyze_headers(url, headers)
        meta_overrides = {}
        if fetch_html and html:
            meta_overrides = analyze_meta_http_equiv(html)
            for k, v in meta_overrides.items():
                header_issues = [
                    i for i in header_issues if not (i[0] == "missing" and i[1] == k)
                ]

        if header_issues:
            table_h = Table(title="HTTP Security Headers")
            table_h.add_column("Type")
            table_h.add_column("Header")
            table_h.add_column("Detail")
            for t, h, d in header_issues:
                table_h.add_row(t.upper(), h, d)
                findings.append(
                    {
                        "type": t,
                        "area": "header",
                        "name": h,
                        "detail": d,
                        "severity": _severity_for(t, h),
                    }
                )
            print(table_h)
        else:
            print("✅ Headers: sin hallazgos críticos.")

        if meta_overrides:
            table_m = Table(title="Meta http-equiv detected")
            table_m.add_column("Header")
            table_m.add_column("Value")
            for k, v in meta_overrides.items():
                table_m.add_row(k, v)
            print(table_m)

        cookie_issues = analyze_cookies(headers)
        if cookie_issues:
            table_c = Table(title="Cookie Flags")
            table_c.add_column("Type")
            table_c.add_column("Cookie")
            table_c.add_column("Detail")
            for t, c, d in cookie_issues:
                table_c.add_row(t.upper(), c, d)
                findings.append(
                    {
                        "type": t,
                        "area": "cookie",
                        "name": c,
                        "detail": d,
                        "severity": _severity_for(t, c),
                    }
                )
            print(table_c)

        techs, leaks = fingerprint(headers)
        if techs or leaks:
            table_f = Table(title="Fingerprint / Info Leaks")
            table_f.add_column("Key")
            table_f.add_column("Value")
            if techs:
                table_f.add_row("Detected", ", ".join(techs))
                findings.append(
                    {
                        "type": "info",
                        "area": "fingerprint",
                        "name": "detected",
                        "detail": ", ".join(techs),
                        "severity": "info",
                    }
                )
            for k, v in leaks:
                table_f.add_row(f"Leak: {k}", v)
                findings.append(
                    {
                        "type": "info",
                        "area": "leak",
                        "name": k,
                        "detail": v,
                        "severity": "low",
                    }
                )
            print(table_f)

        tls_issues = []
        open_ports = []
        if not quick:
            open_ports = scan_ports(host)
            if open_ports:
                table_p = Table(title="Open web ports")
                table_p.add_column("Port", justify="right")
                for p in open_ports:
                    table_p.add_row(str(p))
                print(table_p)
                findings.append(
                    {
                        "type": "info",
                        "area": "ports",
                        "name": "open_ports",
                        "detail": open_ports,
                        "severity": "info",
                    }
                )

            if url.startswith("https://"):
                try:
                    info = tls_info(host, 443)
                    tls_issues = analyze_tls(info)
                    table_t = Table(title="TLS Info")
                    table_t.add_column("Field")
                    table_t.add_column("Value")
                    table_t.add_row("Version", str(info.get("version")))
                    cipher = info.get("cipher") or ("", "", "")
                    table_t.add_row("Cipher", str(cipher[0]))
                    exp = info.get("expires_at")
                    table_t.add_row(
                        "Expires",
                        exp.strftime("%Y-%m-%d %H:%M:%S UTC") if exp else "N/A",
                    )
                    print(table_t)
                    for t, a, d in tls_issues:
                        findings.append(
                            {
                                "type": t,
                                "area": a,
                                "name": a,
                                "detail": d,
                                "severity": _severity_for(t, a),
                            }
                        )
                except Exception as e:
                    print(f"[yellow]⚠ No se pudo leer TLS:[/yellow] {e}")

        payload = {
            "target": url,
            "http_version": "1.1" if (force_http1 or not H2_AVAILABLE) else "2.0",
            "findings": findings,
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"💾 Reporte JSON guardado en: {out_path}")
        wrote = True

        total_findings = sum(
            1
            for f in findings
            if f["severity"] in ("low", "medium", "warn", "critical")
        )
        if tls_issues:
            table_tls = Table(title="TLS Issues")
            table_tls.add_column("Type")
            table_tls.add_column("Area")
            table_tls.add_column("Detail")
            for t, a, d in tls_issues:
                table_tls.add_row(t.upper(), a, d)
            print(table_tls)

        if total_findings == 0:
            print("[bold][green]✅ Scan finalizado: sin hallazgos[/green][/bold]")
            raise typer.Exit(code=0)
        else:
            print(
                f"[bold][yellow]⚠ Scan finalizado con {total_findings} hallazgos[/yellow][/bold]"
            )
            raise typer.Exit(code=1)

    except typer.Exit:
        raise
    except Exception as e:
        print(f"[red]✗ Error inesperado[/red]: {e}")
        if not wrote:
            payload = {
                "target": url,
                "http_version": "1.1" if (force_http1 or not H2_AVAILABLE) else "2.0",
                "error": str(e),
                "findings": findings,
            }
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            print(f"💾 Reporte JSON guardado en: {out_path}")
        raise typer.Exit(code=1)
    finally:
        if not wrote:
            try:
                payload = {
                    "target": url,
                    "http_version": (
                        "1.1" if (force_http1 or not H2_AVAILABLE) else "2.0"
                    ),
                    "findings": findings,
                }
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)
                print(f"💾 Reporte JSON guardado en: {out_path}")
            except Exception:
                pass
