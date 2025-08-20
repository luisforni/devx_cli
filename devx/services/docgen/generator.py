import ast
from pathlib import Path

def extract(pyfile: Path):
    tree = ast.parse(pyfile.read_text(encoding="utf-8", errors="ignore"))
    out = []
    mod_doc = ast.get_docstring(tree)
    if mod_doc:
        out.append(f"# {pyfile.name}\n\n{mod_doc}\n")

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name = node.name
            doc = ast.get_docstring(node) or "No docs."
            out.append(f"### {name}\n\n{doc}\n")

        elif isinstance(node, ast.ClassDef):
            class_doc = ast.get_docstring(node) or "No docs."
            out.append(f"## {node.name}\n\n{class_doc}\n")

            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    meth_name = item.name
                    meth_doc = ast.get_docstring(item) or "No docs."
                    out.append(f"#### {meth_name}\n\n{meth_doc}\n")

    return "\n".join(out)
