"""O notebook de análise precisa continuar rodando com o banco atual do sistema."""

import json
from pathlib import Path

import pytest

NOTEBOOK = Path(__file__).resolve().parent.parent / "analises" / "analise_oficina.ipynb"


def test_notebook_de_analise_executa_sem_erros(monkeypatch):
    pytest.importorskip("pandas")
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg")  # sem janelas
    import matplotlib.pyplot as plt

    monkeypatch.chdir(NOTEBOOK.parent)
    celulas = [c for c in json.loads(NOTEBOOK.read_text(encoding="utf-8"))["cells"] if c["cell_type"] == "code"]
    assert celulas
    contexto: dict = {}
    try:
        for numero, celula in enumerate(celulas, start=1):
            exec(compile("".join(celula["source"]), f"célula {numero}", "exec"), contexto)
    finally:
        plt.close("all")
    assert contexto["orcamentos"]["aprovado"].any() and len(contexto["abc"]) > 10
