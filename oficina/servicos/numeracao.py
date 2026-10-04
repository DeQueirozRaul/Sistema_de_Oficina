"""Numeração sequencial de OS e orçamentos."""

import sqlite3

from oficina.modelos import ErroValidacao
from oficina.servicos import configuracoes as cfg

_TABELAS = {
    cfg.PROXIMO_NUMERO_OS: "ordens_servico",
    cfg.PROXIMO_NUMERO_ORCAMENTO: "orcamentos",
}


def proximo_numero(conn: sqlite3.Connection, chave: str) -> int:
    """Número que o próximo documento vai receber (sem reservar)."""
    configurado = int(cfg.obter(conn, chave))
    maior = conn.execute(f"SELECT MAX(numero) FROM {_TABELAS[chave]}").fetchone()[0]
    return max(configurado, (maior or 0) + 1)


def reservar_numero(conn: sqlite3.Connection, chave: str) -> int:
    """Pega o próximo número e avança o contador (não faz commit)."""
    numero = proximo_numero(conn, chave)
    cfg.definir(conn, chave, numero + 1)
    return numero


def menor_numero_permitido(conn: sqlite3.Connection, chave: str) -> int:
    maior = conn.execute(f"SELECT MAX(numero) FROM {_TABELAS[chave]}").fetchone()[0]
    return (maior or 0) + 1


def definir_proximo_numero(conn: sqlite3.Connection, chave: str, numero: int) -> None:
    """Ajuste manual da numeração, feito pela tela de Configurações (não faz commit)."""
    minimo = menor_numero_permitido(conn, chave)
    if numero < minimo:
        raise ErroValidacao(f"O próximo número deve ser pelo menos {minimo}, "
                            f"pois já existe um documento com o número {minimo - 1}.")
    cfg.definir(conn, chave, numero)
