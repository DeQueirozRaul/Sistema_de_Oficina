"""Cálculo de períodos (semana, mês) usados nos filtros."""

import calendar
from datetime import date, timedelta

MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]


def semana(dia: date) -> tuple[date, date]:
    """Semana de segunda a domingo que contém o dia.

    A oficina trabalha de segunda a sexta, mas o domingo entra no período para
    que uma OS lançada no fim de semana não fique de fora.
    """
    inicio = dia - timedelta(days=dia.weekday())
    return inicio, inicio + timedelta(days=6)


def mes(dia: date) -> tuple[date, date]:
    ultimo_dia = calendar.monthrange(dia.year, dia.month)[1]
    return dia.replace(day=1), dia.replace(day=ultimo_dia)


def deslocar_mes(dia: date, meses: int) -> date:
    indice = dia.year * 12 + (dia.month - 1) + meses
    ano, mes_ = divmod(indice, 12)
    return date(ano, mes_ + 1, 1)


def nome_mes(dia: date) -> str:
    return f"{MESES[dia.month - 1]} de {dia.year}"


def formatar_data(dia: date | None) -> str:
    return dia.strftime("%d/%m/%Y") if dia else ""
