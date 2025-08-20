from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

@dataclass
class Finding:
    level: str
    code: str
    message: str
    advice: str

@dataclass
class StaticReport:
    multistage: bool
    uses_non_root: bool
    findings: List[Finding]

def _normalize(line: str) -> str:
    return line.strip()

def analyze_dockerfile(dockerfile_path: Path) -> StaticReport:
    text = dockerfile_path.read_text(encoding="utf-8", errors="ignore").splitlines()

    froms: List[str] = []
    users: List[str] = []
    runs: List[str] = []
    copies: List[str] = []

    for raw in text:
        line = _normalize(raw)
        if not line or line.startswith("#"):
            continue
        upper = line.upper()
        if upper.startswith("FROM "):
            froms.append(line)
        elif upper.startswith("USER "):
            users.append(line.split(None, 1)[1].strip())
        elif upper.startswith("RUN "):
            runs.append(line[4:])
        elif upper.startswith("COPY "):
            copies.append(line[5:])

    multistage = len(froms) > 1
    uses_non_root = any(u not in ("root", "0") for u in users) if users else False

    findings: List[Finding] = []

    if not multistage:
        findings.append(Finding(
            level="WARN",
            code="DKR001",
            message="No se detecta multi-stage build (una única instrucción FROM).",
            advice="Usa multi-stage para reducir tamaño y evitar toolchains en la imagen final."
        ))

    if not users:
        findings.append(Finding(
            level="WARN",
            code="DKR002",
            message="No se define USER; por defecto se ejecuta como root.",
            advice="Añade `USER app` (crea el usuario) para endurecer la imagen."
        ))
    elif not uses_non_root:
        findings.append(Finding(
            level="WARN",
            code="DKR003",
            message="Se define USER pero sigue siendo root.",
            advice="Cambia a un usuario sin privilegios: `RUN useradd -m app && chown -R app:app /app` y `USER app`."
        ))

    for cmd in runs:
        l = cmd.lower()
        if "apt-get update" in l and "apt-get install" not in l:
            findings.append(Finding(
                level="WARN",
                code="DKR004",
                message="`apt-get update` sin `apt-get install` en la misma capa.",
                advice="Combina: `RUN apt-get update && apt-get install -y ... && rm -rf /var/lib/apt/lists/*`."
            ))
            break

    for cmd in runs:
        l = cmd.lower()
        if "pip install" in l and "--no-cache-dir" not in l:
            findings.append(Finding(
                level="INFO",
                code="DKR005",
                message="`pip install` sin `--no-cache-dir`.",
                advice="Usa `pip install --no-cache-dir -r requirements.txt` para reducir tamaño."
            ))
            break

    if any(c.strip() in (". .", "./ .", ". ./") or c.strip().startswith(". ") for c in copies):
        has_dockerignore = (dockerfile_path.parent / ".dockerignore").exists()
        if not has_dockerignore:
            findings.append(Finding(
                level="WARN",
                code="DKR006",
                message="`COPY . .` sin .dockerignore.",
                advice="Crea .dockerignore para excluir artefactos (venv, .git, node_modules, dist, etc.)."
            ))

    run_count = len(runs)
    if run_count >= 10:
        findings.append(Finding(
            level="INFO",
            code="DKR007",
            message=f"Se detectan {run_count} instrucciones RUN (posible exceso de capas).",
            advice="Combina comandos relacionados en una sola capa cuando sea coherente."
        ))

    return StaticReport(multistage=multistage, uses_non_root=uses_non_root, findings=findings)
