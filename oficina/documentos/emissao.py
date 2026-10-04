"""Emissão dos PDFs a partir das OS/orçamentos salvos.

Estas funções não acessam o banco: recebem tudo pronto (dados da oficina e,
se for o caso, a logo) para poderem rodar em segundo plano.
Os PDFs são organizados em subpastas por mês: OS/2026-09/OS_ABC1D23_1002.pdf
"""

import re
from pathlib import Path

from PySide6.QtGui import QImage

from oficina.documentos import nota_pdf
from oficina.modelos import Orcamento, OrdemServico

DICA_ARQUIVO_ABERTO = "Se o PDF anterior estiver aberto em outro programa, feche-o e tente de novo."


def nome_arquivo(texto) -> str:
    """Remove caracteres que o Windows não aceita em nome de arquivo."""
    return re.sub(r'[\\/:*?"<>|]', "", str(texto)).strip()


def _pasta_do_mes(pasta_raiz: Path, quando) -> Path:
    pasta = Path(pasta_raiz) / quando.strftime("%Y-%m")
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def _gravar(nota: nota_pdf.Nota, caminho: Path) -> tuple[bool, str]:
    try:
        nota_pdf.salvar_pdf(nota, caminho)
    except OSError as erro:
        return False, f"Não foi possível gravar {caminho}: {erro}. {DICA_ARQUIVO_ABERTO}"
    return True, str(caminho)


def emitir_os(os_: OrdemServico, oficina: dict, pasta_raiz: Path, logo: QImage | None = None) -> tuple[bool, str]:
    """Gera o PDF da OS. Devolve (True, caminho_do_pdf) ou (False, mensagem_de_erro)."""
    caminho = _pasta_do_mes(pasta_raiz, os_.data) / f"OS_{nome_arquivo(os_.placa)}_{os_.numero}.pdf"
    return _gravar(nota_pdf.montar_os(os_, oficina, logo), caminho)


def emitir_orcamento(orcamento: Orcamento, oficina: dict, pasta_raiz: Path,
                     logo: QImage | None = None) -> tuple[bool, str]:
    caminho = _pasta_do_mes(pasta_raiz, orcamento.data) / f"ORC_{nome_arquivo(orcamento.placa)}_{orcamento.numero}.pdf"
    return _gravar(nota_pdf.montar_orcamento(orcamento, oficina, logo), caminho)
