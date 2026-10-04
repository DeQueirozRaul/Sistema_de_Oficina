"""Gera a logo genérica (SVG) e o ícone do executável (.ico).

Uso (só é preciso rodar de novo se o desenho mudar):
    pip install pillow
    python ferramentas/gerar_icones.py

Saída:
    oficina/ui/recursos/logo_padrao.svg  (engrenagem com chave de boca)
    oficina/ui/recursos/icone.ico        (ícone do .exe, em vários tamanhos)
"""

import io
import math
import os
from pathlib import Path

RECURSOS = Path(__file__).resolve().parent.parent / "oficina" / "ui" / "recursos"
AZUL, LARANJA, BRANCO = "#1A365C", "#F59E0B", "#FFFFFF"


def desenho_engrenagem(dentes: int = 12, raio_externo: float = 78, raio_interno: float = 63,
                       raio_furo: float = 24, centro: float = 100) -> str:
    """Caminho SVG de uma engrenagem com dentes em trapézio simétrico e furo central."""
    passo = 2 * math.pi / dentes
    pontos = []
    for i in range(dentes):
        inicio = passo * i - math.pi / 2
        for fracao, raio in ((0.00, raio_interno), (0.10, raio_externo), (0.40, raio_externo), (0.50, raio_interno)):
            angulo = inicio + fracao * passo
            pontos.append((centro + raio * math.cos(angulo), centro + raio * math.sin(angulo)))
    contorno = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pontos) + " Z"
    r, c = raio_furo, centro
    furo = f"M{c + r},{c} A{r},{r} 0 1,0 {c - r},{c} A{r},{r} 0 1,0 {c + r},{c} Z"
    return f"{contorno} {furo}"


def svg_logo() -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
  <!-- Logo genérica do Sistema de Oficina: engrenagem com chave de boca.
       Gerada por ferramentas/gerar_icones.py. -->
  <circle cx="100" cy="100" r="98" fill="{BRANCO}"/>
  <path d="{desenho_engrenagem()}" fill="{AZUL}" fill-rule="evenodd"/>
  <g transform="rotate(-45 100 100)">
    <rect x="91" y="64" width="18" height="92" rx="9" fill="{LARANJA}" stroke="{BRANCO}" stroke-width="5"/>
    <circle cx="100" cy="54" r="24" fill="{LARANJA}" stroke="{BRANCO}" stroke-width="5"/>
    <rect x="92" y="26" width="16" height="30" rx="3" fill="{BRANCO}"/>
  </g>
</svg>
'''


def gerar_ico(svg: Path, destino: Path) -> None:
    """Renderiza o SVG com o Qt e salva um .ico com vários tamanhos (Pillow)."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PIL import Image
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
    from PySide6.QtGui import QGuiApplication, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    aplicacao = QGuiApplication.instance() or QGuiApplication([])  # o Qt exige uma aplicação ativa
    imagem = QImage(256, 256, QImage.Format.Format_ARGB32)
    imagem.fill(Qt.GlobalColor.transparent)
    pintor = QPainter(imagem)
    QSvgRenderer(QByteArray(svg.read_bytes())).render(pintor)
    pintor.end()
    dados = QByteArray()
    buffer = QBuffer(dados)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    imagem.save(buffer, "PNG")
    Image.open(io.BytesIO(bytes(dados))).save(destino, sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                                                               (64, 64), (128, 128), (256, 256)])
    del aplicacao


def main() -> None:
    svg = RECURSOS / "logo_padrao.svg"
    svg.write_text(svg_logo(), encoding="utf-8")
    gerar_ico(svg, RECURSOS / "icone.ico")
    print(f"Gerados: {svg} e {RECURSOS / 'icone.ico'}")


if __name__ == "__main__":
    main()
