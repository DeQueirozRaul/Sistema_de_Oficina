
import pytest

from conftest import item, nova_os
from oficina.banco import conectar
from oficina.modelos import Cliente, ErroValidacao, Mecanico, Orcamento, Veiculo
from oficina.servicos import backup, catalogo, clientes, mecanicos, numeracao, orcamentos, ordens
from oficina.servicos import configuracoes as cfg


def _orcamento(**campos):
    padrao = dict(placa="abc1d23", modelo="Gol", itens=[item("Bieleta", "peca", 2, 4000),
                                                         item("Troca de bieleta", "mao_de_obra", 1, 6000)])
    padrao.update(campos)
    return Orcamento(**padrao)


def test_orcamento_numeracao_propria(conn):
    cfg.salvar(conn, {cfg.PROXIMO_NUMERO_ORCAMENTO: 2000})
    salvo = orcamentos.salvar(conn, _orcamento())
    assert salvo.numero == 2000
    assert ordens.proximo_numero(conn) == 1000
    assert salvo.totais.total == 14000


def test_orcamento_vira_os_com_dados_do_cliente(conn, mecanico):
    ordens.salvar(conn, nova_os(mecanico.id), "finalizada")  # cadastra ABC1D23 com cliente
    orcamento = orcamentos.salvar(conn, _orcamento(desconto=500))

    os_ = orcamentos.montar_os(conn, orcamento.id)
    assert os_.id is None and os_.orcamento_id == orcamento.id
    assert os_.cliente_nome == "João da Silva" and os_.ano == "2015"
    assert [(i.descricao, i.tipo) for i in os_.itens] == [("Bieleta", "peca"), ("Troca de bieleta", "mao_de_obra")]

    os_.mecanico_id = mecanico.id
    salva = ordens.salvar(conn, os_, "finalizada")
    assert ordens.os_do_orcamento(conn, orcamento.id).numero == salva.numero
    assert orcamentos.buscar(conn)[0].os_numero == salva.numero


def test_mecanico_nome_repetido_e_exclusao(conn, mecanico):
    with pytest.raises(ErroValidacao):
        mecanicos.salvar(conn, Mecanico(nome="marcos", percentual_comissao=10))
    with pytest.raises(ErroValidacao):
        mecanicos.salvar(conn, Mecanico(nome="Novo", percentual_comissao=120))
    ordens.salvar(conn, nova_os(mecanico.id), "finalizada")
    with pytest.raises(ErroValidacao, match="Desativar"):
        mecanicos.excluir(conn, mecanico.id)
    mecanicos.definir_ativo(conn, mecanico.id, False)
    assert mecanicos.listar(conn, somente_ativos=True) == []


def test_placa_duplicada_no_cadastro(conn):
    clientes.salvar_veiculo(conn, Veiculo(placa="ABC-1234"))
    with pytest.raises(ErroValidacao, match="já está cadastrada"):
        clientes.salvar_veiculo(conn, Veiculo(placa="abc1234"))


def test_excluir_cliente_mantem_os_e_solta_veiculo(conn, mecanico):
    salva = ordens.salvar(conn, nova_os(mecanico.id), "finalizada")
    clientes.excluir_cliente(conn, salva.cliente_id)
    assert ordens.carregar(conn, salva.id).cliente_nome == "João da Silva"
    assert clientes.buscar_veiculo_por_placa(conn, "ABC1D23").cliente_id is None


def test_busca_de_clientes(conn):
    clientes.salvar_cliente(conn, Cliente(nome="José Antônio", documento="111.222.333-44", telefone="(11) 98888-7777"))
    assert len(clientes.listar_clientes(conn, "jose antonio")) == 1
    assert len(clientes.listar_clientes(conn, "98888")) == 1
    assert clientes.listar_clientes(conn, "Maria") == []


def test_catalogo_editar_e_excluir(conn, mecanico):
    ordens.salvar(conn, nova_os(mecanico.id), "finalizada")
    itens = catalogo.listar(conn, "amortecedor")
    assert len(itens) == 2
    catalogo.atualizar(conn, itens[0].id, "Amortecedor dianteiro (par)", "peca", 50000)
    with pytest.raises(ErroValidacao):
        catalogo.atualizar(conn, itens[1].id, "amortecedor dianteiro (PAR)", "peca", 1)
    catalogo.excluir(conn, itens[1].id)
    assert [i.descricao for i in catalogo.listar(conn)] == ["Amortecedor dianteiro (par)"]


def test_ajuste_manual_de_numeracao(conn, mecanico):
    ordens.salvar(conn, nova_os(mecanico.id), "finalizada")
    with pytest.raises(ErroValidacao):
        numeracao.definir_proximo_numero(conn, cfg.PROXIMO_NUMERO_OS, 1000)
    numeracao.definir_proximo_numero(conn, cfg.PROXIMO_NUMERO_OS, 1500)
    assert ordens.proximo_numero(conn) == 1500


def test_backup_mantem_ultimas_copias(tmp_path, mecanico, conn):
    ordens.salvar(conn, nova_os(mecanico.id), "finalizada")
    for antigo in ("oficina_2026-01-01.db", "oficina_2026-01-02.db", "oficina_2026-01-03.db"):
        (tmp_path / antigo).write_bytes(b"")
    destino = backup.fazer_backup(conn, tmp_path, manter=2)
    assert sorted(p.name for p in tmp_path.glob("*.db")) == ["oficina_2026-01-03.db", destino.name]
    copia = conectar(destino)
    assert copia.execute("SELECT COUNT(*) FROM ordens_servico").fetchone()[0] == 1
    copia.close()
