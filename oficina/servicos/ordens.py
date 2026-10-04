"""Ordens de serviço: salvar, carregar, buscar, cancelar."""

import sqlite3
from dataclasses import dataclass
from datetime import date

from oficina.banco import agora, para_data
from oficina.modelos import (
    STATUS_ABERTA, STATUS_CANCELADA, STATUS_FINALIZADA, STATUS_OS,
    ErroValidacao, Item, OrdemServico, calcular_totais, validar_itens,
)
from oficina.servicos import catalogo, clientes, mecanicos, numeracao
from oficina.servicos import configuracoes as cfg
from oficina.servicos.clientes import normalizar_placa


def proximo_numero(conn: sqlite3.Connection) -> int:
    return numeracao.proximo_numero(conn, cfg.PROXIMO_NUMERO_OS)


def _validar(os_: OrdemServico, status: str) -> None:
    if status not in (STATUS_ABERTA, STATUS_FINALIZADA):
        raise ErroValidacao("Situação inválida para salvar a OS.")
    validar_itens(os_.itens, os_.desconto)
    if status == STATUS_FINALIZADA:
        if not os_.itens:
            raise ErroValidacao("Adicione pelo menos um item à OS.")
        if os_.mecanico_id is None:
            raise ErroValidacao("Escolha o mecânico responsável pela OS.")
    elif not (os_.itens or os_.placa.strip() or os_.cliente_nome.strip()):
        raise ErroValidacao("Preencha pelo menos a placa, o cliente ou um item antes de salvar.")


def percentual_para(os_anterior: OrdemServico | None, mecanico_id: int | None,
                    percentual_atual_mecanico: float) -> float:
    """Percentual de comissão a gravar na OS.

    Depois que a OS é finalizada o percentual fica congelado: se o cadastro do
    mecânico mudar de 30% para 35%, as OS já finalizadas continuam com 30%.
    O percentual só é atualizado se a OS ainda estava em aberto ou se o
    mecânico da OS foi trocado.
    """
    if (os_anterior is not None and os_anterior.status == STATUS_FINALIZADA
            and os_anterior.mecanico_id == mecanico_id):
        return os_anterior.percentual_comissao
    return percentual_atual_mecanico


def salvar(conn: sqlite3.Connection, os_: OrdemServico, status: str) -> OrdemServico:
    """Grava a OS (nova ou existente) com seus itens numa única transação.

    Também atualiza o cadastro do cliente/veículo e o catálogo de itens.
    Devolve a OS como ficou gravada (com número e id).
    """
    _validar(os_, status)
    anterior = carregar(conn, os_.id) if os_.id is not None else None
    if anterior is not None and anterior.status == STATUS_CANCELADA:
        raise ErroValidacao("Esta OS está cancelada. Reative-a pelo Histórico para poder editar.")

    mecanico_nome, percentual = "", 0.0
    if os_.mecanico_id is not None:
        mecanico = mecanicos.obter(conn, os_.mecanico_id)
        if mecanico is None:
            raise ErroValidacao("O mecânico escolhido não existe mais. Escolha outro.")
        mecanico_nome = mecanico.nome
        percentual = percentual_para(anterior, os_.mecanico_id, mecanico.percentual_comissao)

    totais = calcular_totais(os_.itens, os_.desconto, percentual)
    momento = agora()

    with conn:
        cliente_id = clientes.registrar_cliente(
            conn, os_.cliente_id, os_.cliente_nome, os_.cliente_documento, os_.cliente_telefone
        )
        veiculo_id = clientes.registrar_veiculo(conn, os_.placa, os_.modelo, os_.ano, os_.km, cliente_id)
        campos = {
            "status": status,
            "data": os_.data.isoformat(),
            "mecanico_id": os_.mecanico_id,
            "mecanico_nome": mecanico_nome,
            "percentual_comissao": percentual,
            "cliente_id": cliente_id,
            "cliente_nome": os_.cliente_nome.strip(),
            "cliente_documento": os_.cliente_documento.strip(),
            "cliente_telefone": os_.cliente_telefone.strip(),
            "veiculo_id": veiculo_id,
            "placa": os_.placa.strip().upper(),
            "modelo": os_.modelo.strip(),
            "ano": os_.ano.strip(),
            "km": os_.km.strip(),
            "desconto": os_.desconto,
            "total_pecas": totais.pecas,
            "total_mao_de_obra": totais.mao_de_obra,
            "total_terceiros": totais.terceiros,
            "total": totais.total,
            "comissao": totais.comissao,
            "observacoes": os_.observacoes.strip(),
            "orcamento_id": os_.orcamento_id,
            "atualizado_em": momento,
        }
        if anterior is None:
            campos["numero"] = numeracao.reservar_numero(conn, cfg.PROXIMO_NUMERO_OS)
            campos["criado_em"] = momento
            colunas = ", ".join(campos)
            marcadores = ", ".join("?" for _ in campos)
            os_id = conn.execute(
                f"INSERT INTO ordens_servico ({colunas}) VALUES ({marcadores})", list(campos.values())
            ).lastrowid
        else:
            os_id = anterior.id
            atribuicoes = ", ".join(f"{coluna} = ?" for coluna in campos)
            conn.execute(f"UPDATE ordens_servico SET {atribuicoes} WHERE id = ?", [*campos.values(), os_id])
            conn.execute("DELETE FROM itens_os WHERE os_id = ?", (os_id,))

        conn.executemany(
            "INSERT INTO itens_os (os_id, posicao, descricao, tipo, quantidade, valor_unitario, total)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(os_id, posicao, item.descricao.strip(), item.tipo, item.quantidade, item.valor_unitario, item.total)
             for posicao, item in enumerate(os_.itens, start=1)],
        )
        catalogo.registrar_itens(conn, os_.itens, os_.data)

    return carregar(conn, os_id)


def carregar(conn: sqlite3.Connection, os_id: int) -> OrdemServico | None:
    linha = conn.execute("SELECT * FROM ordens_servico WHERE id = ?", (os_id,)).fetchone()
    if linha is None:
        return None
    itens = [
        Item(descricao=i["descricao"], tipo=i["tipo"], quantidade=i["quantidade"], valor_unitario=i["valor_unitario"])
        for i in conn.execute("SELECT * FROM itens_os WHERE os_id = ? ORDER BY posicao", (os_id,))
    ]
    return OrdemServico(
        id=linha["id"],
        numero=linha["numero"],
        status=linha["status"],
        data=para_data(linha["data"]),
        mecanico_id=linha["mecanico_id"],
        mecanico_nome=linha["mecanico_nome"],
        percentual_comissao=linha["percentual_comissao"],
        cliente_id=linha["cliente_id"],
        cliente_nome=linha["cliente_nome"],
        cliente_documento=linha["cliente_documento"],
        cliente_telefone=linha["cliente_telefone"],
        veiculo_id=linha["veiculo_id"],
        placa=linha["placa"],
        modelo=linha["modelo"],
        ano=linha["ano"],
        km=linha["km"],
        itens=itens,
        desconto=linha["desconto"],
        observacoes=linha["observacoes"],
        orcamento_id=linha["orcamento_id"],
        comissao_paga=bool(linha["comissao_paga"]),
        data_pagamento_comissao=para_data(linha["data_pagamento_comissao"]),
        caminho_pdf=linha["caminho_pdf"],
    )


def definir_caminho_pdf(conn: sqlite3.Connection, os_id: int, caminho: str) -> None:
    with conn:
        conn.execute("UPDATE ordens_servico SET caminho_pdf = ? WHERE id = ?", (caminho, os_id))


def cancelar(conn: sqlite3.Connection, os_id: int) -> None:
    with conn:
        conn.execute(
            "UPDATE ordens_servico SET status = ?, atualizado_em = ? WHERE id = ?",
            (STATUS_CANCELADA, agora(), os_id),
        )


def reativar(conn: sqlite3.Connection, os_id: int) -> None:
    """Cancelada -> em aberto (para ser conferida e finalizada de novo)."""
    with conn:
        conn.execute(
            "UPDATE ordens_servico SET status = ?, atualizado_em = ? WHERE id = ? AND status = ?",
            (STATUS_ABERTA, agora(), os_id, STATUS_CANCELADA),
        )


@dataclass
class ResumoOS:
    """Linha da listagem de OS (sem os itens)."""
    id: int
    numero: int
    data: date
    status: str
    placa: str
    modelo: str
    cliente_nome: str
    mecanico_nome: str
    total: int
    total_mao_de_obra: int
    comissao: int
    comissao_paga: bool
    caminho_pdf: str

    @property
    def status_texto(self) -> str:
        return STATUS_OS[self.status]


def _para_resumo(linha: sqlite3.Row) -> ResumoOS:
    return ResumoOS(
        id=linha["id"], numero=linha["numero"], data=para_data(linha["data"]), status=linha["status"],
        placa=linha["placa"], modelo=linha["modelo"], cliente_nome=linha["cliente_nome"],
        mecanico_nome=linha["mecanico_nome"], total=linha["total"], total_mao_de_obra=linha["total_mao_de_obra"],
        comissao=linha["comissao"], comissao_paga=bool(linha["comissao_paga"]), caminho_pdf=linha["caminho_pdf"],
    )


def buscar(conn: sqlite3.Connection, busca: str = "", status: str | None = None,
           inicio: date | None = None, fim: date | None = None, limite: int | None = None) -> list[ResumoOS]:
    """Lista OS filtrando por texto (nº, placa, cliente, modelo, mecânico), situação e período."""
    condicoes, parametros = [], []
    busca = busca.strip()
    if busca:
        opcoes = [
            "normalizar(cliente_nome) LIKE '%' || normalizar(?) || '%'",
            "normalizar(modelo) LIKE '%' || normalizar(?) || '%'",
            "normalizar(mecanico_nome) LIKE '%' || normalizar(?) || '%'",
        ]
        parametros += [busca, busca, busca]
        if normalizar_placa(busca):
            opcoes.append("REPLACE(REPLACE(UPPER(placa), '-', ''), ' ', '') LIKE '%' || ? || '%'")
            parametros.append(normalizar_placa(busca))
        if busca.isdigit():
            opcoes.append("numero = ?")
            parametros.append(int(busca))
        condicoes.append("(" + " OR ".join(opcoes) + ")")
    if status:
        condicoes.append("status = ?")
        parametros.append(status)
    if inicio:
        condicoes.append("data >= ?")
        parametros.append(inicio.isoformat())
    if fim:
        condicoes.append("data <= ?")
        parametros.append(fim.isoformat())
    sql = "SELECT * FROM ordens_servico"
    if condicoes:
        sql += " WHERE " + " AND ".join(condicoes)
    sql += " ORDER BY numero DESC"
    if limite:
        sql += f" LIMIT {int(limite)}"
    return [_para_resumo(linha) for linha in conn.execute(sql, parametros)]


def os_do_orcamento(conn: sqlite3.Connection, orcamento_id: int) -> ResumoOS | None:
    """OS (não cancelada) criada a partir do orçamento, se houver."""
    linha = conn.execute(
        "SELECT * FROM ordens_servico WHERE orcamento_id = ? AND status <> ? ORDER BY numero DESC LIMIT 1",
        (orcamento_id, STATUS_CANCELADA),
    ).fetchone()
    return _para_resumo(linha) if linha else None
