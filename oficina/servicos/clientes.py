"""Cadastro de clientes e veículos.

Os cadastros são alimentados automaticamente ao salvar OS e orçamentos: basta
digitar a placa numa próxima vez para o sistema preencher o resto.
"""

import re
import sqlite3

from oficina.banco import somente_digitos
from oficina.modelos import Cliente, ErroValidacao, Veiculo


def normalizar_placa(placa: str) -> str:
    """'abc-1234 ' -> 'ABC1234'."""
    return re.sub(r"[^A-Z0-9]", "", (placa or "").upper())


# ---------------------------------------------------------------- clientes

def _para_cliente(linha: sqlite3.Row) -> Cliente:
    return Cliente(
        id=linha["id"],
        nome=linha["nome"],
        documento=linha["documento"],
        telefone=linha["telefone"],
        observacoes=linha["observacoes"],
    )


def obter_cliente(conn: sqlite3.Connection, cliente_id: int) -> Cliente | None:
    linha = conn.execute("SELECT * FROM clientes WHERE id = ?", (cliente_id,)).fetchone()
    return _para_cliente(linha) if linha else None


def listar_clientes(conn: sqlite3.Connection, busca: str = "") -> list[tuple[Cliente, int]]:
    """Clientes (com a quantidade de veículos), filtrando por nome, CPF/CNPJ ou telefone."""
    sql = """
        SELECT c.*, (SELECT COUNT(*) FROM veiculos v WHERE v.cliente_id = c.id) AS qtd_veiculos
        FROM clientes c
    """
    parametros: list = []
    busca = busca.strip()
    if busca:
        sql += " WHERE normalizar(c.nome) LIKE '%' || normalizar(?) || '%'"
        parametros.append(busca)
        if somente_digitos(busca):
            sql += " OR digitos(c.documento) LIKE '%' || ? || '%' OR digitos(c.telefone) LIKE '%' || ? || '%'"
            parametros += [somente_digitos(busca)] * 2
    sql += " ORDER BY c.nome COLLATE NOCASE"
    return [(_para_cliente(linha), linha["qtd_veiculos"]) for linha in conn.execute(sql, parametros)]


def nomes_clientes(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    linhas = conn.execute("SELECT id, nome FROM clientes ORDER BY nome COLLATE NOCASE")
    return [(linha["id"], linha["nome"]) for linha in linhas]


def salvar_cliente(conn: sqlite3.Connection, cliente: Cliente) -> int:
    if not cliente.nome.strip():
        raise ErroValidacao("Informe o nome do cliente.")
    valores = (cliente.nome.strip(), cliente.documento.strip(), cliente.telefone.strip(), cliente.observacoes.strip())
    with conn:
        if cliente.id is None:
            return conn.execute(
                "INSERT INTO clientes (nome, documento, telefone, observacoes) VALUES (?, ?, ?, ?)", valores
            ).lastrowid
        conn.execute(
            "UPDATE clientes SET nome = ?, documento = ?, telefone = ?, observacoes = ? WHERE id = ?",
            (*valores, cliente.id),
        )
        return cliente.id


def excluir_cliente(conn: sqlite3.Connection, cliente_id: int) -> None:
    """Exclui o cadastro. As OS antigas continuam com os dados impressos nelas."""
    with conn:
        conn.execute("DELETE FROM clientes WHERE id = ?", (cliente_id,))


def registrar_cliente(conn: sqlite3.Connection, cliente_id: int | None, nome: str, documento: str,
                      telefone: str) -> int | None:
    """Cria ou atualiza o cliente usado numa OS (não faz commit).

    Ordem de identificação: cliente escolhido na tela -> mesmo CPF/CNPJ ->
    mesmo nome. Se nada bater, cria um cliente novo.
    """
    nome, documento, telefone = nome.strip(), documento.strip(), telefone.strip()
    if not nome:
        return None
    if cliente_id is not None and obter_cliente(conn, cliente_id) is None:
        cliente_id = None
    if cliente_id is None and somente_digitos(documento):
        linha = conn.execute(
            "SELECT id FROM clientes WHERE digitos(documento) = ? LIMIT 1", (somente_digitos(documento),)
        ).fetchone()
        cliente_id = linha["id"] if linha else None
    if cliente_id is None:
        linha = conn.execute(
            "SELECT id FROM clientes WHERE normalizar(nome) = normalizar(?) LIMIT 1", (nome,)
        ).fetchone()
        cliente_id = linha["id"] if linha else None

    if cliente_id is None:
        return conn.execute(
            "INSERT INTO clientes (nome, documento, telefone) VALUES (?, ?, ?)", (nome, documento, telefone)
        ).lastrowid
    conn.execute(
        """UPDATE clientes SET nome = ?,
               documento = CASE WHEN ? <> '' THEN ? ELSE documento END,
               telefone = CASE WHEN ? <> '' THEN ? ELSE telefone END
           WHERE id = ?""",
        (nome, documento, documento, telefone, telefone, cliente_id),
    )
    return cliente_id


# ---------------------------------------------------------------- veículos

_SQL_VEICULOS = """
    SELECT v.*, COALESCE(c.nome, '') AS cliente_nome
    FROM veiculos v LEFT JOIN clientes c ON c.id = v.cliente_id
"""


def _para_veiculo(linha: sqlite3.Row) -> Veiculo:
    return Veiculo(
        id=linha["id"],
        placa=linha["placa"],
        modelo=linha["modelo"],
        ano=linha["ano"],
        ultimo_km=linha["ultimo_km"],
        cliente_id=linha["cliente_id"],
        cliente_nome=linha["cliente_nome"],
    )


def buscar_veiculo_por_placa(conn: sqlite3.Connection, placa: str) -> Veiculo | None:
    normalizada = normalizar_placa(placa)
    if not normalizada:
        return None
    linha = conn.execute(_SQL_VEICULOS + " WHERE v.placa_normalizada = ?", (normalizada,)).fetchone()
    return _para_veiculo(linha) if linha else None


def obter_veiculo(conn: sqlite3.Connection, veiculo_id: int) -> Veiculo | None:
    linha = conn.execute(_SQL_VEICULOS + " WHERE v.id = ?", (veiculo_id,)).fetchone()
    return _para_veiculo(linha) if linha else None


def listar_veiculos(conn: sqlite3.Connection, cliente_id: int | None = None, busca: str = "") -> list[Veiculo]:
    condicoes, parametros = [], []
    if cliente_id is not None:
        condicoes.append("v.cliente_id = ?")
        parametros.append(cliente_id)
    busca = busca.strip()
    if busca:
        condicoes.append(
            "(v.placa_normalizada LIKE '%' || ? || '%' OR normalizar(v.modelo) LIKE '%' || normalizar(?) || '%'"
            " OR normalizar(c.nome) LIKE '%' || normalizar(?) || '%')"
        )
        parametros += [normalizar_placa(busca) or busca, busca, busca]
    sql = _SQL_VEICULOS
    if condicoes:
        sql += " WHERE " + " AND ".join(condicoes)
    sql += " ORDER BY v.placa_normalizada"
    return [_para_veiculo(linha) for linha in conn.execute(sql, parametros)]


def placas_cadastradas(conn: sqlite3.Connection) -> list[str]:
    return [linha["placa"] for linha in conn.execute("SELECT placa FROM veiculos ORDER BY placa_normalizada")]


def salvar_veiculo(conn: sqlite3.Connection, veiculo: Veiculo) -> int:
    normalizada = normalizar_placa(veiculo.placa)
    if not normalizada:
        raise ErroValidacao("Informe a placa do veículo.")
    repetido = conn.execute(
        "SELECT 1 FROM veiculos WHERE placa_normalizada = ? AND id IS NOT ?", (normalizada, veiculo.id)
    ).fetchone()
    if repetido:
        raise ErroValidacao(f"A placa {veiculo.placa.upper()} já está cadastrada.")
    valores = (veiculo.placa.strip().upper(), normalizada, veiculo.modelo.strip(), veiculo.ano.strip(),
               veiculo.ultimo_km.strip(), veiculo.cliente_id)
    with conn:
        if veiculo.id is None:
            return conn.execute(
                "INSERT INTO veiculos (placa, placa_normalizada, modelo, ano, ultimo_km, cliente_id)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                valores,
            ).lastrowid
        conn.execute(
            "UPDATE veiculos SET placa = ?, placa_normalizada = ?, modelo = ?, ano = ?, ultimo_km = ?, cliente_id = ?"
            " WHERE id = ?",
            (*valores, veiculo.id),
        )
        return veiculo.id


def excluir_veiculo(conn: sqlite3.Connection, veiculo_id: int) -> None:
    with conn:
        conn.execute("DELETE FROM veiculos WHERE id = ?", (veiculo_id,))


def registrar_veiculo(conn: sqlite3.Connection, placa: str, modelo: str = "", ano: str = "", km: str = "",
                      cliente_id: int | None = None) -> int | None:
    """Cria ou atualiza o veículo usado numa OS/orçamento (não faz commit).

    Só sobrescreve os campos que vieram preenchidos.
    """
    normalizada = normalizar_placa(placa)
    if not normalizada:
        return None
    placa, modelo, ano, km = placa.strip().upper(), modelo.strip(), ano.strip(), km.strip()
    existente = conn.execute("SELECT id FROM veiculos WHERE placa_normalizada = ?", (normalizada,)).fetchone()
    if existente is None:
        return conn.execute(
            "INSERT INTO veiculos (placa, placa_normalizada, modelo, ano, ultimo_km, cliente_id)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (placa, normalizada, modelo, ano, km, cliente_id),
        ).lastrowid
    conn.execute(
        """UPDATE veiculos SET
               placa = ?,
               modelo = CASE WHEN ? <> '' THEN ? ELSE modelo END,
               ano = CASE WHEN ? <> '' THEN ? ELSE ano END,
               ultimo_km = CASE WHEN ? <> '' THEN ? ELSE ultimo_km END,
               cliente_id = COALESCE(?, cliente_id)
           WHERE id = ?""",
        (placa, modelo, modelo, ano, ano, km, km, cliente_id, existente["id"]),
    )
    return existente["id"]
