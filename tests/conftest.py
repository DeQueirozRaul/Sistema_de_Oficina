import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from oficina.banco import conectar  # noqa: E402
from oficina.modelos import Item, Mecanico, OrdemServico  # noqa: E402
from oficina.servicos import mecanicos  # noqa: E402


@pytest.fixture
def conn():
    conexao = conectar(":memory:")
    yield conexao
    conexao.close()


@pytest.fixture
def mecanico(conn):
    """Mecânico com 30% de comissão."""
    mecanico_id = mecanicos.salvar(conn, Mecanico(nome="Marcos", percentual_comissao=30))
    return mecanicos.obter(conn, mecanico_id)


def item(descricao="Amortecedor", tipo="peca", quantidade=1, valor=10000):
    return Item(descricao=descricao, tipo=tipo, quantidade=quantidade, valor_unitario=valor)


def nova_os(mecanico_id=None, **campos):
    padrao = dict(
        mecanico_id=mecanico_id,
        cliente_nome="João da Silva",
        cliente_documento="123.456.789-00",
        cliente_telefone="(61) 99999-0000",
        placa="ABC1D23",
        modelo="Gol",
        ano="2015",
        km="120000",
        itens=[item("Amortecedor dianteiro", "peca", 2, 25000), item("Troca de amortecedor", "mao_de_obra", 1, 15000)],
    )
    padrao.update(campos)
    return OrdemServico(**padrao)
