"""Orçamentos: salvar, carregar, buscar e transformar em OS."""

import sqlite3
from dataclasses import dataclass
from datetime import date

from oficina.banco import agora, para_data
from oficina.modelos import Cliente, ErroValidacao, Item, Orcamento, OrdemServico, validar_itens
from oficina.servicos import catalogo, clientes, numeracao
from oficina.servicos import configuracoes as cfg
from oficina.servicos.clientes import normalizar_placa


def proximo_numero(conn: sqlite3.Connection) -> int:
    return numeracao.proximo_numero(conn, cfg.PROXIMO_NUMERO_ORCAMENTO)


def salvar(conn: sqlite3.Connection, orcamento: Orcamento) -> Orcamento:
    if not orcamento.itens:
        raise ErroValidacao("Adicione pelo menos um item ao orçamento.")
    validar_itens(orcamento.itens, orcamento.desconto)
    totais = orcamento.totais
    momento = agora()

    with conn:
        veiculo_id = clientes.registrar_veiculo(conn, orcamento.placa, orcamento.modelo)
        campos = {
            "data": orcamento.data.isoformat(),
            "veiculo_id": veiculo_id,
            "placa": orcamento.placa.strip().upper(),
            "modelo": orcamento.modelo.strip(),
            "desconto": orcamento.desconto,
            "total": totais.total,
            "observacoes": orcamento.observacoes.strip(),
            "atualizado_em": momento,
        }
        existe = orcamento.id is not None and conn.execute(
            "SELECT 1 FROM orcamentos WHERE id = ?", (orcamento.id,)
        ).fetchone()
        if not existe:
            campos["numero"] = numeracao.reservar_numero(conn, cfg.PROXIMO_NUMERO_ORCAMENTO)
            campos["criado_em"] = momento
            orcamento_id = conn.execute(
                f"INSERT INTO orcamentos ({', '.join(campos)}) VALUES ({', '.join('?' for _ in campos)})",
                list(campos.values()),
            ).lastrowid
        else:
            orcamento_id = orcamento.id
            atribuicoes = ", ".join(f"{coluna} = ?" for coluna in campos)
            conn.execute(f"UPDATE orcamentos SET {atribuicoes} WHERE id = ?", [*campos.values(), orcamento_id])
            conn.execute("DELETE FROM itens_orcamento WHERE orcamento_id = ?", (orcamento_id,))

        conn.executemany(
            "INSERT INTO itens_orcamento (orcamento_id, posicao, descricao, tipo, quantidade, valor_unitario, total)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(orcamento_id, posicao, item.descricao.strip(), item.tipo, item.quantidade, item.valor_unitario,
              item.total) for posicao, item in enumerate(orcamento.itens, start=1)],
        )
        catalogo.registrar_itens(conn, orcamento.itens, orcamento.data)

    return carregar(conn, orcamento_id)


def carregar(conn: sqlite3.Connection, orcamento_id: int) -> Orcamento | None:
    linha = conn.execute("SELECT * FROM orcamentos WHERE id = ?", (orcamento_id,)).fetchone()
    if linha is None:
        return None
    itens = [
        Item(descricao=i["descricao"], tipo=i["tipo"], quantidade=i["quantidade"], valor_unitario=i["valor_unitario"])
        for i in conn.execute("SELECT * FROM itens_orcamento WHERE orcamento_id = ? ORDER BY posicao", (orcamento_id,))
    ]
    return Orcamento(
        id=linha["id"],
        numero=linha["numero"],
        data=para_data(linha["data"]),
        veiculo_id=linha["veiculo_id"],
        placa=linha["placa"],
        modelo=linha["modelo"],
        itens=itens,
        desconto=linha["desconto"],
        observacoes=linha["observacoes"],
        caminho_pdf=linha["caminho_pdf"],
    )


def definir_caminho_pdf(conn: sqlite3.Connection, orcamento_id: int, caminho: str) -> None:
    with conn:
        conn.execute("UPDATE orcamentos SET caminho_pdf = ? WHERE id = ?", (caminho, orcamento_id))


@dataclass
class ResumoOrcamento:
    id: int
    numero: int
    data: date
    placa: str
    modelo: str
    total: int
    caminho_pdf: str
    os_numero: int | None  # OS gerada a partir deste orçamento


def buscar(conn: sqlite3.Connection, busca: str = "", inicio: date | None = None,
           fim: date | None = None) -> list[ResumoOrcamento]:
    condicoes, parametros = [], []
    busca = busca.strip()
    if busca:
        opcoes = ["normalizar(o.modelo) LIKE '%' || normalizar(?) || '%'"]
        parametros.append(busca)
        if normalizar_placa(busca):
            opcoes.append("REPLACE(REPLACE(UPPER(o.placa), '-', ''), ' ', '') LIKE '%' || ? || '%'")
            parametros.append(normalizar_placa(busca))
        if busca.isdigit():
            opcoes.append("o.numero = ?")
            parametros.append(int(busca))
        condicoes.append("(" + " OR ".join(opcoes) + ")")
    if inicio:
        condicoes.append("o.data >= ?")
        parametros.append(inicio.isoformat())
    if fim:
        condicoes.append("o.data <= ?")
        parametros.append(fim.isoformat())
    sql = """
        SELECT o.*, (SELECT MAX(os.numero) FROM ordens_servico os
                     WHERE os.orcamento_id = o.id AND os.status <> 'cancelada') AS os_numero
        FROM orcamentos o
    """
    if condicoes:
        sql += " WHERE " + " AND ".join(condicoes)
    sql += " ORDER BY o.numero DESC"
    return [
        ResumoOrcamento(
            id=linha["id"], numero=linha["numero"], data=para_data(linha["data"]), placa=linha["placa"],
            modelo=linha["modelo"], total=linha["total"], caminho_pdf=linha["caminho_pdf"],
            os_numero=linha["os_numero"],
        )
        for linha in conn.execute(sql, parametros)
    ]


def montar_os(conn: sqlite3.Connection, orcamento_id: int) -> OrdemServico:
    """Cria (sem salvar) uma OS preenchida com os dados do orçamento.

    Se a placa já for conhecida, também preenche ano e dados do cliente.
    """
    orcamento = carregar(conn, orcamento_id)
    if orcamento is None:
        raise ErroValidacao("Orçamento não encontrado.")
    os_ = OrdemServico(
        placa=orcamento.placa,
        modelo=orcamento.modelo,
        itens=[Item(i.descricao, i.tipo, i.quantidade, i.valor_unitario) for i in orcamento.itens],
        desconto=orcamento.desconto,
        orcamento_id=orcamento.id,
    )
    veiculo = clientes.buscar_veiculo_por_placa(conn, orcamento.placa)
    if veiculo is not None:
        os_.ano = veiculo.ano
        os_.modelo = os_.modelo or veiculo.modelo
        if veiculo.cliente_id is not None:
            cliente = clientes.obter_cliente(conn, veiculo.cliente_id)
            if cliente is not None:
                os_.cliente_id = cliente.id
                os_.cliente_nome = cliente.nome
                os_.cliente_documento = cliente.documento
                os_.cliente_telefone = cliente.telefone
    return os_


def cliente_do_orcamento(conn: sqlite3.Connection, orcamento: Orcamento) -> Cliente | None:
    """Cliente dono do carro do orçamento (pela placa), se o carro já estiver cadastrado."""
    veiculo = clientes.buscar_veiculo_por_placa(conn, orcamento.placa)
    if veiculo is None or veiculo.cliente_id is None:
        return None
    return clientes.obter_cliente(conn, veiculo.cliente_id)
