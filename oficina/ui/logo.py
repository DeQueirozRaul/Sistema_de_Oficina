"""Logo da oficina: a imagem escolhida em Configurações ou a logo genérica do sistema.

A imagem escolhida é copiada (convertida para PNG) para a pasta de dados, para
o sistema não depender do arquivo original continuar no mesmo lugar.
"""

from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from oficina import caminhos
from oficina.modelos import ErroValidacao
from oficina.servicos import configuracoes as cfg

PASTA_RECURSOS = Path(__file__).resolve().parent / "recursos"
LOGO_PADRAO = PASTA_RECURSOS / "logo_padrao.svg"
NOME_ARQUIVO_LOGO = "logo_oficina.png"
TAMANHO_MAXIMO = 600  # px; logos maiores são reduzidas ao salvar
FORMATOS = "Imagens (*.png *.jpg *.jpeg *.bmp *.webp *.svg)"


def renderizar_svg(caminho: Path, tamanho: int) -> QImage:
    imagem = QImage(tamanho, tamanho, QImage.Format.Format_ARGB32_Premultiplied)
    imagem.fill(Qt.GlobalColor.transparent)
    pintor = QPainter(imagem)
    QSvgRenderer(QByteArray(Path(caminho).read_bytes())).render(pintor)
    pintor.end()
    return imagem


def _abrir_imagem(caminho: Path, tamanho_svg: int = TAMANHO_MAXIMO) -> QImage:
    if Path(caminho).suffix.lower() == ".svg":
        return renderizar_svg(caminho, tamanho_svg)
    return QImage(str(caminho))


def caminho_logo_personalizada(conn) -> Path | None:
    nome = cfg.obter(conn, cfg.LOGO_ARQUIVO)
    if not nome:
        return None
    caminho = caminhos.pasta_dados() / nome
    return caminho if caminho.exists() else None


def imagem_logo(conn, tamanho: int = 512) -> QImage:
    """Logo atual como imagem (usada também no cabeçalho da nota em PDF)."""
    personalizada = caminho_logo_personalizada(conn)
    if personalizada is not None:
        imagem = QImage(str(personalizada))
        if not imagem.isNull():
            return imagem
    return renderizar_svg(LOGO_PADRAO, tamanho)


def pixmap_logo(conn, largura: int, altura: int | None = None) -> QPixmap:
    """Logo atual pronta para a tela, nítida também com zoom do Windows (125%, 150%...)."""
    altura = altura or largura
    tela = QGuiApplication.primaryScreen()
    escala = tela.devicePixelRatio() if tela else 1.0
    imagem = imagem_logo(conn, round(max(largura, altura) * escala)).scaled(
        round(largura * escala), round(altura * escala),
        Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    pixmap = QPixmap.fromImage(imagem)
    pixmap.setDevicePixelRatio(escala)
    return pixmap


def salvar_logo(conn, origem: str | Path) -> Path:
    """Copia a imagem escolhida para a pasta de dados e passa a usá-la como logo."""
    imagem = _abrir_imagem(Path(origem))
    if imagem.isNull():
        raise ErroValidacao("Não foi possível abrir essa imagem. Use um arquivo PNG ou JPG.")
    if max(imagem.width(), imagem.height()) > TAMANHO_MAXIMO:
        imagem = imagem.scaled(TAMANHO_MAXIMO, TAMANHO_MAXIMO, Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
    destino = caminhos.pasta_dados() / NOME_ARQUIVO_LOGO
    if not imagem.save(str(destino), "PNG"):
        raise ErroValidacao(f"Não foi possível salvar a logo em {destino}.")
    cfg.salvar(conn, {cfg.LOGO_ARQUIVO: NOME_ARQUIVO_LOGO})
    return destino


def usar_logo_padrao(conn) -> None:
    cfg.salvar(conn, {cfg.LOGO_ARQUIVO: ""})
    arquivo = caminhos.pasta_dados() / NOME_ARQUIVO_LOGO
    try:
        arquivo.unlink()
    except OSError:
        pass
