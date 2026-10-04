import pytest

from oficina.dinheiro import (
    aplicar_percentual, formatar_compacto, formatar_quantidade, formatar_reais, texto_para_centavos,
    texto_para_quantidade, total_do_item,
)


@pytest.mark.parametrize("texto, esperado", [
    ("150", 15000),
    ("150,5", 15050),
    ("150,50", 15050),
    ("150.50", 15050),
    ("1.234,56", 123456),
    ("1.234", 123400),
    ("R$ 1.234,56", 123456),
    ("0,01", 1),
    (" 80 ", 8000),
])
def test_texto_para_centavos(texto, esperado):
    assert texto_para_centavos(texto) == esperado


@pytest.mark.parametrize("texto", ["", "abc", "1,2,3", "-5", "NaN", "1e5"])
def test_texto_para_centavos_invalido(texto):
    with pytest.raises(ValueError):
        texto_para_centavos(texto)


def test_formatar_reais():
    assert formatar_reais(15050) == "R$ 150,50"
    assert formatar_reais(123456789) == "R$ 1.234.567,89"
    assert formatar_reais(5, simbolo=False) == "0,05"
    assert formatar_reais(-1000) == "-R$ 10,00"


def test_formatar_compacto():
    assert formatar_compacto(0) == "0"
    assert formatar_compacto(85000) == "850"
    assert formatar_compacto(100000) == "1 mil"
    assert formatar_compacto(4823050) == "48,2 mil"
    assert formatar_compacto(99996000) == "1 mi"  # 999,96 mil arredondaria para "1000 mil"
    assert formatar_compacto(123456789) == "1,23 mi"
    assert formatar_compacto(-250000) == "-2,5 mil"


def test_quantidade():
    assert texto_para_quantidade("2") == 2
    assert texto_para_quantidade("1,5") == 1.5
    assert formatar_quantidade(2.0) == "2"
    assert formatar_quantidade(1.5) == "1,5"
    for invalido in ("0", "-1", "x", ""):
        with pytest.raises(ValueError):
            texto_para_quantidade(invalido)


def test_total_do_item_arredonda_meio_centavo_para_cima():
    assert total_do_item(3, 3333) == 9999
    assert total_do_item(1.5, 33) == 50  # 49,5 centavos -> 50
    assert total_do_item(0.1, 3) == 0


def test_aplicar_percentual():
    assert aplicar_percentual(15000, 30) == 4500
    assert aplicar_percentual(10001, 12.5) == 1250  # 1250,125 -> 1250
    assert aplicar_percentual(3333, 50) == 1667  # 1666,5 -> 1667
