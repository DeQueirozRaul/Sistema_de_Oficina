"""Números do painel inicial."""

import sqlite3
from dataclasses import dataclass
from datetime import date

from oficina.modelos import STATUS_ABERTA, STATUS_FINALIZADA


@dataclass
class ResumoPeriodo:
    quantidade_os: int
    faturamento: int
    mao_de_obra: int
    pecas: int
    terceiros: int
    descontos: int
    comissao: int

    @property
    def ticket_medio(self) -> int:
        return self.faturamento // self.quantidade_os if self.quantidade_os else 0


def resumo_periodo(conn: sqlite3.Connection, inicio: date, fim: date) -> ResumoPeriodo:
    linha = conn.execute(
        """SELECT COUNT(*) AS qtd,
                  COALESCE(SUM(total), 0) AS faturamento,
                  COALESCE(SUM(total_mao_de_obra), 0) AS mao,
                  COALESCE(SUM(total_pecas), 0) AS pecas,
                  COALESCE(SUM(total_terceiros), 0) AS terceiros,
                  COALESCE(SUM(desconto), 0) AS descontos,
                  COALESCE(SUM(comissao), 0) AS comissao
           FROM ordens_servico WHERE status = ? AND data BETWEEN ? AND ?""",
        (STATUS_FINALIZADA, inicio.isoformat(), fim.isoformat()),
    ).fetchone()
    return ResumoPeriodo(linha["qtd"], linha["faturamento"], linha["mao"], linha["pecas"],
                         linha["terceiros"], linha["descontos"], linha["comissao"])


def quantidade_em_aberto(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM ordens_servico WHERE status = ?", (STATUS_ABERTA,)).fetchone()[0]
