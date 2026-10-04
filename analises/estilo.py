"""Estilo e formatação do notebook de análise.

Usa as mesmas cores e regras da tela de Relatórios do sistema: barras finas,
grade clara só no eixo dos valores, sem bordas desnecessárias, textos em
cinza-escuro (nunca na cor da série) e números no formato brasileiro.
"""

import matplotlib as mpl
import pandas as pd
from matplotlib.ticker import FuncFormatter

MAO_DE_OBRA = "#1BAF7A"
PECAS = "#2A78D6"
TERCEIROS = "#EB6834"
NEUTRA = "#2B5088"  # séries que não são de um tipo de item
APAGADA = "#CBD5E1"  # o que é contexto, para destacar o resto
TEXTO = "#1E293B"
TEXTO_SUAVE = "#64748B"
GRADE = "#E2E8F0"

CORES_TIPO = {"Mão de obra": MAO_DE_OBRA, "Peças": PECAS, "Terceirizados": TERCEIROS}


def aplicar() -> None:
    mpl.rcParams.update({
        "figure.figsize": (10, 4),
        "figure.dpi": 100,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.spines.left": False,
        "axes.edgecolor": APAGADA,
        "axes.linewidth": 1,
        "axes.grid": True,
        "axes.grid.axis": "y",
        "axes.axisbelow": True,
        "grid.color": GRADE,
        "grid.linewidth": 1,
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.titlecolor": TEXTO,
        "axes.titlepad": 22,
        "axes.labelcolor": TEXTO_SUAVE,
        "xtick.color": TEXTO_SUAVE,
        "ytick.color": TEXTO_SUAVE,
        "xtick.major.size": 0,
        "ytick.major.size": 0,
        "text.color": TEXTO,
        "font.size": 9.5,
        "legend.frameon": False,
        "legend.fontsize": 9,
        "lines.linewidth": 2,
        "lines.solid_capstyle": "round",
        "lines.solid_joinstyle": "round",
    })


def subtitulo(ax, texto: str) -> None:
    """Linha explicativa logo abaixo do título do gráfico."""
    ax.text(0, 1.02, texto, transform=ax.transAxes, color=TEXTO_SUAVE, fontsize=9, va="bottom")


# ---------------------------------------------------------------- números no formato brasileiro

def _br(numero: str) -> str:
    return numero.replace(",", "X").replace(".", ",").replace("X", ".")


def reais(valor: float, casas: int = 2) -> str:
    """1234.5 -> 'R$ 1.234,50'."""
    return f"R$ {_br(f'{valor:,.{casas}f}')}"


def compacto(valor: float) -> str:
    """Para eixos e rótulos: 34900 -> '34,9 mil'."""
    if abs(valor) >= 1_000_000:
        return _br(f"{valor / 1_000_000:.1f}").removesuffix(",0") + " mi"
    if abs(valor) >= 1_000:
        return _br(f"{valor / 1_000:.1f}").removesuffix(",0") + " mil"
    return _br(f"{valor:.0f}")


def pct(fracao: float, casas: int = 0) -> str:
    """0.256 -> '26%'."""
    return _br(f"{fracao * 100:.{casas}f}") + "%"


EIXO_REAIS = FuncFormatter(lambda valor, _: compacto(valor))
EIXO_PCT = FuncFormatter(lambda valor, _: _br(f"{valor * 100:.1f}").removesuffix(",0") + "%")


def tabela(df: pd.DataFrame, reais_: list[str] = (), pct_: list[str] = (), inteiros: list[str] = ()) -> pd.DataFrame:
    """Cópia da tabela com os números já formatados, para exibir."""
    saida = df.copy()
    for coluna in reais_:
        saida[coluna] = saida[coluna].map(reais)
    for coluna in pct_:
        saida[coluna] = saida[coluna].map(lambda v: pct(v, 1))
    for coluna in inteiros:
        saida[coluna] = saida[coluna].map(lambda v: _br(f"{v:,.0f}"))
    return saida
