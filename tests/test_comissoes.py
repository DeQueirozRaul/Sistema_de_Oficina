from datetime import date

from conftest import item, nova_os
from oficina.modelos import Mecanico
from oficina.periodos import deslocar_mes, mes, semana
from oficina.servicos import comissoes, mecanicos, ordens, painel


def _cenario(conn, mecanico):
    """Marcos (30%) e Bruno (20%) com OS em datas diferentes."""
    bruno_id = mecanicos.salvar(conn, Mecanico(nome="Bruno", percentual_comissao=20))
    mao = lambda valor: [item("Peça", "peca", 1, 50000), item("Serviço", "mao_de_obra", 1, valor)]
    ordens.salvar(conn, nova_os(mecanico.id, data=date(2026, 9, 22), itens=mao(10000)), "finalizada")  # seg
    ordens.salvar(conn, nova_os(mecanico.id, data=date(2026, 9, 26), itens=mao(20000)), "finalizada")  # sex
    ordens.salvar(conn, nova_os(bruno_id, data=date(2026, 9, 23), itens=mao(30000)), "finalizada")
    ordens.salvar(conn, nova_os(mecanico.id, data=date(2026, 9, 29), itens=mao(40000)), "finalizada")  # outra semana
    ordens.salvar(conn, nova_os(mecanico.id, data=date(2026, 9, 24), itens=mao(99900)), "aberta")  # não conta
    cancelada = ordens.salvar(conn, nova_os(mecanico.id, data=date(2026, 9, 24), itens=mao(88800)), "finalizada")
    ordens.cancelar(conn, cancelada.id)  # não conta
    ordens.salvar(conn, nova_os(mecanico.id, data=date(2026, 9, 25), itens=[item("Só peça", "peca", 1, 100)]), "finalizada")
    return bruno_id


def test_periodos():
    assert semana(date(2026, 9, 25)) == (date(2026, 9, 21), date(2026, 9, 27))
    assert semana(date(2026, 9, 21)) == (date(2026, 9, 21), date(2026, 9, 27))
    assert mes(date(2026, 2, 10)) == (date(2026, 2, 1), date(2026, 2, 28))
    assert deslocar_mes(date(2026, 1, 31), -1) == date(2025, 12, 1)
    assert deslocar_mes(date(2026, 12, 5), 1) == date(2027, 1, 1)


def test_relatorio_semanal_so_conta_finalizadas_com_mao_de_obra(conn, mecanico):
    _cenario(conn, mecanico)
    linhas = comissoes.listar(conn, *semana(date(2026, 9, 24)))
    assert [(l.mecanico_nome, l.mao_de_obra, l.comissao) for l in linhas] == [
        ("Marcos", 10000, 3000),
        ("Bruno", 30000, 6000),
        ("Marcos", 20000, 6000),
    ]
    resumo = comissoes.resumir_por_mecanico(linhas)
    assert [(r.mecanico_nome, r.quantidade_os, r.comissao, r.pendente) for r in resumo] == [
        ("Bruno", 1, 6000, 6000),
        ("Marcos", 2, 9000, 9000),
    ]  # em ordem alfabética


def test_filtro_mensal_por_mecanico(conn, mecanico):
    bruno_id = _cenario(conn, mecanico)
    marcos = comissoes.listar(conn, *mes(date(2026, 9, 1)), mecanico_id=mecanico.id)
    assert sum(l.comissao for l in marcos) == 3000 + 6000 + 12000
    bruno = comissoes.listar(conn, date(2026, 9, 1), date(2026, 9, 30), mecanico_id=bruno_id)
    assert [l.comissao for l in bruno] == [6000]


def test_marcar_como_paga_e_filtrar_pendentes(conn, mecanico):
    _cenario(conn, mecanico)
    inicio, fim = semana(date(2026, 9, 24))
    linhas = comissoes.listar(conn, inicio, fim, mecanico_id=mecanico.id)
    alteradas = comissoes.marcar_como_pagas(conn, [l.os_id for l in linhas], date(2026, 9, 26))
    assert alteradas == 2

    assert comissoes.listar(conn, inicio, fim, mecanico_id=mecanico.id, situacao="pendentes") == []
    pagas = comissoes.listar(conn, inicio, fim, situacao="pagas")
    assert all(l.data_pagamento == date(2026, 9, 26) for l in pagas)
    # Marcar de novo não altera nada
    assert comissoes.marcar_como_pagas(conn, [l.os_id for l in linhas], date(2026, 9, 27)) == 0

    pendentes = {r.mecanico_nome: r.pendente for r in comissoes.pendentes_por_mecanico(conn)}
    assert pendentes == {"Marcos": 12000, "Bruno": 6000}

    assert comissoes.desfazer_pagamento(conn, [linhas[0].os_id]) == 1
    assert len(comissoes.listar(conn, inicio, fim, situacao="pendentes")) == 2


def test_painel_do_mes(conn, mecanico):
    _cenario(conn, mecanico)
    resumo = painel.resumo_periodo(conn, *mes(date(2026, 9, 1)))
    assert resumo.quantidade_os == 5  # 4 com mão de obra + 1 só peça
    assert resumo.mao_de_obra == 100000
    assert resumo.pecas == 4 * 50000 + 100
    assert painel.quantidade_em_aberto(conn) == 1


def test_mecanico_com_zero_por_cento_nao_gera_comissao_a_pagar(conn, mecanico):
    """Sócio cadastrado com 0%: as OS dele não aparecem para pagamento."""
    socio_id = mecanicos.salvar(conn, Mecanico(nome="Paulo", percentual_comissao=0))
    os_socio = ordens.salvar(conn, nova_os(socio_id, data=date(2026, 9, 25)), "finalizada")
    ordens.salvar(conn, nova_os(mecanico.id, data=date(2026, 9, 25)), "finalizada")

    linhas = comissoes.listar(conn, *semana(date(2026, 9, 25)))
    assert [l.mecanico_nome for l in linhas] == ["Marcos"]
    assert [r.mecanico_nome for r in comissoes.pendentes_por_mecanico(conn)] == ["Marcos"]
    assert comissoes.marcar_como_pagas(conn, [os_socio.id], date(2026, 9, 26)) == 0
    assert comissoes.mecanicos_com_comissao(conn) == {mecanico.id}
    # A mão de obra do sócio continua contando no faturamento
    assert painel.resumo_periodo(conn, *semana(date(2026, 9, 25))).mao_de_obra == 2 * 15000
