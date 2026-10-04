"""Relatório e pagamento de comissões.

Regras:
- só OS FINALIZADAS contam, pela data da OS;
- a base é o total dos itens do tipo "Mão de obra" (sem abater desconto);
- o percentual é o que estava gravado na OS quando ela foi finalizada;
- OS sem valor de comissão (ex.: mecânico cadastrado com 0%, como um sócio)
  não aparecem: não há nada a pagar.
"""

import sqlite3
from dataclasses import dataclass
from datetime import date

from oficina.banco import para_data
from oficina.modelos import STATUS_FINALIZADA

SITUACAO_TODAS = "todas"
SITUACAO_PENDENTES = "pendentes"
SITUACAO_PAGAS = "pagas"


@dataclass
class LinhaComissao:
    os_id: int
    numero: int
    data: date
    mecanico_id: int
    mecanico_nome: str
    placa: str
    modelo: str
    cliente_nome: str
    mao_de_obra: int
    percentual: float
    comissao: int
    paga: bool
    data_pagamento: date | None


@dataclass
class ResumoMecanico:
    mecanico_id: int
    mecanico_nome: str
    quantidade_os: int = 0
    mao_de_obra: int = 0
    comissao: int = 0
    paga: int = 0
    pendente: int = 0


def listar(conn: sqlite3.Connection, inicio: date, fim: date, mecanico_id: int | None = None,
           situacao: str = SITUACAO_TODAS) -> list[LinhaComissao]:
    sql = """
        SELECT * FROM ordens_servico
        WHERE status = ? AND comissao > 0 AND data BETWEEN ? AND ?
    """
    parametros: list = [STATUS_FINALIZADA, inicio.isoformat(), fim.isoformat()]
    if mecanico_id is not None:
        sql += " AND mecanico_id = ?"
        parametros.append(mecanico_id)
    if situacao == SITUACAO_PENDENTES:
        sql += " AND comissao_paga = 0"
    elif situacao == SITUACAO_PAGAS:
        sql += " AND comissao_paga = 1"
    sql += " ORDER BY data, numero"
    return [
        LinhaComissao(
            os_id=linha["id"], numero=linha["numero"], data=para_data(linha["data"]),
            mecanico_id=linha["mecanico_id"], mecanico_nome=linha["mecanico_nome"], placa=linha["placa"],
            modelo=linha["modelo"], cliente_nome=linha["cliente_nome"], mao_de_obra=linha["total_mao_de_obra"],
            percentual=linha["percentual_comissao"], comissao=linha["comissao"], paga=bool(linha["comissao_paga"]),
            data_pagamento=para_data(linha["data_pagamento_comissao"]),
        )
        for linha in conn.execute(sql, parametros)
    ]


def resumir_por_mecanico(linhas: list[LinhaComissao]) -> list[ResumoMecanico]:
    resumos: dict[int, ResumoMecanico] = {}
    for linha in linhas:
        resumo = resumos.setdefault(linha.mecanico_id, ResumoMecanico(linha.mecanico_id, linha.mecanico_nome))
        resumo.quantidade_os += 1
        resumo.mao_de_obra += linha.mao_de_obra
        resumo.comissao += linha.comissao
        if linha.paga:
            resumo.paga += linha.comissao
        else:
            resumo.pendente += linha.comissao
    return sorted(resumos.values(), key=lambda r: r.mecanico_nome.casefold())


def marcar_como_pagas(conn: sqlite3.Connection, os_ids: list[int], data_pagamento: date) -> int:
    """Marca a comissão das OS como paga. Devolve quantas foram alteradas."""
    with conn:
        cursor = conn.executemany(
            "UPDATE ordens_servico SET comissao_paga = 1, data_pagamento_comissao = ? "
            "WHERE id = ? AND status = ? AND comissao_paga = 0 AND comissao > 0",
            [(data_pagamento.isoformat(), os_id, STATUS_FINALIZADA) for os_id in os_ids],
        )
        return cursor.rowcount


def desfazer_pagamento(conn: sqlite3.Connection, os_ids: list[int]) -> int:
    with conn:
        cursor = conn.executemany(
            "UPDATE ordens_servico SET comissao_paga = 0, data_pagamento_comissao = NULL WHERE id = ? AND comissao_paga = 1",
            [(os_id,) for os_id in os_ids],
        )
        return cursor.rowcount


def pendentes_por_mecanico(conn: sqlite3.Connection) -> list[ResumoMecanico]:
    """Comissões ainda não pagas de todas as datas, por mecânico (para o painel)."""
    linhas = conn.execute(
        """SELECT mecanico_id, mecanico_nome, COUNT(*) AS qtd, SUM(total_mao_de_obra) AS mao, SUM(comissao) AS com
           FROM ordens_servico
           WHERE status = ? AND comissao_paga = 0 AND comissao > 0
           GROUP BY mecanico_id ORDER BY mecanico_nome COLLATE NOCASE""",
        (STATUS_FINALIZADA,),
    )
    return [
        ResumoMecanico(l["mecanico_id"], l["mecanico_nome"], l["qtd"], l["mao"], l["com"], 0, l["com"])
        for l in linhas
    ]


def data_mais_antiga_pendente(conn: sqlite3.Connection, mecanico_id: int | None = None) -> date | None:
    sql = "SELECT MIN(data) FROM ordens_servico WHERE status = ? AND comissao_paga = 0 AND comissao > 0"
    parametros: list = [STATUS_FINALIZADA]
    if mecanico_id is not None:
        sql += " AND mecanico_id = ?"
        parametros.append(mecanico_id)
    return para_data(conn.execute(sql, parametros).fetchone()[0])


def mecanicos_com_comissao(conn: sqlite3.Connection) -> set[int]:
    """Mecânicos que já tiveram alguma comissão (para o filtro da tela de comissões)."""
    return {linha[0] for linha in conn.execute(
        "SELECT DISTINCT mecanico_id FROM ordens_servico WHERE comissao > 0 AND mecanico_id IS NOT NULL")}
