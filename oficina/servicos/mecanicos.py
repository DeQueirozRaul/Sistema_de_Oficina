"""Cadastro de mecânicos e seus percentuais de comissão."""

import sqlite3

from oficina.modelos import ErroValidacao, Mecanico


def _para_mecanico(linha: sqlite3.Row) -> Mecanico:
    return Mecanico(
        id=linha["id"],
        nome=linha["nome"],
        percentual_comissao=linha["percentual_comissao"],
        telefone=linha["telefone"],
        ativo=bool(linha["ativo"]),
    )


def listar(conn: sqlite3.Connection, somente_ativos: bool = False) -> list[Mecanico]:
    sql = "SELECT * FROM mecanicos"
    if somente_ativos:
        sql += " WHERE ativo = 1"
    sql += " ORDER BY ativo DESC, nome COLLATE NOCASE"
    return [_para_mecanico(linha) for linha in conn.execute(sql)]


def obter(conn: sqlite3.Connection, mecanico_id: int) -> Mecanico | None:
    linha = conn.execute("SELECT * FROM mecanicos WHERE id = ?", (mecanico_id,)).fetchone()
    return _para_mecanico(linha) if linha else None


def salvar(conn: sqlite3.Connection, mecanico: Mecanico) -> int:
    nome = mecanico.nome.strip()
    if not nome:
        raise ErroValidacao("Informe o nome do mecânico.")
    if not 0 <= mecanico.percentual_comissao <= 100:
        raise ErroValidacao("A comissão deve estar entre 0% e 100%.")
    repetido = conn.execute(
        "SELECT 1 FROM mecanicos WHERE normalizar(nome) = normalizar(?) AND id IS NOT ?",
        (nome, mecanico.id),
    ).fetchone()
    if repetido:
        raise ErroValidacao(f"Já existe um mecânico chamado \"{nome}\".")

    valores = (nome, mecanico.percentual_comissao, mecanico.telefone.strip(), int(mecanico.ativo))
    with conn:
        if mecanico.id is None:
            cursor = conn.execute(
                "INSERT INTO mecanicos (nome, percentual_comissao, telefone, ativo) VALUES (?, ?, ?, ?)",
                valores,
            )
            return cursor.lastrowid
        conn.execute(
            "UPDATE mecanicos SET nome = ?, percentual_comissao = ?, telefone = ?, ativo = ? WHERE id = ?",
            (*valores, mecanico.id),
        )
        return mecanico.id


def definir_ativo(conn: sqlite3.Connection, mecanico_id: int, ativo: bool) -> None:
    with conn:
        conn.execute("UPDATE mecanicos SET ativo = ? WHERE id = ?", (int(ativo), mecanico_id))


def possui_os(conn: sqlite3.Connection, mecanico_id: int) -> bool:
    linha = conn.execute("SELECT 1 FROM ordens_servico WHERE mecanico_id = ? LIMIT 1", (mecanico_id,)).fetchone()
    return linha is not None


def excluir(conn: sqlite3.Connection, mecanico_id: int) -> None:
    if possui_os(conn, mecanico_id):
        raise ErroValidacao("Este mecânico já tem OS registradas e não pode ser excluído. "
                            "Use \"Desativar\" para que ele não apareça mais nas novas OS.")
    with conn:
        conn.execute("DELETE FROM mecanicos WHERE id = ?", (mecanico_id,))
