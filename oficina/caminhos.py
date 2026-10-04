"""Onde o sistema guarda banco de dados, PDFs, backups e log de erros.

Por padrão tudo fica em "Documentos/Sistema Oficina". Assim os dados não se
perdem quando o programa é atualizado (basta trocar a pasta do programa).
Para testes/desenvolvimento, defina a variável de ambiente OFICINA_DADOS.
"""

import os
import sys
from pathlib import Path

NOME_PASTA_DADOS = "Sistema Oficina"


def pasta_do_programa() -> Path:
    if getattr(sys, "frozen", False):  # executável gerado pelo PyInstaller
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def pasta_documentos() -> Path:
    try:
        from PySide6.QtCore import QStandardPaths

        local = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        if local:
            return Path(local)
    except ImportError:
        pass
    return Path.home() / "Documents"


def pasta_dados() -> Path:
    personalizada = os.environ.get("OFICINA_DADOS")
    pasta = Path(personalizada) if personalizada else pasta_documentos() / NOME_PASTA_DADOS
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def caminho_banco() -> Path:
    return pasta_dados() / "oficina.db"


def caminho_log() -> Path:
    return pasta_dados() / "erros.log"


def pasta_padrao_os() -> Path:
    return pasta_dados() / "OS"


def pasta_padrao_orcamentos() -> Path:
    return pasta_dados() / "Orçamentos"


def pasta_padrao_backups() -> Path:
    return pasta_dados() / "Backups"
