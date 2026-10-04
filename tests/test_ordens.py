from datetime import date

import pytest

from conftest import item, nova_os
from oficina.modelos import ErroValidacao, Mecanico, calcular_totais
from oficina.servicos import catalogo, clientes, mecanicos, ordens
from oficina.servicos import configuracoes as cfg


def test_totais_separam_tipos_e_desconto_nao_reduz_comissao():
    itens = [
        item("Pivô", "peca", 2, 5000),
        item("Troca de pivô", "mao_de_obra", 1, 12000),
        item("Retífica", "terceiros", 1, 30000),
    ]
    totais = calcular_totais(itens, desconto=2000, percentual_comissao=30)
    assert totais.pecas == 10000
    assert totais.mao_de_obra == 12000
    assert totais.terceiros == 30000
    assert totais.subtotal == 52000
    assert totais.total == 50000
    assert totais.comissao == 3600  # 30% de 120,00, desconto não afeta


def test_salvar_os_nova_numera_e_grava_totais(conn, mecanico):
    cfg.salvar(conn, {cfg.PROXIMO_NUMERO_OS: 1002})
    salva = ordens.salvar(conn, nova_os(mecanico.id, desconto=1000), "finalizada")

    assert salva.numero == 1002
    assert ordens.proximo_numero(conn) == 1003
    assert salva.mecanico_nome == "Marcos"
    assert salva.percentual_comissao == 30
    assert len(salva.itens) == 2
    assert salva.totais.total == 50000 + 15000 - 1000
    assert salva.totais.comissao == 4500

    linha = conn.execute("SELECT total, comissao, total_mao_de_obra FROM ordens_servico").fetchone()
    assert tuple(linha) == (64000, 4500, 15000)


def test_finalizar_exige_mecanico_e_itens(conn, mecanico):
    with pytest.raises(ErroValidacao, match="mecânico"):
        ordens.salvar(conn, nova_os(None), "finalizada")
    with pytest.raises(ErroValidacao, match="item"):
        ordens.salvar(conn, nova_os(mecanico.id, itens=[]), "finalizada")
    # Em aberto pode ficar sem mecânico
    assert ordens.salvar(conn, nova_os(None), "aberta").numero == 1000


def test_desconto_maior_que_itens_e_recusado(conn, mecanico):
    with pytest.raises(ErroValidacao, match="desconto"):
        ordens.salvar(conn, nova_os(mecanico.id, desconto=10_000_000), "finalizada")


def test_percentual_fica_congelado_depois_de_finalizada(conn, mecanico):
    salva = ordens.salvar(conn, nova_os(mecanico.id), "finalizada")

    mecanico.percentual_comissao = 40
    mecanicos.salvar(conn, mecanico)

    salva.observacoes = "editada depois"
    editada = ordens.salvar(conn, salva, "finalizada")
    assert editada.percentual_comissao == 30
    assert editada.totais.comissao == 4500


def test_os_em_aberto_usa_percentual_atual_ao_finalizar(conn, mecanico):
    aberta = ordens.salvar(conn, nova_os(mecanico.id), "aberta")
    mecanico.percentual_comissao = 40
    mecanicos.salvar(conn, mecanico)
    finalizada = ordens.salvar(conn, aberta, "finalizada")
    assert finalizada.percentual_comissao == 40


def test_trocar_mecanico_usa_percentual_do_novo(conn, mecanico):
    outro_id = mecanicos.salvar(conn, Mecanico(nome="Bruno", percentual_comissao=20))
    salva = ordens.salvar(conn, nova_os(mecanico.id), "finalizada")
    salva.mecanico_id = outro_id
    editada = ordens.salvar(conn, salva, "finalizada")
    assert editada.mecanico_nome == "Bruno"
    assert editada.percentual_comissao == 20


def test_edicao_substitui_itens_e_mantem_numero(conn, mecanico):
    salva = ordens.salvar(conn, nova_os(mecanico.id), "finalizada")
    salva.itens = [item("Alinhamento", "mao_de_obra", 1, 8000)]
    editada = ordens.salvar(conn, salva, "finalizada")
    assert editada.numero == salva.numero
    assert [i.descricao for i in editada.itens] == ["Alinhamento"]
    assert conn.execute("SELECT COUNT(*) FROM itens_os").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM ordens_servico").fetchone()[0] == 1


def test_os_cancelada_nao_pode_ser_editada_ate_reativar(conn, mecanico):
    salva = ordens.salvar(conn, nova_os(mecanico.id), "finalizada")
    ordens.cancelar(conn, salva.id)
    with pytest.raises(ErroValidacao, match="cancelada"):
        ordens.salvar(conn, salva, "finalizada")
    ordens.reativar(conn, salva.id)
    assert ordens.carregar(conn, salva.id).status == "aberta"


def test_salvar_os_cadastra_cliente_veiculo_e_catalogo(conn, mecanico):
    ordens.salvar(conn, nova_os(mecanico.id), "finalizada")

    veiculo = clientes.buscar_veiculo_por_placa(conn, "abc-1d23")
    assert veiculo is not None and veiculo.modelo == "Gol" and veiculo.ultimo_km == "120000"
    assert veiculo.cliente_nome == "João da Silva"

    sugestao = catalogo.obter_por_descricao(conn, "troca de amortecedor")
    assert sugestao.tipo == "mao_de_obra" and sugestao.valor_unitario == 15000

    # Segunda OS do mesmo cliente (achado pelo CPF) não duplica o cadastro
    ordens.salvar(conn, nova_os(mecanico.id, cliente_nome="João Silva", placa="XYZ9876"), "finalizada")
    assert len(clientes.listar_clientes(conn)) == 1
    assert len(clientes.listar_veiculos(conn)) == 2


def test_catalogo_nao_e_sobrescrito_por_os_antiga(conn, mecanico):
    ordens.salvar(conn, nova_os(mecanico.id, data=date(2026, 9, 20)), "finalizada")
    antiga = ordens.salvar(conn, nova_os(mecanico.id, data=date(2026, 1, 10)), "finalizada")
    antiga.itens[1].valor_unitario = 999
    ordens.salvar(conn, antiga, "finalizada")
    assert catalogo.obter_por_descricao(conn, "Troca de amortecedor").valor_unitario == 15000


def test_buscar_por_placa_cliente_sem_acento_e_numero(conn, mecanico):
    ordens.salvar(conn, nova_os(mecanico.id), "finalizada")
    ordens.salvar(conn, nova_os(mecanico.id, placa="QWE-1234", cliente_nome="Maria", cliente_documento=""), "aberta")

    assert [r.numero for r in ordens.buscar(conn, "abc1d23")] == [1000]
    assert [r.numero for r in ordens.buscar(conn, "qwe1234")] == [1001]
    assert [r.numero for r in ordens.buscar(conn, "joao")] == [1000]
    assert [r.numero for r in ordens.buscar(conn, "1001")] == [1001]
    assert [r.numero for r in ordens.buscar(conn, status="aberta")] == [1001]


def test_numeracao_nunca_repete_mesmo_com_configuracao_menor(conn, mecanico):
    ordens.salvar(conn, nova_os(mecanico.id), "finalizada")
    cfg.salvar(conn, {cfg.PROXIMO_NUMERO_OS: 500})
    assert ordens.salvar(conn, nova_os(mecanico.id), "finalizada").numero == 1001
