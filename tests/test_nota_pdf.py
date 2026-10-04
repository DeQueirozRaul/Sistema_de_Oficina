"""Nota em PDF desenhada com o Qt: conteúdo (modelo), arquivo gerado e aparência."""

from datetime import date

import pytest

from conftest import item
from oficina.documentos import emissao, nota_pdf
from oficina.modelos import Orcamento, OrdemServico

OFICINA = {"nome": "AUTO CENTER EXEMPLO", "endereco": "Rua das Oficinas, 100", "telefone": "", "cnpj": ""}


def _os(**campos):
    padrao = dict(
        numero=1002, data=date(2026, 9, 25), mecanico_nome="Marcos", cliente_nome="João da Silva",
        cliente_documento="123.456.789-00", cliente_telefone="(61) 99999-0000", placa="ABC-1D23", modelo="Gol",
        ano="2015", km="120000", desconto=1000, observacoes="Revisar em 10.000 km",
        itens=[item("Amortecedor dianteiro", "peca", 2, 25000), item("Troca de amortecedor", "mao_de_obra", 1, 15000)],
    )
    padrao.update(campos)
    return OrdemServico(**padrao)


def _textos(nota):
    return [linha.texto() for linha in nota.linhas if linha.celulas]


def test_modelo_da_os_tem_o_mesmo_conteudo_da_nota_original():
    nota = nota_pdf.montar_os(_os(), OFICINA)
    assert nota.cabecalho.titulo == "ORDEM DE SERVIÇO - AUTO CENTER EXEMPLO"
    assert nota.cabecalho.linhas == ["Endereço: Rua das Oficinas, 100"]
    textos = _textos(nota)
    assert ["OS Nº:", "1002", "Data:", "25/09/2026"] in textos
    assert ["Mecânico:", "Marcos"] in textos
    assert ["Ano / KM:", "2015 / 120000"] == textos[5][2:]
    assert ["Amortecedor dianteiro", "2", "R$ 250,00", "R$ 500,00"] in textos
    assert ["Subtotal:", "R$ 650,00"] in textos
    assert ["Desconto:", "R$ 10,00"] in textos
    assert ["TOTAL GERAL:", "R$ 640,00"] in textos
    assert ["Assinatura do Técnico", "Assinatura do Cliente"] == textos[-1]


def test_cabecalho_com_telefone_e_cnpj():
    oficina = dict(OFICINA, telefone="(61) 3333-4444", cnpj="12.345.678/0001-99")
    nota = nota_pdf.montar_orcamento(Orcamento(numero=7, itens=[item()]), oficina)
    assert nota.cabecalho.titulo == "ORÇAMENTO - AUTO CENTER EXEMPLO"
    assert nota.cabecalho.linhas[1] == "Tel.: (61) 3333-4444   •   CNPJ: 12.345.678/0001-99"
    assert ["Orçamento Nº:", "7"] == _textos(nota)[0][:2]
    assert ["Observações / Validade:"] in _textos(nota)


def test_pdf_gerado_em_subpasta_do_mes(app, tmp_path):
    ok, caminho = emissao.emitir_os(_os(), OFICINA, tmp_path)
    assert ok, caminho
    assert caminho.endswith("2026-09/OS_ABC-1D23_1002.pdf".replace("/", __import__("os").sep))
    assert open(caminho, "rb").read(5) == b"%PDF-"


def test_muitos_itens_continuam_na_proxima_pagina(app, tmp_path):
    itens = [item(f"Item {i}", "peca", 1, 1000) for i in range(30)]  # ~720 pt de itens: 2 páginas
    assert nota_pdf.salvar_pdf(nota_pdf.montar_os(_os(itens=itens), OFICINA), tmp_path / "a.pdf") == 2
    assert nota_pdf.salvar_pdf(nota_pdf.montar_os(_os(), OFICINA), tmp_path / "b.pdf") == 1


def test_aparencia_faixa_azul_e_total_geral(app):
    """Confere as cores em pontos fixos da imagem (faixa do cabeçalho e linha do total)."""
    from PySide6.QtGui import QColor

    imagem = nota_pdf.imagem_previa(nota_pdf.montar_os(_os(), OFICINA), dpi=72)  # 1 px = 1 pt
    meio = imagem.width() // 2
    assert QColor(imagem.pixel(meio, 36 + 57)).name() == nota_pdf.AZUL_ESCURO.lower()  # faixa sob o endereço
    azuis = [y for y in range(imagem.height())
             if QColor(imagem.pixel(imagem.width() - 70, y)).name() == nota_pdf.AZUL_ESCURO.lower()]
    assert len(azuis) >= 20  # linha "TOTAL GERAL" (24 pt) pintada de azul na coluna do valor


def test_descricao_longa_quebra_linha_em_vez_de_cortar(app):
    from PySide6.QtGui import QImage

    longa = "Kit de suspensão dianteira completo com amortecedores, molas, batentes, coifas e coxins " * 2
    nota = nota_pdf.montar_os(_os(itens=[item(longa, "peca", 1, 100)]), OFICINA)
    imagem = QImage(10, 10, QImage.Format.Format_RGB32)
    imagem.setDotsPerMeterX(round(72 / 0.0254))
    from PySide6.QtGui import QPainter
    pintor = QPainter(imagem)
    altura = nota_pdf._Pintor(pintor, imagem).altura_necessaria(
        next(linha for linha in nota.linhas if linha.celulas and linha.celulas[0].texto == longa))
    pintor.end()
    assert altura > nota_pdf.ALTURA_LINHA


@pytest.mark.parametrize("placa, esperado", [("ABC/1234", "ABC1234"), ('A:B*C?"<>|', "ABC")])
def test_nome_de_arquivo_sem_caracteres_proibidos(placa, esperado):
    assert emissao.nome_arquivo(placa) == esperado
