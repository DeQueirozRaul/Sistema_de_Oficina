"""Testes da interface simulando o uso real (sem abrir janelas na tela)."""

import os
import time

import pytest

pytest.importorskip("PySide6.QtWidgets")

from oficina.banco import conectar  # noqa: E402
from oficina.modelos import Mecanico  # noqa: E402
from oficina.servicos import comissoes, mecanicos, ordens  # noqa: E402


class Respostas:
    """Substitui as caixas de mensagem: registra o texto e responde automaticamente."""

    def __init__(self):
        self.mensagens: list[str] = []
        self.escolha = 0
        self.confirmar = True

    def avisar(self, _parent, texto, *args, **kwargs):
        self.mensagens.append(texto)

    def perguntar(self, _parent, texto, *args, **kwargs):
        self.mensagens.append(texto)
        return self.confirmar

    def escolher(self, _parent, texto, opcoes, *args, **kwargs):
        self.mensagens.append(texto)
        return self.escolha


@pytest.fixture
def janela(app, tmp_path, monkeypatch):
    monkeypatch.setenv("OFICINA_DADOS", str(tmp_path))
    respostas = Respostas()
    from oficina.ui import (
        acoes, editor_itens, pagina_comissoes, pagina_historico, pagina_orcamento, pagina_os, pagina_relatorios,
    )
    for modulo in (acoes, editor_itens, pagina_comissoes, pagina_historico, pagina_orcamento, pagina_os,
                   pagina_relatorios):
        for nome in ("avisar", "mostrar_erro", "informar"):
            if hasattr(modulo, nome):
                monkeypatch.setattr(modulo, nome, respostas.avisar)
        for nome, funcao in (("perguntar", respostas.perguntar), ("escolher", respostas.escolher)):
            if hasattr(modulo, nome):
                monkeypatch.setattr(modulo, nome, funcao)
        if hasattr(modulo, "abrir_arquivo"):
            monkeypatch.setattr(modulo, "abrir_arquivo", lambda caminho: True)

    from oficina.ui.janela_principal import JanelaPrincipal
    conn = conectar(":memory:")
    mecanicos.salvar(conn, Mecanico("Marcos", 30))
    janela = JanelaPrincipal(conn)
    janela.respostas = respostas
    yield janela
    janela.pagina_os._modificado = False
    janela.pagina_orcamento._modificado = False
    janela.close()
    conn.close()


def _esperar(app, condicao, segundos=10):
    limite = time.time() + segundos
    while not condicao() and time.time() < limite:
        app.processEvents()
        time.sleep(0.01)
    assert condicao()


def _adicionar_item(editor, descricao, tipo, qtd, valor):
    editor.descricao.setText(descricao)
    editor.tipo.setCurrentIndex(editor.tipo.findData(tipo) if tipo else -1)
    editor.quantidade.setText(qtd)
    editor.valor.setText(valor)
    return editor._confirmar_item()


def test_fluxo_completo_da_os(app, janela, monkeypatch):
    pagina = janela.pagina_os
    janela.nova_os()
    assert pagina.numero.text() == "1000"

    # Item sem tipo é recusado com explicação
    assert not _adicionar_item(pagina.editor, "Amortecedor", None, "2", "285,00")
    assert "Mão de obra" in janela.respostas.mensagens[-1]

    assert _adicionar_item(pagina.editor, "Amortecedor", "peca", "2", "285,00")
    assert _adicionar_item(pagina.editor, "Troca de amortecedor", "mao_de_obra", "1", "180")
    pagina.placa.setText("abc1d23")
    pagina.modelo.setText("Gol")
    pagina.cliente.setText("João")
    pagina.mecanico.setCurrentIndex(0)
    assert "R$ 54,00" in pagina.totais._valores["comissao"].text()

    # Salvar em aberto
    pagina._salvar(finalizar=False, gerar_pdf=False)
    os_ = ordens.carregar(janela.conn, pagina.os_carregada.id)
    assert os_.status == "aberta" and os_.numero == 1000 and not pagina.modificado

    # Finalizar e gerar PDF (a emissão é simulada)
    from oficina.documentos import emissao
    pdf = os.path.join(os.environ["OFICINA_DADOS"], "OS_ABC1D23_1000.pdf")
    monkeypatch.setattr(emissao, "emitir_os", lambda *a: (True, pdf))
    janela.respostas.escolha = 3  # "Continuar nesta OS"
    pagina._salvar(finalizar=True, gerar_pdf=True)
    _esperar(app, lambda: ordens.carregar(janela.conn, os_.id).caminho_pdf == pdf)
    assert ordens.carregar(janela.conn, os_.id).status == "finalizada"
    assert "PDF gerado" in janela.respostas.mensagens[-1]

    # Comissão aparece e pode ser marcada como paga
    janela.ir_para("comissoes")
    tela = janela.pagina_comissoes
    tela.periodo.definir_modo("mes")
    assert tela.card_pendente._valor.text() == "R$ 54,00"
    tela._pagar_todas()
    assert comissoes.listar(janela.conn, os_.data, os_.data)[0].paga
    assert tela.card_paga._valor.text() == "R$ 54,00"

    # Editar OS com comissão paga pede confirmação
    janela.abrir_os(os_.id)
    assert "já foi paga" in pagina.faixa.text()
    _adicionar_item(pagina.editor, "Troca de bieleta", "mao_de_obra", "1", "100")
    janela.respostas.confirmar = False
    pagina._salvar(finalizar=False, gerar_pdf=False)
    assert "já foi paga" in janela.respostas.mensagens[-1]
    assert ordens.carregar(janela.conn, os_.id).totais.comissao == 5400

    # Cancelar pelo histórico
    pagina._modificado = False
    janela.respostas.confirmar = True
    janela.ir_para("historico")
    janela.pagina_historico.tabela_os.selectRow(0)
    janela.pagina_historico._cancelar_os()
    assert ordens.carregar(janela.conn, os_.id).status == "cancelada"
    assert not pagina.botao_principal.isVisible() or pagina.os_carregada.status == "cancelada"


def test_placa_conhecida_preenche_dados(app, janela):
    pagina = janela.pagina_os
    _adicionar_item(pagina.editor, "Pivô", "peca", "1", "80")
    pagina.placa.setText("XYZ1234")
    pagina.modelo.setText("Onix")
    pagina.ano.setText("2019")
    pagina.km.setText("50000")
    pagina.cliente.setText("Maria")
    pagina.telefone.setText("(61) 90000-0000")
    pagina._salvar(finalizar=False, gerar_pdf=False)

    pagina.nova(confirmar=False)
    pagina.placa.setText("xyz-1234")
    pagina._buscar_placa()
    assert (pagina.modelo.text(), pagina.ano.text(), pagina.cliente.text()) == ("Onix", "2019", "Maria")
    assert "50000" in pagina.km.placeholderText()


def test_autocompletar_sugere_tipo_e_valor_editavel(app, janela):
    pagina = janela.pagina_os
    _adicionar_item(pagina.editor, "Alinhamento", "terceiros", "1", "120")
    pagina.mecanico.setCurrentIndex(0)
    pagina._salvar(finalizar=True, gerar_pdf=False)

    pagina.nova(confirmar=False)
    editor = pagina.editor
    editor._sugestao_escolhida("alinhamento")
    assert editor.tipo.currentData() == "terceiros"
    assert editor.valor.text() == "120,00"
    editor.valor.setText("150")
    editor.descricao.setText("Alinhamento")
    assert editor._confirmar_item()
    assert editor.itens()[0].valor_unitario == 15000


def test_item_digitado_sem_adicionar_e_avisado(app, janela):
    pagina = janela.pagina_os
    pagina.editor.descricao.setText("Bucha")
    janela.respostas.escolha = 2  # "Voltar"
    pagina._salvar(finalizar=False, gerar_pdf=False)
    assert "não foi adicionado" in janela.respostas.mensagens[-1]
    assert pagina.os_carregada is None


def test_orcamento_vira_os(app, janela):
    tela = janela.pagina_orcamento
    janela.novo_orcamento()
    tela.placa.setText("QWE4R56")
    tela.modelo.setText("Onix")
    _adicionar_item(tela.editor, "Bieleta", "peca", "2", "45")
    _adicionar_item(tela.editor, "Troca de bieleta", "mao_de_obra", "1", "80")
    tela._transformar_em_os()  # salva o orçamento (perguntar -> Sim) e abre a OS
    assert janela.pilha.currentWidget() is janela.pagina_os
    os_tela = janela.pagina_os
    assert [i.tipo for i in os_tela.editor.itens()] == ["peca", "mao_de_obra"]
    assert "orçamento nº 1000" in os_tela.faixa.text()


def test_tema_claro_mesmo_com_windows_em_modo_escuro(app):
    """Com o Windows em modo escuro, calendário/diálogos ficavam com texto invisível."""
    from PySide6.QtGui import QColor, QPalette
    from oficina.ui import tema

    escura = QPalette()
    for papel, cor in ((QPalette.ColorRole.Window, "#202020"), (QPalette.ColorRole.Base, "#2B2B2B"),
                       (QPalette.ColorRole.Text, "#FFFFFF"), (QPalette.ColorRole.WindowText, "#FFFFFF")):
        escura.setColor(papel, QColor(cor))
    app.setPalette(escura)
    tema.aplicar(app)
    paleta = app.palette()
    assert paleta.color(QPalette.ColorRole.Base).name() == "#ffffff"
    assert paleta.color(QPalette.ColorRole.Window).lightness() > 200
    assert paleta.color(QPalette.ColorRole.Text).lightness() < 100
    assert paleta.color(QPalette.ColorRole.WindowText).lightness() < 100


def test_logo_padrao_e_logo_da_oficina(app, janela, tmp_path):
    from PySide6.QtGui import QColor, QImage
    from oficina.modelos import ErroValidacao
    from oficina.ui import logo

    assert logo.LOGO_PADRAO.exists()
    assert logo.caminho_logo_personalizada(janela.conn) is None
    assert not logo.pixmap_logo(janela.conn, 120).isNull()

    imagem = QImage(1200, 600, QImage.Format.Format_RGB32)
    imagem.fill(QColor("#C0392B"))
    arquivo = tmp_path / "minha_logo.jpg"
    imagem.save(str(arquivo))
    salva = logo.salvar_logo(janela.conn, arquivo)
    assert salva.exists() and logo.caminho_logo_personalizada(janela.conn) == salva
    assert max(QImage(str(salva)).width(), QImage(str(salva)).height()) == logo.TAMANHO_MAXIMO
    janela.configuracoes_alteradas()
    assert janela.logo.objectName() == "logoPersonalizada" and not janela.nome_oficina.isVisibleTo(janela)

    logo.usar_logo_padrao(janela.conn)
    assert logo.caminho_logo_personalizada(janela.conn) is None and not salva.exists()

    (tmp_path / "nao_e_imagem.png").write_text("texto")
    with pytest.raises(ErroValidacao):
        logo.salvar_logo(janela.conn, tmp_path / "nao_e_imagem.png")


# ---------------------------------------------------------------- WhatsApp

@pytest.fixture
def whatsapp_simulado(janela, monkeypatch, tmp_path):
    """Número configurado, explicação já vista e abertura de links registrada (sem abrir nada)."""
    from oficina.servicos import configuracoes as cfg
    from oficina.ui import acoes

    cfg.salvar(janela.conn, {cfg.WHATSAPP_NUMERO: "(61) 99999-0000", cfg.WHATSAPP_EXPLICACAO_VISTA: "1"})
    abertos: list[str] = []
    resultado = {"aplicativo_abre": True}

    def abrir_url(url):
        abertos.append(url)
        return resultado["aplicativo_abre"] or not url.startswith("whatsapp:")

    monkeypatch.setattr(acoes, "abrir_url", abrir_url)
    return abertos, resultado, cfg


def _pdf_falso(tmp_path, nome):
    caminho = tmp_path / nome
    caminho.write_bytes(b"%PDF-1.4 teste")
    return str(caminho)


def _caminho(texto):
    """Normaliza o caminho para comparar: no Windows o Qt usa "C:/..." e o Python "C:\\..."."""
    return os.path.normcase(os.path.normpath(texto))


def _arquivo_na_area_de_transferencia(app):
    return [_caminho(url.toLocalFile()) for url in app.clipboard().mimeData().urls()]


def test_os_gerada_abre_whatsapp_automaticamente(app, janela, whatsapp_simulado, monkeypatch, tmp_path):
    abertos, _, _ = whatsapp_simulado
    from oficina.documentos import emissao
    pdf = _pdf_falso(tmp_path, "OS_ABC1D23_1000.pdf")
    monkeypatch.setattr(emissao, "emitir_os", lambda *a: (True, pdf))

    pagina = janela.pagina_os
    _adicionar_item(pagina.editor, "Troca de pivô", "mao_de_obra", "1", "120")
    pagina.mecanico.setCurrentIndex(0)
    quantidade_mensagens = len(janela.respostas.mensagens)
    pagina._salvar(finalizar=True, gerar_pdf=True)
    _esperar(app, lambda: abertos)

    assert abertos == ["whatsapp://send?phone=5561999990000"]
    assert _arquivo_na_area_de_transferencia(app) == [_caminho(pdf)]
    assert len(janela.respostas.mensagens) == quantidade_mensagens  # nenhuma janela por cima do WhatsApp
    assert pagina.botao_whatsapp.isVisibleTo(pagina)


def test_orcamento_envia_pelo_whatsapp_ao_escolher(app, janela, whatsapp_simulado, monkeypatch, tmp_path):
    abertos, resultado, cfg = whatsapp_simulado
    cfg.salvar(janela.conn, {cfg.WHATSAPP_AUTOMATICO: "0"})
    resultado["aplicativo_abre"] = False  # sem o aplicativo instalado: usa o WhatsApp Web
    from oficina.documentos import emissao
    pdf = _pdf_falso(tmp_path, "ORC_QWE4R56_1000.pdf")
    monkeypatch.setattr(emissao, "emitir_orcamento", lambda *a: (True, pdf))

    tela = janela.pagina_orcamento
    _adicionar_item(tela.editor, "Bieleta", "peca", "2", "45")
    janela.respostas.escolha = 0  # "Enviar no WhatsApp"
    tela._gerar()
    _esperar(app, lambda: len(abertos) == 2)

    assert abertos == ["whatsapp://send?phone=5561999990000", "https://web.whatsapp.com/send?phone=5561999990000"]
    assert _arquivo_na_area_de_transferencia(app) == [_caminho(pdf)]


def test_historico_envia_os_e_orcamento(app, janela, whatsapp_simulado, tmp_path):
    abertos, _, _ = whatsapp_simulado
    from oficina.modelos import Item, Orcamento
    from oficina.servicos import orcamentos
    pdf_os, pdf_orc = _pdf_falso(tmp_path, "os.pdf"), _pdf_falso(tmp_path, "orc.pdf")

    pagina = janela.pagina_os
    _adicionar_item(pagina.editor, "Pivô", "peca", "1", "80")
    pagina.mecanico.setCurrentIndex(0)
    pagina._salvar(finalizar=True, gerar_pdf=False)
    ordens.definir_caminho_pdf(janela.conn, pagina.os_carregada.id, pdf_os)
    orcamento = orcamentos.salvar(janela.conn, Orcamento(itens=[Item("Pivô", "peca", 1, 8000)]))
    orcamentos.definir_caminho_pdf(janela.conn, orcamento.id, pdf_orc)

    historico = janela.pagina_historico
    janela.ir_para("historico")
    historico.tabela_os.selectRow(0)
    assert historico.botao_os_whatsapp.isEnabled()
    historico._whatsapp_os()
    assert _arquivo_na_area_de_transferencia(app) == [_caminho(pdf_os)]

    historico.abas.setCurrentIndex(1)
    historico.tabela_orc.selectRow(0)
    historico._whatsapp_orcamento()
    assert _arquivo_na_area_de_transferencia(app) == [_caminho(pdf_orc)]
    assert len(abertos) == 2


def test_whatsapp_sem_numero_pede_o_numero(app, janela, monkeypatch, tmp_path):
    from oficina.servicos import configuracoes as cfg
    from oficina.ui import acoes

    class DialogoFalso:
        def __init__(self, parent, conn):
            self.conn = conn

        def exec(self):
            cfg.salvar(self.conn, {cfg.WHATSAPP_NUMERO: "(61) 3333-4444"})
            return True

    abertos = []
    monkeypatch.setattr(acoes, "DialogoWhatsApp", DialogoFalso)
    monkeypatch.setattr(acoes, "abrir_url", lambda url: abertos.append(url) or True)
    monkeypatch.setattr(acoes, "explicar_envio", lambda parent: (True, True))

    assert acoes.enviar_whatsapp(janela, _pdf_falso(tmp_path, "x.pdf"), "OS 1")
    assert abertos == ["whatsapp://send?phone=556133334444"]
    assert cfg.obter(janela.conn, cfg.WHATSAPP_EXPLICACAO_VISTA) == "1"
    assert not acoes.enviar_whatsapp(janela, str(tmp_path / "nao_existe.pdf"), "OS 2")
    assert "não foi encontrado" in janela.respostas.mensagens[-1]


def test_inicio_sempre_abre_com_valores_escondidos(app, janela):
    from oficina.ui.pagina_inicio import VALOR_OCULTO

    pagina = janela.pagina_os
    _adicionar_item(pagina.editor, "Troca de pivô", "mao_de_obra", "1", "120")
    pagina.mecanico.setCurrentIndex(0)
    pagina._salvar(finalizar=True, gerar_pdf=False)

    janela.ir_para("inicio")
    inicio = janela.pagina_inicio
    assert inicio.card_faturamento._valor.text() == VALOR_OCULTO
    assert VALOR_OCULTO in inicio.card_os._detalhe.text()  # ticket médio
    assert inicio.card_os._valor.text() == "1"  # quantidade continua visível
    assert inicio.tabela_ultimas.item(0, 7).text() == VALOR_OCULTO
    assert "Mostrar" in inicio.botao_valores.text()

    inicio.botao_valores.click()
    assert inicio.card_faturamento._valor.text() == "R$ 120,00"
    inicio.periodo.definir_modo("semana")  # trocar o período não esconde de novo
    assert inicio.card_faturamento._valor.text() == "R$ 120,00"

    janela.ir_para("historico")
    janela.ir_para("inicio")  # voltou para o Início: escondido de novo
    assert inicio.card_faturamento._valor.text() == VALOR_OCULTO


def test_mecanico_sem_comissao_na_tela_de_os(app, janela):
    from oficina.modelos import Mecanico
    socio_id = mecanicos.salvar(janela.conn, Mecanico("Paulo", 0))
    pagina = janela.pagina_os
    pagina.ao_exibir()
    pagina.mecanico.setCurrentIndex(pagina.mecanico.findData(socio_id))
    assert pagina.rotulo_percentual.text() == "Sem comissão"
    assert pagina.totais._comissao_texto.text() == "Sem comissão (0%)"


def test_cor_da_barra_de_titulo_no_formato_do_windows():
    from oficina.ui.sistema_windows import _colorref
    assert _colorref("#1A365C") == 0x005C361A


def test_whatsapp_vai_para_o_celular_do_cliente(app, janela, whatsapp_simulado, monkeypatch, tmp_path):
    abertos, _, cfg = whatsapp_simulado
    from oficina.documentos import emissao
    pdf = _pdf_falso(tmp_path, "OS_cliente.pdf")
    monkeypatch.setattr(emissao, "emitir_os", lambda *a: (True, pdf))

    pagina = janela.pagina_os
    _adicionar_item(pagina.editor, "Troca de pivô", "mao_de_obra", "1", "120")
    pagina.mecanico.setCurrentIndex(0)
    pagina.placa.setText("ABC1D23")
    pagina.cliente.setText("João")
    pagina.telefone.setText("(61) 98888-7777")
    pagina._salvar(finalizar=True, gerar_pdf=True)
    _esperar(app, lambda: abertos)
    assert abertos == ["whatsapp://send?phone=5561988887777"]
    assert "cliente João" in janela.statusBar().currentMessage()

    # "Sempre a loja" nas Configurações
    cfg.salvar(janela.conn, {cfg.WHATSAPP_DESTINO: "loja"})
    pagina._enviar_whatsapp()
    assert abertos[-1] == "whatsapp://send?phone=5561999990000"
    assert "da loja" in janela.statusBar().currentMessage()


def test_whatsapp_cliente_com_telefone_fixo_vai_para_a_loja(app, janela, whatsapp_simulado, tmp_path):
    abertos, _, _ = whatsapp_simulado
    from oficina.ui import acoes
    acoes.enviar_whatsapp(janela, _pdf_falso(tmp_path, "x.pdf"), "OS 1", "Maria", "(61) 3333-4444")
    assert abertos == ["whatsapp://send?phone=5561999990000"]


def test_orcamento_vai_para_o_dono_do_carro(app, janela, whatsapp_simulado, tmp_path):
    abertos, _, _ = whatsapp_simulado
    from oficina.modelos import Item, Orcamento
    from oficina.servicos import orcamentos

    # Carro já cadastrado com cliente (vem de uma OS anterior)
    pagina = janela.pagina_os
    _adicionar_item(pagina.editor, "Pivô", "peca", "1", "80")
    pagina.placa.setText("QWE4R56")
    pagina.cliente.setText("Carlos")
    pagina.telefone.setText("(61) 97777-6666")
    pagina._salvar(finalizar=False, gerar_pdf=False)

    orcamento = orcamentos.salvar(janela.conn, Orcamento(placa="qwe-4r56", itens=[Item("Pivô", "peca", 1, 8000)]))
    orcamentos.definir_caminho_pdf(janela.conn, orcamento.id, _pdf_falso(tmp_path, "orc.pdf"))
    historico = janela.pagina_historico
    janela.ir_para("historico")
    historico.abas.setCurrentIndex(1)
    historico.tabela_orc.selectRow(0)
    historico._whatsapp_orcamento()
    assert abertos == ["whatsapp://send?phone=5561977776666"]


def test_whatsapp_do_cliente_nao_exige_numero_da_loja(app, janela, monkeypatch, tmp_path):
    from oficina.ui import acoes

    class DialogoQueNaoPodeAbrir:
        def __init__(self, *a):
            raise AssertionError("não deveria pedir o número da loja")

    abertos = []
    monkeypatch.setattr(acoes, "DialogoWhatsApp", DialogoQueNaoPodeAbrir)
    monkeypatch.setattr(acoes, "abrir_url", lambda url: abertos.append(url) or True)
    monkeypatch.setattr(acoes, "explicar_envio", lambda parent: (True, True))
    assert acoes.envio_automatico_ativo(janela.conn, "(61) 98888-7777")
    assert not acoes.envio_automatico_ativo(janela.conn, "")
    assert acoes.enviar_whatsapp(janela, _pdf_falso(tmp_path, "x.pdf"), "OS 1", "Ana", "(61) 98888-7777")
    assert abertos == ["whatsapp://send?phone=5561988887777"]



def test_finalizar_gera_o_pdf_de_verdade_em_segundo_plano(app, janela):
    """Sem simular a emissão: desenha a nota com o Qt numa thread e grava o arquivo."""
    from pathlib import Path

    pagina = janela.pagina_os
    _adicionar_item(pagina.editor, "Troca de pivô", "mao_de_obra", "1", "120")
    pagina.mecanico.setCurrentIndex(0)
    pagina.placa.setText("ABC1D23")
    janela.respostas.escolha = 3  # "Continuar nesta OS"
    pagina._salvar(finalizar=True, gerar_pdf=True)
    _esperar(app, lambda: ordens.carregar(janela.conn, pagina.os_carregada.id).caminho_pdf)
    caminho = Path(ordens.carregar(janela.conn, pagina.os_carregada.id).caminho_pdf)
    assert caminho.name == "OS_ABC1D23_1000.pdf" and caminho.read_bytes()[:5] == b"%PDF-"
    assert pagina.botao_abrir_pdf.isVisibleTo(pagina)


def test_relatorios_graficos_tabela_dica_e_exportacao(app, janela, monkeypatch, tmp_path):
    from datetime import date

    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QColor, QMouseEvent

    from conftest import item, nova_os
    from oficina.ui import pagina_relatorios
    from oficina.ui.graficos import COR_MAO_DE_OBRA, COR_PECA

    marcos = mecanicos.listar(janela.conn)[0]
    hoje = date.today()
    for valor in (20000, 40000):
        ordens.salvar(janela.conn, nova_os(marcos.id, data=hoje, itens=[
            item("Amortecedor", "peca", 1, valor), item("Troca de amortecedor", "mao_de_obra", 1, 10000)]),
            "finalizada")

    janela.ir_para("relatorios")
    pagina = janela.pagina_relatorios
    assert pagina.periodo.descricao_periodo().endswith(f"/{hoje.year}")
    assert pagina.card_os._valor.text() == "2"
    assert pagina.card_faturamento._valor.text() == "R$ 800,00"
    assert pagina.card_conversao._valor.text() == "—"

    grafico = pagina.bloco_faturamento.grafico
    assert pagina.bloco_faturamento.title() == "Faturamento por mês" and len(grafico._rotulos) == 12
    grafico.resize(800, 300)
    imagem = grafico.grab().toImage()
    cores = {imagem.pixelColor(x, y).name() for x in range(0, imagem.width(), 2) for y in range(0, imagem.height(), 2)}
    assert QColor(COR_PECA).name() in cores and QColor(COR_MAO_DE_OBRA).name() in cores

    # Passar o mouse sobre a última coluna (o mês atual) destaca a coluna e mostra os valores dela.
    area = grafico._area
    ponto = QPointF(area.right() - grafico._banda / 2, area.center().y())
    movimento = QMouseEvent(QEvent.Type.MouseMove, ponto, grafico.mapToGlobal(ponto), Qt.MouseButton.NoButton,
                            Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
    app.sendEvent(grafico, movimento)
    assert grafico.destaque == 11
    assert "R$ 800,00" in grafico._dicas[11] and "2 OS" in grafico._dicas[11]

    itens = pagina.bloco_itens.grafico
    assert [b.rotulo for b in itens._barras] == ["Amortecedor", "Troca de amortecedor"]
    assert [b.rotulo for b in pagina.bloco_mecanicos.grafico._barras] == ["Marcos"]

    pagina.bloco_itens.alternar()
    assert pagina.bloco_itens.mostrando_tabela() and pagina.bloco_itens.tabela.rowCount() == 2
    assert pagina.bloco_itens.botao_alternar.text() == "Ver gráfico"

    destino = tmp_path / "relatorio"
    monkeypatch.setattr(pagina_relatorios.QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: (str(destino), "")))
    pagina._exportar_excel()
    pagina._exportar_csv()
    assert (tmp_path / "relatorio.xlsx").stat().st_size > 0
    assert (tmp_path / "relatorio.csv").read_text(encoding="utf-8-sig").count("\n") == 3
    assert sum("Relatório salvo" in m for m in janela.respostas.mensagens) == 2
