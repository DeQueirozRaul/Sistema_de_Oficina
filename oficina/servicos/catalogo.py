"""Itens já lançados, usados para o autocompletar de peças e serviços.

Guarda o último tipo e o último valor usados em cada descrição. O valor é só
uma sugestão: na tela ele pode ser alterado livremente em cada OS.
"""

import sqlite3
from dataclasses import dataclass
from datetime import date

from oficina.modelos import TIPOS_ITEM, ErroValidacao, Item


@dataclass
class ItemCatalogo:
    id: int
    descricao: str
    tipo: str
    valor_unitario: int
    ultimo_uso: date


def _para_item(linha: sqlite3.Row) -> ItemCatalogo:
    return ItemCatalogo(
        id=linha["id"],
        descricao=linha["descricao"],
        tipo=linha["tipo"],
        valor_unitario=linha["valor_unitario"],
        ultimo_uso=date.fromisoformat(linha["ultimo_uso"]),
    )


def listar(conn: sqlite3.Connection, busca: str = "") -> list[ItemCatalogo]:
    sql = "SELECT * FROM catalogo_itens"
    parametros: list = []
    if busca.strip():
        sql += " WHERE normalizar(descricao) LIKE '%' || normalizar(?) || '%'"
        parametros.append(busca.strip())
    sql += " ORDER BY descricao COLLATE NOCASE"
    return [_para_item(linha) for linha in conn.execute(sql, parametros)]


def obter_por_descricao(conn: sqlite3.Connection, descricao: str) -> ItemCatalogo | None:
    linha = conn.execute("SELECT * FROM catalogo_itens WHERE descricao = ?", (descricao.strip(),)).fetchone()
    return _para_item(linha) if linha else None


def registrar_itens(conn: sqlite3.Connection, itens: list[Item], quando: date) -> None:
    """Atualiza o catálogo com os itens de uma OS/orçamento (não faz commit).

    Ao editar uma OS antiga, o tipo/valor do catálogo só muda se ela for a
    mais recente que usou aquele item.
    """
    for item in itens:
        conn.execute(
            """INSERT INTO catalogo_itens (descricao, tipo, valor_unitario, ultimo_uso) VALUES (?, ?, ?, ?)
               ON CONFLICT(descricao) DO UPDATE SET
                   tipo = CASE WHEN excluded.ultimo_uso >= ultimo_uso THEN excluded.tipo ELSE tipo END,
                   valor_unitario = CASE WHEN excluded.ultimo_uso >= ultimo_uso
                                         THEN excluded.valor_unitario ELSE valor_unitario END,
                   ultimo_uso = MAX(ultimo_uso, excluded.ultimo_uso)""",
            (item.descricao.strip(), item.tipo, item.valor_unitario, quando.isoformat()),
        )


def atualizar(conn: sqlite3.Connection, item_id: int, descricao: str, tipo: str, valor_unitario: int) -> None:
    if not descricao.strip():
        raise ErroValidacao("Informe a descrição.")
    if tipo not in TIPOS_ITEM:
        raise ErroValidacao("Escolha o tipo do item.")
    if valor_unitario < 0:
        raise ErroValidacao("O valor não pode ser negativo.")
    repetido = conn.execute(
        "SELECT 1 FROM catalogo_itens WHERE descricao = ? AND id <> ?", (descricao.strip(), item_id)
    ).fetchone()
    if repetido:
        raise ErroValidacao(f"Já existe um item com a descrição \"{descricao.strip()}\".")
    with conn:
        conn.execute(
            "UPDATE catalogo_itens SET descricao = ?, tipo = ?, valor_unitario = ? WHERE id = ?",
            (descricao.strip(), tipo, valor_unitario, item_id),
        )


def excluir(conn: sqlite3.Connection, item_id: int) -> None:
    with conn:
        conn.execute("DELETE FROM catalogo_itens WHERE id = ?", (item_id,))
