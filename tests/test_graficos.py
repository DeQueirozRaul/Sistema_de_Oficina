import pytest

pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtCore import QPointF  # noqa: E402
from PySide6.QtGui import QColor  # noqa: E402

from oficina.ui.graficos import Barra, GraficoBarras, GraficoColunas, Serie, escala  # noqa: E402


def test_escala_com_numeros_redondos():
    assert escala(0) == (100_000, 25_000)
    assert escala(3_490_000) == (4_000_000, 1_000_000)  # R$ 34.900 -> eixo até R$ 40 mil, de 10 em 10 mil
    assert escala(245_000) == (300_000, 100_000)
    assert escala(5_000) == (6_000, 2_000)  # R$ 50 -> 0, 20, 40, 60
    assert escala(300) == (300, 100)  # nunca menos de R$ 1 por divisão, nem R$ 2,50


def _cores(widget) -> set[str]:
    imagem = widget.grab().toImage()
    return {imagem.pixelColor(x, y).name() for x in range(0, imagem.width(), 2) for y in range(0, imagem.height(), 2)}


def test_graficos_vazios_nao_quebram(app):
    for grafico in (GraficoColunas(), GraficoBarras()):
        grafico.resize(400, 200)
        cores = _cores(grafico)
        assert "#ffffff" in cores and len(cores) > 1  # fundo branco + a mensagem "Nenhuma OS..."
        assert grafico.indice_em(QPointF(100, 100)) is None


def test_colunas_empilhadas_com_espaco_entre_as_partes(app):
    grafico = GraficoColunas()
    grafico.resize(300, 260)
    vermelho, azul = Serie("A", "#ff0000"), Serie("B", "#0000ff")
    grafico.definir(["jan", "fev"], [vermelho, azul], [[50_000, 50_000], [0, 0]], ["dica jan", "dica fev"])
    imagem = grafico.grab().toImage()
    assert {"#ff0000", "#0000ff"} <= _cores(grafico)

    # Coluna de janeiro, de baixo para cima: vermelho, 2 px de branco, azul.
    x = round(grafico._area.left() + grafico._banda / 2)
    sequencia = []
    for y in range(round(grafico._area.bottom()) - 2, round(grafico._area.top()), -1):
        cor = imagem.pixelColor(x, y).name()
        if not sequencia or sequencia[-1] != cor:
            sequencia.append(cor)
    assert sequencia[:3] == ["#ff0000", "#ffffff", "#0000ff"]

    assert grafico.indice_em(QPointF(grafico._area.left() + 2, grafico._area.center().y())) == 0
    assert grafico.indice_em(QPointF(grafico._area.right() - 2, grafico._area.center().y())) == 1
    assert grafico.indice_em(QPointF(2, 2)) is None


def test_barras_horizontais_proporcionais(app):
    grafico = GraficoBarras()
    grafico.definir([Barra("Maior", 1000, "#ff0000", "1000"), Barra("Metade", 500, "#0000ff", "500")],
                    [Serie("Tipo", "#ff0000")])
    assert grafico.minimumHeight() >= 26 + 2 * GraficoBarras.ALTURA_LINHA
    grafico.resize(400, grafico.minimumHeight())
    imagem = grafico.grab().toImage()

    def comprimento(cor: str, y: int) -> int:
        return sum(imagem.pixelColor(x, y).name() == cor for x in range(imagem.width()))

    topo = grafico._topo_linhas
    meio = lambda linha: round(topo + GraficoBarras.ALTURA_LINHA * (linha + 0.5))  # noqa: E731
    maior, metade = comprimento("#ff0000", meio(0)), comprimento("#0000ff", meio(1))
    assert maior > 0 and abs(metade / maior - 0.5) < 0.05
    assert QColor("#ff0000").name() in _cores(grafico)
    assert grafico.indice_em(QPointF(10, meio(1))) == 1
