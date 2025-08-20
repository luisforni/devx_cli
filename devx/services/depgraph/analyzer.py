from pathlib import Path
import ast

IGNORED_DIRS = {"__pycache__", ".git", "venv", ".venv", "env", "build", "dist", "node_modules"}
EXTRA_IGNORED = set()

def extend_ignored(folders):
    EXTRA_IGNORED.update(folders)

def analyze(root: Path, include_externals: bool = True):
    nodes = set()
    edges = set()

    for pyfile in root.rglob("*.py"):
        if any(part in IGNORED_DIRS or part in EXTRA_IGNORED for part in pyfile.parts):
            continue

        modname = module_name(root, pyfile)
        nodes.add(modname)

        try:
            tree = ast.parse(pyfile.read_text(encoding="utf-8"))
        except Exception:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    dep = alias.name.split(".")[0]
                    if include_externals or dep.startswith(root.name):
                        edges.add((modname, dep))
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    dep = node.module.split(".")[0]
                    if include_externals or dep.startswith(root.name):
                        edges.add((modname, dep))

    cycles = find_cycles(nodes, edges)
    return sorted(nodes), sorted(edges), cycles

def module_name(root: Path, file: Path) -> str:
    rel = file.relative_to(root).with_suffix("")
    return ".".join(rel.parts)

def find_cycles(nodes, edges):
    graph = {}
    for a, b in edges:
        graph.setdefault(a, []).append(b)

    cycles = []

    def dfs(path, visited):
        current = path[-1]
        for neighbor in graph.get(current, []):
            if neighbor == path[0]:
                cycles.append(path[:])
            elif neighbor not in visited:
                dfs(path + [neighbor], visited | {neighbor})

    for n in nodes:
        dfs([n], {n})

    return cycles

def to_dot(nodes, edges, rankdir="LR"):
    lines = [f'digraph deps {{ rankdir={rankdir};']
    for n in nodes:
        lines.append(f'  "{n}";')
    for a, b in edges:
        lines.append(f'  "{a}" -> "{b}";')
    lines.append("}")
    return "\n".join(lines)

def to_json(nodes, edges, cycles):
    return {
        "nodes": nodes,
        "edges": [{"from": a, "to": b} for a, b in edges],
        "cycles": cycles,
    }
