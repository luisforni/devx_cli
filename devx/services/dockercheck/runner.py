from __future__ import annotations
import json, shutil, subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple
from .analyzer import analyze_dockerfile, StaticReport, Finding

@dataclass
class BuildInfo:
    image: Optional[str]
    image_size_bytes: Optional[int]
    layers: List[Tuple[str, int]]

@dataclass
class DockerCheckResult:
    static: StaticReport
    build: BuildInfo
    json_path: Path

def _docker_available() -> bool:
    return shutil.which("docker") is not None

def _run(cmd: list[str], cwd: Optional[Path] = None, timeout: int = 900) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, capture_output=True, text=True, timeout=timeout)

def _parse_size_to_bytes(s: str) -> int:
    units = {"B": 1, "kB": 10**3, "MB": 10**6, "GB": 10**9}
    s = s.strip()
    if s == "" or s == "0B": return 0
    for u in ("GB","MB","kB","B"):
        if s.endswith(u):
            try: return int(float(s[:-len(u)]) * units[u])
            except ValueError: return 0
    return 0

def _image_size(image: str) -> Optional[int]:
    p = _run(["docker","image","inspect",image,"--format","{{.Size}}"])
    if p.returncode != 0: return None
    try: return int(p.stdout.strip())
    except Exception: return None

def _image_layers(image: str) -> List[Tuple[str,int]]:
    p = _run(["docker","history","--no-trunc",image,"--format","{{.ID}};{{.Size}}"])
    layers: List[Tuple[str,int]] = []
    if p.returncode != 0: return layers
    for line in p.stdout.splitlines():
        if ";" in line:
            lid, size = line.split(";",1)
            layers.append((lid.strip(), _parse_size_to_bytes(size.strip())))
    return layers

def run_dockercheck(
    dockerfile: Path,
    image_tag: Optional[str] = None,
    do_build: bool = True,
    workdir: Optional[Path] = None,
    json_out_dir: Optional[Path] = None,
) -> DockerCheckResult:
    dockerfile = dockerfile.resolve()
    base = workdir.resolve() if workdir else dockerfile.parent

    static = analyze_dockerfile(dockerfile)

    build_image = None
    size_bytes: Optional[int] = None
    layers: List[Tuple[str,int]] = []

    if do_build and _docker_available():
        tag = image_tag or f"devx-dockercheck:{abs(hash(str(dockerfile)))%10_000}"
        proc = _run(["docker","build","-t",tag,"-f",str(dockerfile),"."], cwd=base)
        if proc.returncode == 0:
            build_image = tag
            size_bytes = _image_size(tag)
            layers = _image_layers(tag)
        else:
            static.findings.append(Finding(level="ERROR", code="DKR900",
                message="Fallo al construir la imagen Docker.",
                advice=proc.stderr.strip()[:800] or proc.stdout.strip()[:800]))

    out_dir = (json_out_dir.resolve() if json_out_dir else (base / "reports" / "dockercheck"))
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "dockercheck.json"

    payload = {
        "static": {
            "multistage": static.multistage,
            "uses_non_root": static.uses_non_root,
            "findings": [f.__dict__ for f in static.findings],
        },
        "build": {
            "image": build_image,
            "image_size_bytes": size_bytes,
            "layers": layers,
        },
        "docker_available": _docker_available(),
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    return DockerCheckResult(
        static=static,
        build=BuildInfo(image=build_image, image_size_bytes=size_bytes, layers=layers),
        json_path=out_path,
    )
