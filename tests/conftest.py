import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # testes sem abrir janelas na tela

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


@pytest.fixture(scope="session")
def app():
    """Uma única QApplication para todos os testes que usam Qt.

    No fim da sessão as janelas são destruídas explicitamente e as tarefas em
    segundo plano são aguardadas. Sem isso, no Windows o Python podia encerrar
    com erro depois dos testes passarem (o Qt sendo destruído fora de ordem).
    """
    qt_widgets = pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtCore import QThreadPool

    aplicacao = qt_widgets.QApplication.instance() or qt_widgets.QApplication([])
    yield aplicacao
    QThreadPool.globalInstance().waitForDone(5000)
    for janela in aplicacao.topLevelWidgets():
        janela.deleteLater()  # sem close(): as janelas dos testes já foram fechadas
    aplicacao.processEvents()
    aplicacao.sendPostedEvents()
