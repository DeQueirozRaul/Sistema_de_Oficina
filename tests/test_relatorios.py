import csv
from datetime import date

import pytest

from conftest import item, nova_os
from oficina.modelos import Mecanico, Orcamento
from oficina.servicos import mecanicos, orcamentos, ordens, relatorios


def _os(conn, mecanico_id, dia, itens, status="finalizada", **campos):
    return ordens.salvar(conn, nova_os(mecanico_id, data=dia, itens=itens, **campos), status)


@pytest.fixture
def cenario(conn, mecanico):
    """Marcos (30%) e um sócio (0%) com OS em setembro e outubro de 2026."""
    socio_id = mecanicos.salvar(conn, Mecanico(nome="Sócio", percentual_comissao=0))
    _os(conn, mecanico.id, date(2026, 9, 1), [item("Amortecedor", "peca", 2, 20000), item("Troca", "mao_de_obra", 1, 10000)],
        desconto=5000)
    _os(conn, mecanico.id, date(2026, 9, 15), [item("amortecedor ", "peca", 1, 20000), item("Alinhamento", "terceiros", 1, 8000)],
        cliente_nome="Ana", cliente_documento="", cliente_telefone="(00) 98888-0000", placa="AAA1A11")
    _os(conn, socio_id, date(2026, 10, 2), [item("Troca", "mao_de_obra", 1, 30000)])
    _os(conn, mecanico.id, date(2026, 10, 3), [item("Não conta", "peca", 1, 99900)], status="aberta")
    cancelada = _os(conn, mecanico.id, date(2026, 10, 3), [item("Não conta", "peca", 1, 88800)])
    ordens.cancelar(conn, cancelada.id)
    return mecanico.id, socio_id


def test_agrupamento_escolhido_pelo_tamanho_do_periodo():
    assert relatorios.agrupamento_para(date(2026, 10, 5), date(2026, 10, 11)) == relatorios.DIA
    assert relatorios.agrupamento_para(date(2026, 10, 1), date(2026, 10, 31)) == relatorios.SEMANA
    assert relatorios.agrupamento_para(date(2025, 11, 1), date(2026, 10, 31)) == relatorios.MES


def test_faturamento_por_mes_inclui_meses_sem_movimento(conn, cenario):
    fatias = relatorios.faturamento_por_periodo(conn, date(2026, 8, 1), date(2026, 10, 31), relatorios.MES)
    assert [(f.rotulo, f.quantidade_os, f.bruto, f.descontos, f.total) for f in fatias] == [
        ("ago/26", 0, 0, 0, 0),
        ("set/26", 2, 50000 + 28000, 5000, 45000 + 28000),
        ("out/26", 1, 30000, 0, 30000),
    ]
    setembro = fatias[1]
    assert (setembro.pecas, setembro.mao_de_obra, setembro.terceiros) == (60000, 10000, 8000)
    assert setembro.titulo == "Setembro de 2026" and setembro.ticket_medio == 36500


def test_faturamento_por_semana_e_por_dia(conn, cenario):
    semanas = relatorios.faturamento_por_periodo(conn, date(2026, 9, 1), date(2026, 9, 30))
    assert semanas[0].inicio == date(2026, 9, 1)  # a semana de 31/08 é cortada no início do período
    assert semanas[0].titulo == "Semana de 01/09 a 06/09/2026"
    assert semanas[1].titulo == "Semana de 07/09 a 13/09/2026" and semanas[-1].fim == date(2026, 9, 30)
    assert [f.quantidade_os for f in semanas] == [1, 0, 1, 0, 0]

    dias = relatorios.faturamento_por_periodo(conn, date(2026, 9, 28), date(2026, 10, 4))
    assert [f.rotulo for f in dias] == ["28/09", "29/09", "30/09", "01/10", "02/10"]  # sem sábado e domingo vazios
    assert dias[-1].titulo == "Sexta, 02/10/2026" and dias[-1].total == 30000


def test_itens_mais_vendidos_soma_descricoes_parecidas(conn, cenario):
    itens = relatorios.itens_mais_vendidos(conn, date(2026, 9, 1), date(2026, 10, 31))
    assert [(i.descricao, i.tipo, i.quantidade, i.vezes, i.total) for i in itens] == [
        ("Amortecedor", "peca", 3, 2, 60000),
        ("Troca", "mao_de_obra", 2, 2, 40000),
        ("Alinhamento", "terceiros", 1, 1, 8000),
    ]
    assert [i.descricao for i in relatorios.itens_mais_vendidos(conn, date(2026, 9, 1), date(2026, 10, 31),
                                                                 limite=1, tipo="mao_de_obra")] == ["Troca"]


def test_desempenho_dos_mecanicos(conn, cenario):
    marcos_id, socio_id = cenario
    desempenho = relatorios.desempenho_mecanicos(conn, date(2026, 9, 1), date(2026, 10, 31))
    assert [(d.mecanico_id, d.nome, d.quantidade_os, d.faturamento, d.mao_de_obra, d.comissao) for d in desempenho] == [
        (socio_id, "Sócio", 1, 30000, 30000, 0),
        (marcos_id, "Marcos", 2, 73000, 10000, 3000),
    ]
    assert desempenho[1].ticket_medio == 36500


def test_clientes_novos_e_que_voltaram(conn, cenario):
    # João (cliente padrão) veio em 01/09 e 02/10; Ana só em 15/09.
    assert relatorios.clientes_atendidos(conn, date(2026, 9, 1), date(2026, 9, 30)) == relatorios.Clientes(2, 2, 0)
    outubro = relatorios.clientes_atendidos(conn, date(2026, 10, 1), date(2026, 10, 31))
    assert (outubro.atendidos, outubro.novos, outubro.ja_eram_clientes, outubro.voltaram) == (1, 0, 1, 0)
    assert relatorios.clientes_atendidos(conn, date(2026, 9, 1), date(2026, 10, 31)) == relatorios.Clientes(2, 2, 1)


def test_movimento_por_dia_da_semana(conn, cenario):
    dias = relatorios.movimento_por_dia_da_semana(conn, date(2026, 9, 1), date(2026, 10, 31))
    assert [(d.nome, d.quantidade_os) for d in dias] == [
        ("Segunda", 0), ("Terça", 2), ("Quarta", 0), ("Quinta", 0), ("Sexta", 1)]  # sem sábado/domingo vazios
    assert dias[1].faturamento == 45000 + 28000
    _os(conn, cenario[0], date(2026, 10, 3), [item()])  # um sábado com OS passa a aparecer
    assert relatorios.movimento_por_dia_da_semana(conn, date(2026, 9, 1), date(2026, 10, 31))[-1].nome == "Sábado"


def test_conversao_de_orcamentos(conn, mecanico):
    assert relatorios.conversao_orcamentos(conn, date(2026, 9, 1), date(2026, 9, 30)).taxa is None
    feitos = [orcamentos.salvar(conn, Orcamento(data=date(2026, 9, d), placa="ABC1D23", modelo="Gol",
                                                itens=[item()])) for d in (1, 2, 3, 4)]
    _os(conn, mecanico.id, date(2026, 9, 5), [item()], orcamento_id=feitos[0].id)
    cancelada = _os(conn, mecanico.id, date(2026, 9, 5), [item()], orcamento_id=feitos[1].id)
    ordens.cancelar(conn, cancelada.id)  # OS cancelada: o orçamento não conta como aprovado
    conversao = relatorios.conversao_orcamentos(conn, date(2026, 9, 1), date(2026, 9, 30))
    assert (conversao.orcamentos, conversao.aprovados, conversao.taxa) == (4, 1, 0.25)


def test_exportar_csv_no_padrao_do_excel_brasileiro(conn, cenario, tmp_path):
    caminho = relatorios.exportar_csv(conn, date(2026, 9, 1), date(2026, 10, 31), tmp_path / "os.csv")
    assert caminho.read_bytes().startswith(b"\xef\xbb\xbf")  # BOM: o Excel reconhece os acentos
    with caminho.open(encoding="utf-8-sig", newline="") as arquivo:
        linhas = list(csv.reader(arquivo, delimiter=";"))
    assert linhas[0] == relatorios.COLUNAS_OS
    assert len(linhas) == 4  # cabeçalho + 3 OS finalizadas
    primeira = dict(zip(linhas[0], linhas[1]))
    assert primeira["Data"] == "01/09/2026"
    assert (primeira["Peças"], primeira["Desconto"], primeira["Total"]) == ("400,00", "50,00", "450,00")
    assert primeira["Comissão"] == "30,00" and primeira["Comissão paga"] == "Não"
    socio = dict(zip(linhas[0], linhas[3]))
    assert socio["Comissão"] == "0,00" and socio["Comissão paga"] == ""


def test_exportar_excel(conn, cenario, tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    caminho = relatorios.exportar_excel(conn, date(2026, 9, 1), date(2026, 10, 31), tmp_path / "relatorio.xlsx")
    livro = openpyxl.load_workbook(caminho)
    assert livro.sheetnames == ["Resumo", "Faturamento", "Itens", "Mecânicos", "OS"]

    resumo = {linha[0]: linha[1] for linha in livro["Resumo"].iter_rows(min_row=2, values_only=True)}
    assert resumo["OS finalizadas"] == 3 and resumo["Faturamento"] == 1030.0
    assert livro["Resumo"]["B4"].number_format == '"R$" #,##0.00'

    os_ = livro["OS"]
    assert [c.value for c in os_[1]] == relatorios.COLUNAS_OS
    assert os_["B2"].value.date() == date(2026, 9, 1) and os_["B2"].number_format == "DD/MM/YYYY"
    assert os_["K2"].value == 450.0 and os_.max_row == 4
    assert [linha[0] for linha in livro["Mecânicos"].iter_rows(min_row=2, values_only=True)] == ["Sócio", "Marcos"]
