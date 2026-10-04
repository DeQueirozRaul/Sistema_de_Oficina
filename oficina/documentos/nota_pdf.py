"""Nota da OS e do orçamento em PDF, desenhada com o Qt (sem Excel).

A primeira versão do sistema montava uma planilha no Excel e pedia ao próprio
Excel (via pywin32) para exportar o PDF. Funcionava, mas só no Windows, só com
o Excel instalado e levava alguns segundos por nota. Aqui o mesmo layout é
desenhado direto com QPainter/QPdfWriter, que já vêm no PySide6:

- a grade tem as 6 colunas da planilha original, com as mesmas proporções;
- as linhas têm as mesmas alturas (em pontos), cores, bordas e fontes;
- descrições longas quebram em mais de uma linha (na planilha eram cortadas);
- notas com muitos itens continuam na página seguinte.

O código é dividido em duas partes: `montar_os`/`montar_orcamento` criam o
*modelo* da nota (linhas e células, fácil de testar) e `desenhar` pinta esse
modelo em qualquer QPaintDevice (PDF ou imagem de prévia).
"""

from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path

from PySide6.QtCore import QMarginsF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QPageLayout, QPageSize, QPainter, QPdfWriter, QPen

from oficina.dinheiro import formatar_quantidade, formatar_reais
from oficina.modelos import Item, Orcamento, OrdemServico

# Cores da nota (as mesmas da planilha original)
AZUL_ESCURO = "#1A365C"
AZUL_CLARO = "#F1F5F9"
LINHAS_SUAVES = "#CBD5E1"
BRANCO = "#FFFFFF"
PRETO = "#000000"

FONTES = ["Segoe UI", "Noto Sans", "DejaVu Sans", "Arial", "Helvetica"]

# Larguras das colunas A–F da planilha original (em "caracteres" do Excel): só a proporção importa.
LARGURAS_COLUNAS = (15, 18, 13, 15, 15, 15)

# Página A4 em pontos (1 pt = 1/72 polegada)
LARGURA_PAGINA, ALTURA_PAGINA = 595.28, 841.89
LARGURA_NOTA = 540.0
MARGEM_VERTICAL = 36.0  # 0,5 polegada, como na planilha
ALTURA_LINHA = 24.0
RESPIRO_TEXTO = 3.0  # espaço entre a borda da célula e o texto

ESQUERDA = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
CENTRO = Qt.AlignmentFlag.AlignCenter
DIREITA = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter


@dataclass(frozen=True)
class Estilo:
    fundo: str | None = BRANCO
    cor: str = PRETO
    negrito: bool = False
    tamanho: float = 10
    alinhamento: Qt.AlignmentFlag = ESQUERDA
    borda: bool = True
    quebra: bool = False  # quebra o texto em várias linhas (a linha cresce se precisar)


VALOR = Estilo()
VALOR_CENTRO = replace(VALOR, alinhamento=CENTRO)
VALOR_DIREITA = replace(VALOR, alinhamento=DIREITA)
DESCRICAO = replace(VALOR, quebra=True)
ROTULO = Estilo(fundo=AZUL_CLARO, cor=AZUL_ESCURO, negrito=True)
ROTULO_CENTRO = replace(ROTULO, alinhamento=CENTRO)
ROTULO_DIREITA = replace(ROTULO, alinhamento=DIREITA)
TOTAL = Estilo(fundo=AZUL_ESCURO, cor=BRANCO, negrito=True, alinhamento=DIREITA)
OBSERVACAO = Estilo(quebra=True, alinhamento=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
ASSINATURA = Estilo(fundo=None, cor=AZUL_ESCURO, negrito=True, alinhamento=CENTRO, borda=False)


@dataclass
class Celula:
    coluna: int  # 0 a 5 (A a F)
    texto: str
    estilo: Estilo = VALOR
    colunas: int = 1  # quantas colunas a célula ocupa (células mescladas)


@dataclass
class Linha:
    altura: float = ALTURA_LINHA
    celulas: list[Celula] = field(default_factory=list)
    grupo: int | None = None  # linhas do mesmo grupo não são separadas por quebra de página

    def texto(self) -> list[str]:
        return [c.texto for c in self.celulas]


@dataclass
class Cabecalho:
    titulo: str
    linhas: list[str] = field(default_factory=list)  # endereço; telefone e CNPJ
    logo: QImage | None = None


@dataclass
class Nota:
    cabecalho: Cabecalho
    linhas: list[Linha] = field(default_factory=list)
    titulo_documento: str = ""

    def espaco(self, altura: float) -> None:
        self.linhas.append(Linha(altura=altura))

    def linha(self, *celulas: Celula, altura: float = ALTURA_LINHA, grupo: int | None = None) -> None:
        self.linhas.append(Linha(altura=altura, celulas=list(celulas), grupo=grupo))


# ================================================================ montagem do conteúdo

def _linhas_cabecalho(oficina: dict) -> list[str]:
    """Endereço numa linha; telefone e CNPJ (se a oficina escolheu mostrar) na linha de baixo."""
    linhas = [f"Endereço: {oficina['endereco']}"] if oficina.get("endereco") else []
    contato = [f"Tel.: {oficina['telefone']}"] if oficina.get("telefone") else []
    contato += [f"CNPJ: {oficina['cnpj']}"] if oficina.get("cnpj") else []
    if contato:
        linhas.append("   •   ".join(contato))
    return linhas


def _itens_e_totais(nota: Nota, itens: list[Item], desconto: int, observacoes: str, titulo_obs: str) -> None:
    nota.linha(Celula(0, "Descrição de Peças e Serviços", ROTULO_CENTRO, 3), Celula(3, "Qtd", ROTULO_CENTRO),
               Celula(4, "Vlr. Unit", ROTULO_CENTRO), Celula(5, "Total", ROTULO_CENTRO))
    for item in itens:
        nota.linha(Celula(0, item.descricao, DESCRICAO, 3), Celula(3, formatar_quantidade(item.quantidade), VALOR_CENTRO),
                   Celula(4, formatar_reais(item.valor_unitario), VALOR_DIREITA),
                   Celula(5, formatar_reais(item.total), VALOR_DIREITA))
    subtotal = sum(item.total for item in itens)
    nota.espaco(10)
    nota.linha(Celula(4, "Subtotal:", ROTULO_DIREITA), Celula(5, formatar_reais(subtotal), VALOR_DIREITA), grupo=1)
    nota.linha(Celula(4, "Desconto:", ROTULO_DIREITA), Celula(5, formatar_reais(desconto), VALOR_DIREITA), grupo=1)
    nota.linha(Celula(4, "TOTAL GERAL:", TOTAL), Celula(5, formatar_reais(subtotal - desconto), TOTAL), grupo=1)
    nota.espaco(ALTURA_LINHA)
    nota.linha(Celula(0, titulo_obs, ROTULO, 6), grupo=2)
    nota.linha(Celula(0, observacoes, OBSERVACAO, 6), altura=2 * ALTURA_LINHA, grupo=2)


def _data(dia: date) -> str:
    return dia.strftime("%d/%m/%Y")


def montar_os(os_: OrdemServico, oficina: dict, logo: QImage | None = None) -> Nota:
    nota = Nota(Cabecalho(f"ORDEM DE SERVIÇO - {oficina.get('nome', '')}".rstrip(" -"), _linhas_cabecalho(oficina), logo),
                titulo_documento=f"OS {os_.numero}")
    nota.linha(Celula(0, "OS Nº:", ROTULO), Celula(1, str(os_.numero), VALOR, 3),
               Celula(4, "Data:", ROTULO), Celula(5, _data(os_.data)))
    nota.linha(Celula(0, "Mecânico:", ROTULO), Celula(1, os_.mecanico_nome, VALOR, 5))
    nota.espaco(10)
    nota.linha(Celula(0, "DADOS DO CLIENTE", ROTULO_CENTRO, 3), Celula(3, "DADOS DO VEÍCULO", ROTULO_CENTRO, 3))
    ano_km = " / ".join(p for p in (os_.ano, os_.km) if p)
    for rotulo_cliente, valor_cliente, rotulo_veiculo, valor_veiculo in (
            ("Nome:", os_.cliente_nome, "Modelo:", os_.modelo),
            ("CPF/CNPJ:", os_.cliente_documento, "Placa:", os_.placa),
            ("Telefone:", os_.cliente_telefone, "Ano / KM:", ano_km)):
        nota.linha(Celula(0, rotulo_cliente, ROTULO), Celula(1, valor_cliente, VALOR, 2),
                   Celula(3, rotulo_veiculo, ROTULO), Celula(4, valor_veiculo, VALOR, 2))
    nota.espaco(10)
    _itens_e_totais(nota, os_.itens, os_.desconto, os_.observacoes, "Observações:")
    nota.espaco(ALTURA_LINHA)
    nota.espaco(ALTURA_LINHA)
    linha_assinatura = "_" * 48
    nota.linha(Celula(0, linha_assinatura, ASSINATURA, 3), Celula(3, linha_assinatura, ASSINATURA, 3), grupo=3)
    nota.linha(Celula(0, "Assinatura do Técnico", ASSINATURA, 3), Celula(3, "Assinatura do Cliente", ASSINATURA, 3),
               grupo=3)
    return nota


def montar_orcamento(orcamento: Orcamento, oficina: dict, logo: QImage | None = None) -> Nota:
    nota = Nota(Cabecalho(f"ORÇAMENTO - {oficina.get('nome', '')}".rstrip(" -"), _linhas_cabecalho(oficina), logo),
                titulo_documento=f"Orçamento {orcamento.numero}")
    nota.linha(Celula(0, "Orçamento Nº:", ROTULO), Celula(1, str(orcamento.numero), VALOR, 3),
               Celula(4, "Data:", ROTULO), Celula(5, _data(orcamento.data)))
    nota.espaco(10)
    nota.linha(Celula(0, "DADOS DO VEÍCULO", ROTULO_CENTRO, 6))
    nota.linha(Celula(0, "Modelo:", ROTULO), Celula(1, orcamento.modelo, VALOR, 2),
               Celula(3, "Placa:", ROTULO), Celula(4, orcamento.placa, VALOR, 2))
    nota.espaco(10)
    _itens_e_totais(nota, orcamento.itens, orcamento.desconto, orcamento.observacoes, "Observações / Validade:")
    return nota


# ================================================================ desenho

class _Pintor:
    """Converte pontos (pt) para as unidades do dispositivo e desenha as partes da nota."""

    def __init__(self, pintor: QPainter, dispositivo):
        self.p = pintor
        self.dispositivo = dispositivo
        self.escala = dispositivo.logicalDpiX() / 72.0
        total = sum(LARGURAS_COLUNAS)
        self.x0 = (LARGURA_PAGINA - LARGURA_NOTA) / 2
        self.bordas_colunas = [self.x0]
        for largura in LARGURAS_COLUNAS:
            self.bordas_colunas.append(self.bordas_colunas[-1] + LARGURA_NOTA * largura / total)

    def retangulo(self, x: float, y: float, largura: float, altura: float) -> QRectF:
        e = self.escala
        return QRectF(x * e, y * e, largura * e, altura * e)

    def fonte(self, estilo: Estilo) -> QFont:
        fonte = QFont()
        fonte.setFamilies(FONTES)
        fonte.setPointSizeF(estilo.tamanho)
        fonte.setBold(estilo.negrito)
        return fonte

    def area_celula(self, celula: Celula) -> tuple[float, float]:
        inicio = self.bordas_colunas[celula.coluna]
        return inicio, self.bordas_colunas[celula.coluna + celula.colunas] - inicio

    def altura_necessaria(self, linha: Linha) -> float:
        """Altura da linha, aumentada se algum texto com quebra não couber."""
        altura = linha.altura
        for celula in linha.celulas:
            if not celula.estilo.quebra or not celula.texto:
                continue
            _, largura = self.area_celula(celula)
            metrica = QFontMetricsF(self.fonte(celula.estilo), self.dispositivo)
            caixa = metrica.boundingRect(self.retangulo(0, 0, largura - 2 * RESPIRO_TEXTO, 10_000),
                                         int(Qt.TextFlag.TextWordWrap), celula.texto)
            altura = max(altura, caixa.height() / self.escala + 2 * RESPIRO_TEXTO + 2)
        return altura

    def celula(self, celula: Celula, y: float, altura: float) -> None:
        x, largura = self.area_celula(celula)
        estilo = celula.estilo
        area = self.retangulo(x, y, largura, altura)
        if estilo.fundo:
            self.p.fillRect(area, QColor(estilo.fundo))
        if estilo.borda:
            self.p.setPen(QPen(QColor(LINHAS_SUAVES), 0.75 * self.escala))
            self.p.drawRect(area)
        if not celula.texto:
            return
        self.p.setPen(QColor(estilo.cor))
        fonte = self.fonte(estilo)
        self.p.setFont(fonte)
        texto_area = self.retangulo(x + RESPIRO_TEXTO, y + RESPIRO_TEXTO, largura - 2 * RESPIRO_TEXTO,
                                    altura - 2 * RESPIRO_TEXTO)
        if estilo.quebra:
            self.p.drawText(texto_area, int(estilo.alinhamento) | int(Qt.TextFlag.TextWordWrap), celula.texto)
            return
        # Como o "reduzir para caber" do Excel: diminui a fonte até 7 pt e só então corta com "…"
        metrica = QFontMetricsF(fonte, self.dispositivo)
        while metrica.horizontalAdvance(celula.texto) > texto_area.width() and fonte.pointSizeF() > 7:
            fonte.setPointSizeF(fonte.pointSizeF() - 0.5)
            metrica = QFontMetricsF(fonte, self.dispositivo)
        self.p.setFont(fonte)
        texto = metrica.elidedText(celula.texto, Qt.TextElideMode.ElideRight, texto_area.width())
        self.p.drawText(texto_area, int(estilo.alinhamento), texto)

    def cabecalho(self, cabecalho: Cabecalho, y: float) -> float:
        """Título, endereço e a faixa azul. Devolve o y logo abaixo do cabeçalho."""
        largura_titulo, x_titulo = LARGURA_NOTA, self.x0
        if cabecalho.logo is not None and not cabecalho.logo.isNull():
            altura_logo = 52.0
            proporcao = cabecalho.logo.width() / max(1, cabecalho.logo.height())
            largura_logo = min(90.0, altura_logo * proporcao)
            self.p.drawImage(self.retangulo(self.x0, y + 2, largura_logo, largura_logo / proporcao), cabecalho.logo)
            x_titulo += largura_logo + 8
            largura_titulo -= 2 * (largura_logo + 8)  # mantém o título centralizado na página
        titulo = Estilo(fundo=None, cor=AZUL_ESCURO, negrito=True, tamanho=16, borda=False)
        self.p.setFont(self.fonte(titulo))
        self.p.setPen(QColor(AZUL_ESCURO))
        self.p.drawText(self.retangulo(x_titulo, y, largura_titulo, 36),
                        int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom), cabecalho.titulo)
        fonte_info = self.fonte(Estilo())
        self.p.setFont(fonte_info)
        self.p.setPen(QColor(PRETO))
        metrica = QFontMetricsF(fonte_info, self.dispositivo)
        y_info = y + 36
        for linha in cabecalho.linhas or [""]:
            area = self.retangulo(x_titulo, y_info, largura_titulo, 16)
            texto = metrica.elidedText(linha, Qt.TextElideMode.ElideRight, area.width())
            self.p.drawText(area, int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop), texto)
            y_info += 16
        y_faixa = max(y_info + 4, y + 56)  # com uma linha, fica igual à planilha original (faixa em 56 pt)
        self.p.fillRect(self.retangulo(self.x0, y_faixa, LARGURA_NOTA, 3), QColor(AZUL_ESCURO))
        return y_faixa + 3 + 16


def _blocos(linhas: list[Linha]) -> list[list[Linha]]:
    """Agrupa as linhas que precisam ficar juntas na mesma página."""
    blocos: list[list[Linha]] = []
    for linha in linhas:
        if linha.grupo is not None and blocos and blocos[-1][0].grupo == linha.grupo:
            blocos[-1].append(linha)
        else:
            blocos.append([linha])
    return blocos


def desenhar(nota: Nota, dispositivo, nova_pagina=None) -> int:
    """Desenha a nota no dispositivo. `nova_pagina()` é chamada quando o conteúdo não cabe
    numa página (no PDF, cria a página seguinte). Devolve o número de páginas."""
    pintor = QPainter(dispositivo)
    if not pintor.isActive():
        raise OSError("não foi possível iniciar o desenho")
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
    pintor.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    p = _Pintor(pintor, dispositivo)
    paginas = 1
    y = p.cabecalho(nota.cabecalho, MARGEM_VERTICAL)
    limite = ALTURA_PAGINA - MARGEM_VERTICAL
    for bloco in _blocos(nota.linhas):
        alturas = [p.altura_necessaria(linha) for linha in bloco]
        if y + sum(alturas) > limite and y > MARGEM_VERTICAL + 1 and nova_pagina is not None:
            nova_pagina()
            paginas += 1
            y = MARGEM_VERTICAL
            if not bloco[0].celulas:  # não começa a página nova com um espaço em branco
                continue
        for linha, altura in zip(bloco, alturas):
            for celula in linha.celulas:
                p.celula(celula, y, altura)
            y += altura
    pintor.end()
    return paginas


def salvar_pdf(nota: Nota, caminho: Path) -> int:
    """Grava a nota em PDF (A4). Devolve o número de páginas."""
    escritor = QPdfWriter(str(caminho))
    escritor.setPageLayout(QPageLayout(QPageSize(QPageSize.PageSizeId.A4), QPageLayout.Orientation.Portrait,
                                       QMarginsF(0, 0, 0, 0)))
    escritor.setResolution(300)
    escritor.setTitle(nota.titulo_documento)
    escritor.setCreator("Sistema de Oficina")
    return desenhar(nota, escritor, escritor.newPage)


def imagem_previa(nota: Nota, dpi: int = 96) -> QImage:
    """Primeira página da nota como imagem (para conferência e testes)."""
    pontos_por_metro = round(dpi / 0.0254)
    imagem = QImage(round(LARGURA_PAGINA * dpi / 72), round(ALTURA_PAGINA * dpi / 72), QImage.Format.Format_RGB32)
    imagem.setDotsPerMeterX(pontos_por_metro)
    imagem.setDotsPerMeterY(pontos_por_metro)
    imagem.fill(QColor(BRANCO))
    desenhar(nota, imagem)
    return imagem
