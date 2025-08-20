from devx.services.docgen.generator import extract

def test_extract_docs_from_module(tmp_path):
    f = tmp_path / "mod.py"
    f.write_text(
        '"""Módulo de prueba."""\n'
        "def foo():\n"
        '    """Func foo docs."""\n'
        "    return 1\n\n"
        "class Bar:\n"
        '    """Clase Bar docs."""\n'
        "    def baz(self):\n"
        '        """Metodo baz docs."""\n'
        "        return 2\n",
        encoding="utf-8",
    )
    md = extract(f)
    assert "# mod.py" in md
    assert "Func foo docs." in md
    assert "Clase Bar docs." in md
    assert "Metodo baz docs." in md
