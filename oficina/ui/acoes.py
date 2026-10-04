"""Ações usadas por mais de uma tela: gerar, abrir e enviar PDFs; pastas configuradas."""

import sys
from pathlib import Path

from PySide6.QtCore import QByteArray, QMimeData, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import QCheckBox, QMessageBox

from oficina import caminhos, whatsapp
from oficina.documentos import emissao
from oficina.modelos import Orcamento, OrdemServico
from oficina.servicos import configuracoes as cfg
from oficina.servicos import orcamentos, ordens
from oficina.ui import logo
from oficina.ui.componentes import abrir_arquivo, avisar, executar_em_segundo_plano
from oficina.ui.dialogos import DialogoWhatsApp

DICA_ERRO_PDF = ("Se o PDF anterior estiver aberto em outro programa, feche-o e tente de novo.\n"
                 "O documento já está salvo no sistema: você pode gerar o PDF depois pelo Histórico.")

_gerando_pdf = False


def pasta_os(conn) -> Path:
    return Path(cfg.obter(conn, cfg.PASTA_OS) or caminhos.pasta_padrao_os())


def pasta_orcamentos(conn) -> Path:
    return Path(cfg.obter(conn, cfg.PASTA_ORCAMENTOS) or caminhos.pasta_padrao_orcamentos())


def pasta_backups(conn) -> Path:
    return Path(cfg.obter(conn, cfg.PASTA_BACKUPS) or caminhos.pasta_padrao_backups())


def _gerar(janela, texto: str, tarefa, ao_salvar_caminho, depois) -> bool:
    global _gerando_pdf
    if _gerando_pdf:
        avisar(janela, "Aguarde: ainda há um PDF sendo gerado.")
        return False
    _gerando_pdf = True
    janela.definir_ocupado(True, texto)

    def terminou(resultado):
        global _gerando_pdf
        _gerando_pdf = False
        janela.definir_ocupado(False)
        sucesso, mensagem = resultado
        if sucesso:
            ao_salvar_caminho(mensagem)
        depois(sucesso, mensagem)

    executar_em_segundo_plano(tarefa, terminou)
    return True


def logo_da_nota(conn):
    """Logo para o cabeçalho da nota, se a oficina marcou essa opção em Configurações."""
    return logo.imagem_logo(conn, 400) if cfg.obter(conn, cfg.MOSTRAR_LOGO_NA_NOTA) == "1" else None


def gerar_pdf_os(janela, os_: OrdemServico, depois) -> bool:
    """Gera o PDF em segundo plano e chama depois(sucesso, caminho_ou_erro)."""
    conn = janela.conn
    oficina, pasta, imagem_logo = cfg.dados_oficina(conn), pasta_os(conn), logo_da_nota(conn)
    return _gerar(
        janela, f"Gerando o PDF da OS {os_.numero}... aguarde.",
        lambda: emissao.emitir_os(os_, oficina, pasta, imagem_logo),
        lambda caminho: ordens.definir_caminho_pdf(conn, os_.id, caminho),
        depois,
    )


def gerar_pdf_orcamento(janela, orcamento: Orcamento, depois) -> bool:
    conn = janela.conn
    oficina, pasta, imagem_logo = cfg.dados_oficina(conn), pasta_orcamentos(conn), logo_da_nota(conn)
    return _gerar(
        janela, f"Gerando o PDF do orçamento {orcamento.numero}... aguarde.",
        lambda: emissao.emitir_orcamento(orcamento, oficina, pasta, imagem_logo),
        lambda caminho: orcamentos.definir_caminho_pdf(conn, orcamento.id, caminho),
        depois,
    )


def abrir_pdf(parent, caminho: str) -> None:
    if not caminho or not abrir_arquivo(caminho):
        avisar(parent, "O PDF não foi encontrado: ainda não foi gerado, ou foi movido/apagado.\n"
                       "Use \"Gerar PDF\" para criá-lo novamente.")


# ---------------------------------------------------------------- WhatsApp

def numero_destino(conn, telefone_cliente: str = "") -> tuple[str, str]:
    """(número, "cliente" ou "loja") conforme a opção "Enviar para" das Configurações."""
    return whatsapp.numero_destino(cfg.obter(conn, cfg.WHATSAPP_DESTINO), telefone_cliente,
                                   cfg.obter(conn, cfg.WHATSAPP_NUMERO))


def envio_automatico_ativo(conn, telefone_cliente: str = "") -> bool:
    """Se, ao gerar o PDF, o WhatsApp deve abrir sozinho com a nota copiada.

    Só abre sozinho se já houver para quem enviar (celular do cliente ou número da loja).
    """
    return cfg.obter(conn, cfg.WHATSAPP_AUTOMATICO) == "1" and bool(numero_destino(conn, telefone_cliente)[0])


def copiar_arquivo(caminho: str) -> None:
    """Coloca o arquivo na área de transferência, como o "Copiar" do Windows Explorer,
    para que o Ctrl+V no WhatsApp anexe o PDF."""
    dados = QMimeData()
    dados.setUrls([QUrl.fromLocalFile(str(caminho))])
    if sys.platform == "win32":
        # Indica "copiar" (e não "recortar"), como o Explorer faz. 1 = DROPEFFECT_COPY.
        dados.setData('application/x-qt-windows-mime;value="Preferred DropEffect"', QByteArray(b"\x01\x00\x00\x00"))
    QGuiApplication.clipboard().setMimeData(dados)


def abrir_url(url: str) -> bool:
    return QDesktopServices.openUrl(QUrl(url))


def explicar_envio(parent) -> tuple[bool, bool]:
    """Explica o Ctrl+V na primeira vez. Devolve (continuar, não_mostrar_de_novo)."""
    caixa = QMessageBox(QMessageBox.Icon.Information, "Enviar no WhatsApp",
                        "O WhatsApp vai abrir na conversa (do cliente ou da loja) com o PDF já copiado.\n\n"
                        "Lá, é só apertar Ctrl+V e depois Enter.\n\n"
                        "Se o Ctrl+V não anexar o arquivo, clique no ícone de anexo do WhatsApp e escolha o PDF "
                        "na pasta Documentos > Sistema Oficina.", parent=parent)
    abrir = caixa.addButton("Abrir WhatsApp", QMessageBox.ButtonRole.AcceptRole)
    caixa.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
    caixa.setDefaultButton(abrir)
    nao_mostrar = QCheckBox("Não mostrar esta explicação de novo")
    caixa.setCheckBox(nao_mostrar)
    caixa.exec()
    return caixa.clickedButton() is abrir, nao_mostrar.isChecked()


def enviar_whatsapp(janela, caminho: str, documento: str, cliente_nome: str = "", cliente_telefone: str = "") -> bool:
    """Copia o PDF e abre a conversa do WhatsApp. `documento` ex.: "OS 1002".

    Vai para o celular do cliente (se houver e se as Configurações mandarem para o
    cliente); senão, para o WhatsApp da loja.
    """
    conn = janela.conn
    if not caminho or not Path(caminho).exists():
        avisar(janela, f"O PDF ({documento}) não foi encontrado. Gere o PDF antes de enviar.")
        return False
    numero, para = numero_destino(conn, cliente_telefone)
    if not numero:  # vai para a loja, mas o número dela ainda não foi informado
        if not DialogoWhatsApp(janela, conn).exec():
            return False
        numero, para = numero_destino(conn, cliente_telefone)
    if cfg.obter(conn, cfg.WHATSAPP_EXPLICACAO_VISTA) != "1":
        continuar, nao_mostrar = explicar_envio(janela)
        if nao_mostrar:
            cfg.salvar(conn, {cfg.WHATSAPP_EXPLICACAO_VISTA: "1"})
        if not continuar:
            return False

    modo = cfg.obter(conn, cfg.WHATSAPP_MODO)
    copiar_arquivo(caminho)
    aberto = abrir_url(whatsapp.url_conversa(numero, modo))
    if not aberto and modo != whatsapp.MODO_WEB:  # aplicativo não instalado: tenta o WhatsApp Web
        aberto = abrir_url(whatsapp.url_conversa(numero, whatsapp.MODO_WEB))
    if not aberto:
        avisar(janela, "Não foi possível abrir o WhatsApp. O PDF já está copiado: abra o WhatsApp, "
                       "entre na conversa e aperte Ctrl+V.")
        return False
    conversa = f"do cliente {cliente_nome}".rstrip() if para == whatsapp.DESTINO_CLIENTE else "da loja"
    janela.mensagem(f"{documento}: WhatsApp aberto na conversa {conversa} com o PDF copiado. "
                    "Aperte Ctrl+V e depois Enter para enviar.", 20000)
    return True


def enviar_whatsapp_os(janela, os_: OrdemServico) -> bool:
    return enviar_whatsapp(janela, os_.caminho_pdf, f"OS {os_.numero}", os_.cliente_nome, os_.cliente_telefone)


def enviar_whatsapp_orcamento(janela, orcamento: Orcamento) -> bool:
    """O orçamento não tem campos de cliente: usa o cliente dono do carro (pela placa), se houver."""
    cliente = orcamentos.cliente_do_orcamento(janela.conn, orcamento)
    return enviar_whatsapp(janela, orcamento.caminho_pdf, f"Orçamento {orcamento.numero}",
                           cliente.nome if cliente else "", cliente.telefone if cliente else "")
