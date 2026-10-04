"""Inicialização do programa: tema, idioma, banco, backup e tratamento de erros."""

import logging
import os
import sys
import traceback

from PySide6.QtCore import QLibraryInfo, QLocale, QLockFile, QTranslator
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QApplication

from oficina import caminhos
from oficina.banco import conectar
from oficina.servicos import backup
from oficina.servicos import configuracoes as cfg
from oficina.ui import acoes, tema
from oficina.ui import logo
from oficina.ui.componentes import informar, mostrar_erro
from oficina.ui.dialogos import DialogoConfiguracaoInicial
from oficina.ui.janela_principal import MENU, JanelaPrincipal
from oficina.ui.sistema_windows import identificar_aplicativo


def _configurar_log() -> None:
    logging.basicConfig(
        filename=caminhos.caminho_log(), level=logging.INFO, encoding="utf-8",
        format="%(asctime)s %(levelname)s %(message)s",
    )


def _tratar_erro_inesperado(tipo, valor, rastreamento) -> None:
    """Sem console no .exe, erros não tratados iriam sumir: registra no log e avisa na tela."""
    logging.error("Erro inesperado:\n%s", "".join(traceback.format_exception(tipo, valor, rastreamento)))
    try:
        mostrar_erro(None, f"Ocorreu um erro inesperado:\n{valor}\n\nOs detalhes foram salvos em:\n"
                           f"{caminhos.caminho_log()}\n\nSe continuar acontecendo, envie esse arquivo para o suporte.")
    except Exception:  # noqa: BLE001
        pass


def _traduzir_qt(app: QApplication) -> None:
    QLocale.setDefault(QLocale(QLocale.Language.Portuguese, QLocale.Country.Brazil))
    tradutor = QTranslator(app)
    if tradutor.load("qtbase_pt_BR", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        app.installTranslator(tradutor)


def verificar() -> int:
    """Autoteste do programa instalado: python main.py --verificar (ou SistemaOficina.exe --verificar).

    Abre a janela com uma oficina de demonstração em memória, passa por todas as
    telas, gera o PDF de uma OS, copia-o para a área de transferência e exporta
    o relatório em Excel, sem tocar nos dados reais. Devolve 0 se tudo funcionou.
    Usado no GitHub Actions para garantir que o .exe gerado leva tudo de que
    precisa (plugins do Qt, openpyxl...) e fecha sem erro.
    Erros vão para um arquivo de log, porque o .exe não tem console.
    """
    import tempfile
    from datetime import date, timedelta
    from pathlib import Path

    from oficina import demo
    from oficina.documentos import emissao
    from oficina.servicos import ordens, relatorios

    log = Path(tempfile.gettempdir()) / "sistema_oficina_verificacao.log"
    try:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as pasta:
            os.environ["OFICINA_DADOS"] = pasta
            app = QApplication.instance()
            if app is None:  # nos testes a QApplication já existe (e já tem muitas janelas: aplicar o tema seria lento)
                app = QApplication(sys.argv[:1])
                tema.aplicar(app)
            conn = conectar(":memory:")
            demo.gerar(conn, meses=2)
            janela = JanelaPrincipal(conn)
            janela.show()
            for chave, _ in MENU:
                janela.ir_para(chave)
                app.processEvents()
            os_ = ordens.carregar(conn, ordens.buscar(conn, limite=1)[0].id)
            ok, mensagem = emissao.emitir_os(os_, cfg.dados_oficina(conn), Path(pasta) / "OS")
            if not ok:
                raise RuntimeError(mensagem)
            acoes.copiar_arquivo(mensagem)  # como o botão do WhatsApp (o programa precisa fechar sem erro depois)
            fim = date.today()
            relatorios.exportar_excel(conn, fim - timedelta(days=60), fim, Path(pasta) / "relatorio.xlsx")
            janela.close()
            conn.close()
    except Exception:  # noqa: BLE001 - qualquer falha precisa virar código de saída
        log.write_text(traceback.format_exc(), encoding="utf-8")
        return 1
    log.write_text("ok\n", encoding="utf-8")
    return 0


def executar() -> int:
    identificar_aplicativo()
    app = QApplication(sys.argv)
    app.setApplicationName("Sistema Oficina")
    app.setWindowIcon(QIcon(QPixmap.fromImage(logo.renderizar_svg(logo.LOGO_PADRAO, 256))))
    tema.aplicar(app)
    _traduzir_qt(app)
    _configurar_log()
    sys.excepthook = _tratar_erro_inesperado

    trava = QLockFile(str(caminhos.pasta_dados() / "sistema.lock"))
    trava.setStaleLockTime(0)
    if not trava.tryLock(200):
        informar(None, "O sistema já está aberto neste computador.\nProcure a janela na barra de tarefas.")
        return 1

    conn = conectar(caminhos.caminho_banco())
    if cfg.obter(conn, cfg.CONFIGURACAO_INICIAL_FEITA) != "1":
        DialogoConfiguracaoInicial(None, conn).exec()

    try:
        backup.fazer_backup(conn, acoes.pasta_backups(conn))
    except Exception:  # noqa: BLE001 - backup não pode impedir de abrir
        logging.exception("Falha no backup ao abrir")

    janela = JanelaPrincipal(conn)
    janela.showMaximized()
    codigo = app.exec()
    conn.close()
    trava.unlock()
    return codigo
