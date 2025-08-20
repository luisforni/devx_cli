from __future__ import annotations
import asyncio
import enum
from pathlib import Path
from typing import Dict, List, Optional, Set
import typer
from devx.core.logging import get_logger
from .builder import (
    parse_requirements,
    parse_pyproject,
    build_cyclonedx,
    build_spdx,
    query_osv_pyPI,
    serialize_json,
    resolve_installed_versions,
)

try:
    import httpx
except Exception:
    httpx = None

app = typer.Typer(help="Software Bill of Materials (SBOM) para proyectos Python")
log = get_logger(__name__)

class SBOMFormat(str, enum.Enum):
    cyclonedx = "cyclonedx"
    spdx = "spdx"

def _is_pinned_version(spec: str | None) -> bool:
    if not spec:
        return False
    v = spec.lstrip("=")
    return bool(v) and v[0].isdigit()

def _pick_pinned_packages(pkgs: List[Dict]) -> List[Dict]:
    pinned: List[Dict] = []
    for p in pkgs:
        if _is_pinned_version(p.get("version")):
            pinned.append(p)
    return pinned

async def _fetch_osv_detail(client: httpx.AsyncClient, vuln_id: str) -> Dict:
    url = f"https://api.osv.dev/v1/vulns/{vuln_id}"
    r = await client.get(url)
    r.raise_for_status()
    data = r.json()
    title = data.get("summary") or data.get("details") or ""
    sev_list = data.get("severity") or []
    severity = None
    if isinstance(sev_list, list) and sev_list:
        sev = sev_list[0]
        severity = f"{sev.get('type','')}: {sev.get('score','')}".strip(": ").strip()
    return {
        "id": vuln_id,
        "title": title[:300] if title else None,
        "severity": severity,
    }

async def _enrich_osv_details(
    vulns_by_pkg: Dict[str, List[Dict]],
    timeout: float = 10.0,
    concurrency: int = 10,
) -> Dict[str, List[Dict]]:
    if httpx is None:
        log.warning("[SBOM] httpx no está disponible; --osv-details será ignorado.")
        return vulns_by_pkg

    ids: Set[str] = set()
    for lst in vulns_by_pkg.values():
        for v in lst or []:
            vid = v.get("id")
            if vid:
                ids.add(vid)

    if not ids:
        return vulns_by_pkg

    sem = asyncio.Semaphore(concurrency)

    async def _task(
        vuln_id: str, client: httpx.AsyncClient
    ) -> tuple[str, Optional[Dict]]:
        async with sem:
            try:
                detail = await _fetch_osv_detail(client, vuln_id)
                return vuln_id, detail
            except Exception as e:  # pragma: no cover
                log.debug("[SBOM] Falló detalle OSV %s: %s", vuln_id, e)
                return vuln_id, None

    details_map: Dict[str, Dict] = {}
    async with httpx.AsyncClient(timeout=timeout) as client:
        tasks = [_task(vid, client) for vid in ids]
        for fut in asyncio.as_completed(tasks):
            vid, detail = await fut
            if detail:
                details_map[vid] = detail

    enriched: Dict[str, List[Dict]] = {}
    for pkg, lst in vulns_by_pkg.items():
        enriched[pkg] = []
        for v in lst or []:
            vid = v.get("id")
            enriched[pkg].append(details_map.get(vid, v))
    return enriched

@app.command("run")
def run(
    input_path: str = typer.Argument(
        ...,
        help="Ruta a requirements.txt o pyproject.toml",
        show_default=False,
    ),
    out: Optional[str] = typer.Option(
        "sbom.json",
        "--out",
        help="Nombre del archivo de salida (.json). Se guarda en reports/sbom/",
    ),
    fmt: SBOMFormat = typer.Option(
        SBOMFormat.cyclonedx,
        "--format",
        "-f",
        help="Formato del SBOM a generar (cyclonedx o spdx)",
    ),
    osv: bool = typer.Option(
        False,
        "--osv",
        help="Consultar vulnerabilidades en OSV.dev y agregarlas al reporte",
    ),
    osv_details: bool = typer.Option(
        False,
        "--osv-details",
        help="Enriquecer cada vulnerabilidad con título y severidad (consulta /v1/vulns/{id}). Requiere httpx.",
    ),
    timeout: float = typer.Option(
        15.0,
        "--timeout",
        help="Timeout (segundos) para las consultas a OSV.dev",
    ),
    resolve_env: bool = typer.Option(
        False,
        "--resolve-installed",
        help="Completa versiones consultando los paquetes instalados en el entorno actual.",
    ),
) -> None:
    path = Path(input_path)
    if not path.exists():
        typer.echo(f"[SBOM] No existe: {path}")
        raise typer.Exit(code=1)

    if path.name == "requirements.txt":
        pkgs = parse_requirements(path)
        source = "requirements.txt"
    elif path.name == "pyproject.toml":
        pkgs = parse_pyproject(path)
        source = "pyproject.toml"
    else:
        typer.echo("[SBOM] Debes apuntar a requirements.txt o pyproject.toml")
        raise typer.Exit(code=2)

    if not pkgs:
        typer.echo("[SBOM] No se detectaron dependencias")
        raise typer.Exit(code=0)

    if resolve_env:
        pkgs = resolve_installed_versions(pkgs)

    log.info(f"[SBOM] Detectadas {len(pkgs)} dependencias desde {source}")

    if fmt == SBOMFormat.cyclonedx:
        doc = build_cyclonedx(pkgs)
    else:
        doc = build_spdx(pkgs)

    if osv:
        pinned = _pick_pinned_packages(pkgs)
        if not pinned:
            log.warning(
                "[SBOM] No hay versiones exactas; se omite consulta a OSV. "
                "Usa --resolve-installed o fija versiones (pip freeze)."
            )
        else:
            try:
                vulns = asyncio.run(query_osv_pyPI(pinned, timeout=timeout))
                if osv_details:
                    vulns = asyncio.run(_enrich_osv_details(vulns, timeout=timeout))
                doc["_security"] = {
                    "source": "osv.dev",
                    "vulnerabilities_by_package": {
                        k: [
                            {
                                "id": v.get("id"),
                                "title": v.get("title"),
                                "summary": v.get("summary"),
                                "severity": v.get("severity"),
                            }
                            for v in (vulns.get(k) or [])
                        ]
                        for k in vulns.keys()
                    },
                }
                n_total = sum(len(v) for v in vulns.values())
                log.warning(f"[SBOM] Vulnerabilidades encontradas: {n_total}")
            except Exception as e:
                log.exception("[SBOM] Error consultando OSV.dev: %s", e)

    out_dir = Path("reports") / "sbom"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / out
    serialize_json(doc, out_path)
    typer.echo(f"[SBOM] Generado {fmt.value.upper()} → {out_path.resolve()}")
