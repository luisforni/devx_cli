from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional

try:
    import tomllib
except Exception:
    tomllib = None

try:
    from importlib.metadata import version as get_dist_version, PackageNotFoundError
except Exception:
    get_dist_version = None

import httpx

NAME_RE = re.compile(r"^\s*([A-Za-z0-9_.\-]+)")
SPEC_RE = re.compile(r"(==|>=|<=|~=|>|<)")


def _clean_pkg(line: str) -> Optional[Tuple[str, Optional[str]]]:
    line = line.strip()
    if not line or line.startswith("#") or line.startswith("-e ") or "://" in line:
        return None
    m = NAME_RE.match(line)
    if not m:
        return None
    name = m.group(1)
    ver = None
    if "==" in line:
        ver = line.split("==", 1)[1].split("#", 1)[0].strip()
    elif any(op in line for op in (">=", "<=", "~=", ">", "<")):
        parts = SPEC_RE.split(line, maxsplit=1)
        if len(parts) >= 3:
            ver = f"{parts[1]}{parts[2].split('#', 1)[0].strip()}"
    return name, ver


def parse_requirements(req_path: Path) -> List[Dict[str, str]]:
    pkgs: List[Dict[str, str]] = []
    for line in req_path.read_text(encoding="utf-8").splitlines():
        pv = _clean_pkg(line)
        if not pv:
            continue
        name, ver = pv
        item = {"name": name}
        if ver:
            item["version"] = ver
        pkgs.append(item)
    return pkgs


def parse_pyproject(pyproj_path: Path) -> List[Dict[str, str]]:
    if tomllib is None:
        return []
    data = tomllib.loads(pyproj_path.read_text(encoding="utf-8"))
    deps: List[Dict[str, str]] = []

    poetry = data.get("tool", {}).get("poetry", {})
    for dep_name, spec in poetry.get("dependencies", {}).items():
        if dep_name.lower() == "python":
            continue
        deps.append({"name": dep_name, "version": str(spec)})

    for spec in (data.get("project", {}) or {}).get("dependencies", []) or []:
        pv = _clean_pkg(spec)
        if pv:
            name, ver = pv
            item = {"name": name}
            if ver:
                item["version"] = ver
            deps.append(item)

    return deps


def _looks_like_pinned(ver: str) -> bool:
    return bool(ver) and ver[0].isdigit()


def resolve_installed_versions(packages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    if get_dist_version is None:
        return packages
    for p in packages:
        ver = p.get("version")
        if ver and _looks_like_pinned(ver.lstrip("=")):
            continue
        try:
            v = get_dist_version(p["name"])
            p["version"] = v
        except PackageNotFoundError:
            pass
    return packages


def build_cyclonedx(packages: List[Dict[str, str]]) -> Dict:
    components = []
    for p in packages:
        spec = p.get("version", "")
        ver = spec.lstrip("=") if spec else ""
        purl = f"pkg:pypi/{p['name']}"
        if _looks_like_pinned(ver):
            purl = f"{purl}@{ver}"
        comp = {
            "type": "library",
            "name": p["name"],
            "purl": purl,
        }
        if _looks_like_pinned(ver):
            comp["version"] = ver
        components.append(comp)

    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "components": components,
    }


def build_spdx(packages: List[Dict[str, str]]) -> Dict:
    spdx_pkgs = []
    for p in packages:
        spec = p.get("version", "")
        ver = spec.lstrip("=") if spec else ""
        pkg = {
            "name": p["name"],
            "downloadLocation": "NOASSERTION",
            "supplier": "NOASSERTION",
            "licenseConcluded": "NOASSERTION",
            "licenseDeclared": "NOASSERTION",
        }
        if _looks_like_pinned(ver):
            pkg["versionInfo"] = ver
        spdx_pkgs.append(pkg)

    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": "devx-cli-sbom",
        "documentNamespace": "http://spdx.org/spdxdocs/devx-cli-sbom",
        "packages": spdx_pkgs,
    }


async def query_osv_pyPI(
    packages: List[Dict[str, str]],
    timeout: float = 10.0,
) -> Dict[str, List[Dict]]:
    url = "https://api.osv.dev/v1/querybatch"
    payload = {"queries": []}
    idx_map: List[str] = []

    for p in packages:
        spec = p.get("version", "")
        ver = spec.lstrip("=") if spec else ""
        query: Dict = {"package": {"name": p["name"], "ecosystem": "PyPI"}}
        if _looks_like_pinned(ver):
            query["version"] = ver
        payload["queries"].append(query)
        idx_map.append(p["name"])

    out: Dict[str, List[Dict]] = {}
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()
        data = r.json()
        for i, res in enumerate(data.get("results", [])):
            vulns = res.get("vulns") or []
            out.setdefault(idx_map[i], []).extend(vulns)
    return out


def serialize_json(obj: Dict, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
