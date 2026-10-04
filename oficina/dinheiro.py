"""Conversão e cálculo de valores em dinheiro.

Todo valor monetário do sistema é guardado em CENTAVOS (int), nunca em float.
Ex.: R$ 150,50 -> 15050. Assim somas de comissão e totais não acumulam erro de
arredondamento (0.1 + 0.2 != 0.3 no float).
"""

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

_SOMENTE_NUMEROS_E_SEPARADORES = re.compile(r"^[0-9.,]+$")


def texto_para_centavos(texto: str) -> int:
    """Converte o valor digitado pelo usuário em centavos.

    Aceita "150", "150,5", "150,50", "1.234,56", "1234.56" e "R$ 1.234,56".
    Levanta ValueError se o texto não for um valor válido.
    """
    t = (texto or "").replace("R$", "").replace(" ", "").strip()
    if not t or not _SOMENTE_NUMEROS_E_SEPARADORES.match(t):
        raise ValueError(f"Valor inválido: {texto!r}")

    if "," in t:
        # Padrão brasileiro: vírgula é o decimal e pontos são milhar.
        t = t.replace(".", "").replace(",", ".")
    elif t.count(".") == 1 and len(t.split(".")[1]) <= 2:
        pass  # "150.50": ponto usado como decimal
    else:
        t = t.replace(".", "")  # "1.234" ou "1.234.567": pontos de milhar

    try:
        valor = Decimal(t)
    except InvalidOperation:
        raise ValueError(f"Valor inválido: {texto!r}") from None
    return int((valor * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def formatar_reais(centavos: int, simbolo: bool = True) -> str:
    """15050 -> 'R$ 150,50' (ou '150,50' sem símbolo)."""
    sinal = "-" if centavos < 0 else ""
    reais, resto = divmod(abs(int(centavos)), 100)
    texto = f"{reais:,}".replace(",", ".") + f",{resto:02d}"
    return f"{sinal}R$ {texto}" if simbolo else f"{sinal}{texto}"


def formatar_compacto(centavos: int) -> str:
    """Valor curto para eixos e rótulos de gráfico, em reais.

    85000 -> '850', 4823050 -> '48,2 mil', 123456789 -> '1,23 mi'.
    """
    sinal = "-" if centavos < 0 else ""
    reais = abs(int(centavos)) / 100
    mil = round(reais / 1_000, 1)
    if mil >= 1_000:
        texto = f"{reais / 1_000_000:.2f}".rstrip("0").rstrip(".") + " mi"
    elif reais >= 1_000:
        texto = f"{mil:.1f}".rstrip("0").rstrip(".") + " mil"
    else:
        texto = f"{round(reais)}"
    return sinal + texto.replace(".", ",")


def texto_para_quantidade(texto: str) -> float:
    """'2' -> 2.0, '1,5' -> 1.5. Levanta ValueError se inválido ou <= 0."""
    t = (texto or "").strip().replace(",", ".")
    try:
        valor = float(t)
    except ValueError:
        raise ValueError(f"Quantidade inválida: {texto!r}") from None
    if not valor > 0 or valor != valor or valor == float("inf"):
        raise ValueError(f"Quantidade inválida: {texto!r}")
    return valor


def formatar_quantidade(quantidade: float) -> str:
    """2.0 -> '2', 1.5 -> '1,5', 0.25 -> '0,25'."""
    if float(quantidade).is_integer():
        return str(int(quantidade))
    return f"{quantidade:.3f}".rstrip("0").rstrip(".").replace(".", ",")


def total_do_item(quantidade: float, valor_unitario: int) -> int:
    """Quantidade x valor unitário (centavos), arredondado ao centavo."""
    total = Decimal(str(quantidade)) * Decimal(valor_unitario)
    return int(total.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def aplicar_percentual(centavos: int, percentual: float) -> int:
    """Calcula `percentual`% de um valor em centavos, arredondado ao centavo."""
    valor = Decimal(centavos) * Decimal(str(percentual)) / Decimal(100)
    return int(valor.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def formatar_percentual(percentual: float) -> str:
    """30.0 -> '30%', 12.5 -> '12,5%'."""
    return f"{formatar_quantidade(percentual)}%"
