"""Gráficos da tela de Relatórios, desenhados com QPainter (sem bibliotecas extras).

Todos seguem as mesmas regras:
- barras finas (no máximo 24 px), com a ponta arredondada e a base reta;
- 2 px de espaço em branco entre as partes de uma coluna empilhada;
- grade e eixos em linhas finas e claras, sem tracejado;
- textos nas cores de texto, nunca na cor da série (a cor fica no quadradinho da legenda);
- legenda sempre que houver mais de uma série;
- passar o mouse mostra os números (e cada gráfico tem a tabela com os mesmos valores).

As cores dos tipos de item foram conferidas para daltonismo (protanopia,
deuteranopia e tritanopia) sobre o fundo branco: a menor diferença entre
duas delas é ΔE 9,2 (OKLab), acima do mínimo recomendado de 8.
"""

from dataclasses import dataclass
from math import ceil, floor, log10

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QToolTip, QWidget

from oficina.dinheiro import formatar_compacto
from oficina.modelos import TIPO_MAO_DE_OBRA, TIPO_PECA, TIPO_TERCEIROS
from oficina.ui import tema

COR_PECA = "#2A78D6"
COR_MAO_DE_OBRA = "#1BAF7A"
COR_TERCEIROS = "#EB6834"
CORES_TIPO = {TIPO_PECA: COR_PECA, TIPO_MAO_DE_OBRA: COR_MAO_DE_OBRA, TIPO_TERCEIROS: COR_TERCEIROS}
COR_NEUTRA = tema.AZUL_MEDIO  # contagens que não são de um tipo de item (ex.: OS por dia da semana)

SUPERFICIE = "#FFFFFF"
GRADE = "#E2E8F0"
EIXO = "#CBD5E1"
DESTAQUE = "#F1F5F9"  # faixa clara atrás do item sob o mouse

ESPESSURA_MAXIMA = 24
RAIO = 4
ESPACO = 2
TAMANHO_FONTE = 8.5


@dataclass(frozen=True)
class Serie:
    nome: str
    cor: str


@dataclass
class Barra:
    rotulo: str
    valor: int
    cor: str
    texto_valor: str
    dica: str = ""


def escala(maximo: int, divisoes: int = 4) -> tuple[int, int]:
    """Topo e passo "redondos" do eixo (1, 2, 2,5 ou 5 × 10ⁿ) para caber o valor máximo."""
    if maximo <= 0:
        return 100_000, 25_000
    bruto = maximo / divisoes
    potencia = 10 ** floor(log10(bruto))
    multiplos = (1, 2, 2.5, 5, 10) if potencia >= 1_000 else (1, 2, 5, 10)  # 2,5 só a partir de R$ 25
    passo = next(m * potencia for m in multiplos if m * potencia >= bruto)
    passo = max(100, round(passo))  # nunca menos de R$ 1 por divisão
    return ceil(maximo / passo) * passo, passo


def _caminho_barra(retangulo: QRectF, ponta: str) -> QPainterPath:
    """Retângulo com os cantos da ponta ("topo" ou "direita") arredondados e a base reta."""
    x0, y0, x1, y1 = retangulo.left(), retangulo.top(), retangulo.right(), retangulo.bottom()
    caminho = QPainterPath()
    if ponta == "topo":
        r = min(RAIO, retangulo.width() / 2, retangulo.height())
        caminho.moveTo(x0, y1)
        caminho.lineTo(x0, y0 + r)
        caminho.arcTo(QRectF(x0, y0, 2 * r, 2 * r), 180, -90)
        caminho.lineTo(x1 - r, y0)
        caminho.arcTo(QRectF(x1 - 2 * r, y0, 2 * r, 2 * r), 90, -90)
        caminho.lineTo(x1, y1)
    else:
        r = min(RAIO, retangulo.height() / 2, retangulo.width())
        caminho.moveTo(x0, y0)
        caminho.lineTo(x1 - r, y0)
        caminho.arcTo(QRectF(x1 - 2 * r, y0, 2 * r, 2 * r), 90, -90)
        caminho.lineTo(x1, y1 - r)
        caminho.arcTo(QRectF(x1 - 2 * r, y1 - 2 * r, 2 * r, 2 * r), 0, -90)
        caminho.lineTo(x0, y1)
    caminho.closeSubpath()
    return caminho


def _linha_fina(pintor: QPainter, cor: str, x1: float, y1: float, x2: float, y2: float) -> None:
    """Linha de 1 px alinhada à grade de pixels (fica nítida, sem borrar)."""
    pintor.setPen(QPen(QColor(cor), 1))
    if y1 == y2:
        y1 = y2 = floor(y1) + 0.5
    else:
        x1 = x2 = floor(x1) + 0.5
    pintor.drawLine(QPointF(x1, y1), QPointF(x2, y2))


class _Grafico(QWidget):
    """Base: fundo, legenda, mensagem de "sem dados" e dica ao passar o mouse."""

    def __init__(self, vazio: str = "Nenhuma OS finalizada no período."):
        super().__init__()
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._vazio = vazio
        self._dicas: list[str] = []
        self.destaque: int | None = None  # índice do item sob o mouse

    def fonte(self, negrito: bool = False) -> QFont:
        fonte = QFont(self.font())
        fonte.setPointSizeF(TAMANHO_FONTE)
        fonte.setBold(negrito)
        return fonte

    def sizeHint(self) -> QSize:  # noqa: N802 (nome do Qt)
        return QSize(400, self.minimumHeight())

    def indice_em(self, ponto: QPointF) -> int | None:
        raise NotImplementedError

    def mouseMoveEvent(self, evento) -> None:  # noqa: N802 (nome do Qt)
        indice = self.indice_em(evento.position())
        if indice != self.destaque:
            self.destaque = indice
            self.update()
        if indice is None or not self._dicas[indice]:
            QToolTip.hideText()
        else:
            QToolTip.showText(evento.globalPosition().toPoint(), self._dicas[indice], self)

    def leaveEvent(self, evento) -> None:  # noqa: N802 (nome do Qt)
        self.destaque = None
        QToolTip.hideText()
        self.update()
        super().leaveEvent(evento)

    def _iniciar_pintura(self) -> QPainter:
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        pintor.fillRect(self.rect(), QColor(SUPERFICIE))
        pintor.setFont(self.fonte())
        return pintor

    def _desenhar_vazio(self, pintor: QPainter) -> None:
        pintor.setPen(QColor(tema.TEXTO_SUAVE))
        pintor.drawText(QRectF(self.rect()), Qt.AlignmentFlag.AlignCenter, self._vazio)

    def _desenhar_legenda(self, pintor: QPainter, series: list[Serie], x: float, y: float) -> float:
        """Quadradinho na cor da série + nome em cor de texto. Devolve a altura ocupada."""
        metrica = QFontMetricsF(pintor.font())
        altura = metrica.height()
        for serie in series:
            pintor.setPen(Qt.PenStyle.NoPen)
            pintor.setBrush(QColor(serie.cor))
            pintor.drawRoundedRect(QRectF(x, y + (altura - 10) / 2, 10, 10), 2, 2)
            pintor.setPen(QColor(tema.TEXTO_SUAVE))
            pintor.drawText(QPointF(x + 15, y + metrica.ascent()), serie.nome)
            x += 15 + metrica.horizontalAdvance(serie.nome) + 18
        return altura


class GraficoColunas(_Grafico):
    """Colunas empilhadas ao longo do tempo (ex.: faturamento por mês, dividido por tipo)."""

    def __init__(self, vazio: str = "Nenhuma OS finalizada no período."):
        super().__init__(vazio)
        self.setMinimumHeight(260)
        self._rotulos: list[str] = []
        self._series: list[Serie] = []
        self._valores: list[list[int]] = []
        self._rotulos_topo: list[str] = []
        self._area = QRectF()
        self._banda = 0.0

    def definir(self, rotulos: list[str], series: list[Serie], valores: list[list[int]], dicas: list[str],
                rotulos_topo: list[str] | None = None) -> None:
        """valores[i][j] é o valor da série j na coluna i (em centavos)."""
        self._rotulos, self._series, self._valores, self._dicas = rotulos, series, valores, dicas
        self._rotulos_topo = rotulos_topo or []
        self.destaque = None
        self.update()

    def indice_em(self, ponto: QPointF) -> int | None:
        if not self._rotulos or self._banda <= 0:
            return None
        if not (self._area.left() <= ponto.x() < self._area.right()
                and self._area.top() - 20 <= ponto.y() <= self.height()):
            return None
        return min(len(self._rotulos) - 1, int((ponto.x() - self._area.left()) / self._banda))

    def paintEvent(self, _evento) -> None:  # noqa: N802 (nome do Qt)
        pintor = self._iniciar_pintura()
        totais = [sum(v) for v in self._valores]
        if not self._rotulos or not any(totais):
            self._desenhar_vazio(pintor)
            pintor.end()
            return
        metrica = QFontMetricsF(pintor.font())
        altura_texto = metrica.height()
        topo, passo = escala(max(totais))
        marcas = list(range(0, topo + 1, passo))
        largura_eixo = max(metrica.horizontalAdvance(formatar_compacto(v)) for v in marcas) + 10

        y = 2.0
        if len(self._series) > 1:
            y += self._desenhar_legenda(pintor, self._series, largura_eixo, y) + 10
        y += altura_texto + 4  # espaço para o total acima da coluna mais alta
        self._area = area = QRectF(largura_eixo, y, self.width() - largura_eixo - 6,
                                   self.height() - y - altura_texto - 10)
        n = len(self._rotulos)
        self._banda = banda = area.width() / n
        largura = min(ESPESSURA_MAXIMA, banda * 0.6)
        para_y = lambda valor: area.bottom() - valor / topo * area.height()  # noqa: E731

        if self.destaque is not None:
            pintor.fillRect(QRectF(area.left() + banda * self.destaque, area.top() - altura_texto - 4, banda,
                                   area.height() + altura_texto + 4), QColor(DESTAQUE))

        for valor in marcas:  # grade e números do eixo
            yv = para_y(valor)
            _linha_fina(pintor, EIXO if valor == 0 else GRADE, area.left(), yv, area.right(), yv)
            pintor.setPen(QColor(tema.TEXTO_SUAVE))
            pintor.drawText(QRectF(0, yv - altura_texto / 2, largura_eixo - 8, altura_texto),
                            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, formatar_compacto(valor))

        # Bordas em pixels inteiros: as partes ficam nítidas e o espaço entre elas, exato.
        pintor.setPen(Qt.PenStyle.NoPen)
        largura = round(largura)
        for i, valores in enumerate(self._valores):
            x = round(area.left() + banda * (i + 0.5) - largura / 2)
            acumulado = 0
            base = round(area.bottom())
            visiveis = [(j, v) for j, v in enumerate(valores) if v > 0]
            if visiveis:  # o fundo da coluna esconde a grade nos espaços entre as partes
                pintor.fillRect(QRectF(x, round(para_y(sum(valores))), largura, base - round(para_y(sum(valores)))),
                                QColor(DESTAQUE if i == self.destaque else SUPERFICIE))
            for k, (j, valor) in enumerate(visiveis):
                acumulado += valor
                topo_parte = round(para_y(acumulado))
                ultima = k == len(visiveis) - 1
                retangulo = QRectF(x, topo_parte, largura, base - topo_parte)
                if not ultima and retangulo.height() > ESPACO + 1:
                    retangulo.setTop(topo_parte + ESPACO)  # o espaço branco entre as partes
                pintor.setBrush(QColor(self._series[j].cor))
                if ultima:
                    pintor.drawPath(_caminho_barra(retangulo, "topo"))
                else:
                    pintor.drawRect(retangulo)
                base = topo_parte

        pintor.setPen(QColor(tema.TEXTO_SUAVE))
        if self._rotulos_topo and max(metrica.horizontalAdvance(t) for t in self._rotulos_topo) + 4 <= banda:
            for i, texto in enumerate(self._rotulos_topo):
                if totais[i]:
                    topo_coluna = para_y(totais[i])
                    pintor.drawText(QRectF(area.left() + banda * i, topo_coluna - altura_texto - 3, banda,
                                           altura_texto), Qt.AlignmentFlag.AlignCenter, texto)

        # Rótulos do eixo X: se não couberem todos, mostra um a cada N, sempre incluindo o último período.
        largura_rotulo = max(metrica.horizontalAdvance(r) for r in self._rotulos) + 8
        a_cada = max(1, ceil(largura_rotulo / banda))
        for i, rotulo in enumerate(self._rotulos):
            if (n - 1 - i) % a_cada == 0:
                pintor.drawText(QRectF(area.left() + banda * (i + 0.5) - largura_rotulo / 2, area.bottom() + 5,
                                       largura_rotulo, altura_texto), Qt.AlignmentFlag.AlignCenter, rotulo)
        pintor.end()


class GraficoBarras(_Grafico):
    """Barras horizontais com o nome à esquerda e o valor na ponta (ex.: ranking de itens)."""

    ALTURA_LINHA = 28
    ESPESSURA = 14

    def __init__(self, vazio: str = "Nenhuma OS finalizada no período."):
        super().__init__(vazio)
        self._barras: list[Barra] = []
        self._legenda: list[Serie] = []
        self._topo_linhas = 0.0
        self.setMinimumHeight(120)

    def definir(self, barras: list[Barra], legenda: list[Serie] | None = None) -> None:
        self._barras, self._legenda = barras, legenda or []
        self._dicas = [b.dica for b in barras]
        self.destaque = None
        altura_legenda = 26 if self._legenda else 0
        self.setMinimumHeight(max(120, altura_legenda + len(barras) * self.ALTURA_LINHA + 8))
        self.update()

    def indice_em(self, ponto: QPointF) -> int | None:
        if not self._barras or ponto.y() < self._topo_linhas:
            return None
        indice = int((ponto.y() - self._topo_linhas) / self.ALTURA_LINHA)
        return indice if indice < len(self._barras) else None

    def paintEvent(self, _evento) -> None:  # noqa: N802 (nome do Qt)
        pintor = self._iniciar_pintura()
        if not self._barras or not any(b.valor for b in self._barras):
            self._desenhar_vazio(pintor)
            pintor.end()
            return
        metrica = QFontMetricsF(pintor.font())
        largura_rotulo = min(max(metrica.horizontalAdvance(b.rotulo) for b in self._barras), self.width() * 0.42)
        largura_valor = max(metrica.horizontalAdvance(b.texto_valor) for b in self._barras) + 8
        x0 = largura_rotulo + 10
        largura_util = max(10.0, self.width() - x0 - largura_valor - 4)
        maximo = max(b.valor for b in self._barras)

        y = 2.0
        if self._legenda:
            y += self._desenhar_legenda(pintor, self._legenda, x0, y) + 10
        self._topo_linhas = y
        fim = y + len(self._barras) * self.ALTURA_LINHA

        for i, barra in enumerate(self._barras):
            topo_linha = y + i * self.ALTURA_LINHA
            centro = topo_linha + self.ALTURA_LINHA / 2
            if i == self.destaque:
                pintor.fillRect(QRectF(0, topo_linha, self.width(), self.ALTURA_LINHA), QColor(DESTAQUE))
            pintor.setPen(QColor(tema.TEXTO))
            pintor.drawText(QRectF(0, topo_linha, largura_rotulo, self.ALTURA_LINHA),
                            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                            metrica.elidedText(barra.rotulo, Qt.TextElideMode.ElideRight, largura_rotulo))
            comprimento = max(2.0, barra.valor / maximo * largura_util) if barra.valor > 0 else 0
            if comprimento:
                pintor.setPen(Qt.PenStyle.NoPen)
                pintor.setBrush(QColor(barra.cor))
                pintor.drawPath(_caminho_barra(
                    QRectF(x0, centro - self.ESPESSURA / 2, comprimento, self.ESPESSURA), "direita"))
            pintor.setPen(QColor(tema.TEXTO_SUAVE))
            pintor.drawText(QRectF(x0 + comprimento + 6, topo_linha, largura_valor, self.ALTURA_LINHA),
                            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, barra.texto_valor)
        _linha_fina(pintor, EIXO, x0, y + 4, x0, fim - 4)
        pintor.end()
