"""Janela principal: menu lateral + telas."""

import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMainWindow, QStackedWidget, QVBoxLayout, QWidget,
)

from oficina import VERSAO
from oficina.servicos import backup
from oficina.servicos import configuracoes as cfg
from oficina.ui import acoes, tema
from oficina.ui import logo
from oficina.ui.componentes import perguntar, rotulo
from oficina.ui.sistema_windows import pintar_barra_de_titulo
from oficina.ui.pagina_clientes import PaginaClientes
from oficina.ui.pagina_comissoes import PaginaComissoes
from oficina.ui.pagina_configuracoes import PaginaConfiguracoes
from oficina.ui.pagina_historico import PaginaHistorico
from oficina.ui.pagina_inicio import PaginaInicio
from oficina.ui.pagina_mecanicos import PaginaMecanicos
from oficina.ui.pagina_orcamento import PaginaOrcamento
from oficina.ui.pagina_os import PaginaOS

MENU = [
    ("inicio", "Início"),
    ("os", "Ordem de Serviço"),
    ("orcamento", "Orçamento"),
    ("historico", "Histórico"),
    ("comissoes", "Comissões"),
    ("clientes", "Clientes e veículos"),
    ("mecanicos", "Mecânicos"),
    ("configuracoes", "Configurações"),
]


class JanelaPrincipal(QMainWindow):
    def __init__(self, conn):
        super().__init__()
        self.conn = conn
        self.setMinimumSize(1100, 680)

        # ---- menu lateral
        lateral = QFrame()
        lateral.setObjectName("barraLateral")
        lateral.setFixedWidth(215)
        caixa = QVBoxLayout(lateral)
        caixa.setContentsMargins(0, 14, 0, 12)
        self.logo = QLabel()
        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.nome_oficina = rotulo("", "nomeOficina", quebra=True)
        self.nome_oficina.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.nome_oficina.setContentsMargins(12, 8, 12, 0)
        caixa.addWidget(self.logo, alignment=Qt.AlignmentFlag.AlignHCenter)
        caixa.addWidget(self.nome_oficina)
        caixa.addSpacing(14)
        self.menu = QListWidget()
        self.menu.setObjectName("menuLateral")
        self.menu.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.menu.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        for chave, texto in MENU:
            item = QListWidgetItem(texto)
            item.setData(Qt.ItemDataRole.UserRole, chave)
            self.menu.addItem(item)
        caixa.addWidget(self.menu, 1)
        versao = rotulo(f"versão {VERSAO}", "versao")
        versao.setContentsMargins(18, 0, 0, 0)
        caixa.addWidget(versao)

        # ---- telas
        self.pilha = QStackedWidget()
        self.pilha.setObjectName("conteudo")
        self.pagina_inicio = PaginaInicio(self)
        self.pagina_os = PaginaOS(self)
        self.pagina_orcamento = PaginaOrcamento(self)
        self.pagina_historico = PaginaHistorico(self)
        self.pagina_comissoes = PaginaComissoes(self)
        self.pagina_clientes = PaginaClientes(self)
        self.pagina_mecanicos = PaginaMecanicos(self)
        self.pagina_configuracoes = PaginaConfiguracoes(self)
        self.paginas = {
            "inicio": self.pagina_inicio, "os": self.pagina_os, "orcamento": self.pagina_orcamento,
            "historico": self.pagina_historico, "comissoes": self.pagina_comissoes, "clientes": self.pagina_clientes,
            "mecanicos": self.pagina_mecanicos, "configuracoes": self.pagina_configuracoes,
        }
        for pagina in self.paginas.values():
            self.pilha.addWidget(pagina)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(lateral)
        layout.addWidget(self.pilha, 1)
        self.setCentralWidget(central)

        self.menu.currentRowChanged.connect(self._menu_mudou)
        self.configuracoes_alteradas()
        self.ir_para("inicio")

    # ------------------------------------------------------------ navegação

    def ir_para(self, chave: str) -> None:
        linha = [c for c, _ in MENU].index(chave)
        if self.menu.currentRow() == linha:
            self._menu_mudou(linha)
        else:
            self.menu.setCurrentRow(linha)

    def _menu_mudou(self, linha: int) -> None:
        pagina = self.paginas[MENU[linha][0]]
        self.pilha.setCurrentWidget(pagina)
        pagina.ao_exibir()

    def nova_os(self) -> None:
        self.ir_para("os")
        self.pagina_os.nova()

    def abrir_os(self, os_id: int) -> None:
        if self.pagina_os.carregar(os_id):
            self.ir_para("os")

    def novo_orcamento(self) -> None:
        self.ir_para("orcamento")
        self.pagina_orcamento.novo()

    def abrir_orcamento(self, orcamento_id: int) -> None:
        if self.pagina_orcamento.carregar(orcamento_id):
            self.ir_para("orcamento")

    def os_a_partir_do_orcamento(self, orcamento_id: int) -> None:
        if self.pagina_os.carregar_de_orcamento(orcamento_id):
            self.ir_para("os")

    def historico_da_placa(self, placa: str) -> None:
        self.ir_para("historico")
        self.pagina_historico.filtrar_placa(placa)

    def comissoes_do_mecanico(self, mecanico_id: int | None, pendentes: bool = False) -> None:
        self.ir_para("comissoes")
        if pendentes:
            self.pagina_comissoes.mostrar_pendentes(mecanico_id)
        else:
            self.pagina_comissoes.filtrar_mecanico(mecanico_id)

    def os_em_edicao(self) -> int | None:
        os_ = self.pagina_os.os_carregada
        return os_.id if os_ else None

    def recarregar_os_em_edicao(self, os_id: int) -> None:
        """Se a OS alterada no Histórico está aberta na tela de OS, recarrega."""
        if self.os_em_edicao() == os_id:
            self.pagina_os.recarregar()

    # ------------------------------------------------------------ utilidades

    def mensagem(self, texto: str, milissegundos: int = 6000) -> None:
        self.statusBar().showMessage(texto, milissegundos)

    def definir_ocupado(self, ocupado: bool, texto: str = "") -> None:
        if ocupado:
            QGuiApplication.setOverrideCursor(Qt.CursorShape.BusyCursor)
            self.statusBar().showMessage(texto)
        else:
            QGuiApplication.restoreOverrideCursor()
            self.statusBar().clearMessage()

    def configuracoes_alteradas(self) -> None:
        nome = cfg.obter(self.conn, cfg.NOME_OFICINA) or "Sistema de Oficina"
        self.nome_oficina.setText(nome)
        self.setWindowTitle(f"{nome} — Sistema de Oficina")
        personalizada = logo.caminho_logo_personalizada(self.conn) is not None
        if personalizada:
            # Logo da oficina (cores desconhecidas): num cartão branco, com o nome já na própria imagem.
            self.logo.setPixmap(logo.pixmap_logo(self.conn, 165, 120))
            self.logo.setObjectName("logoPersonalizada")
        else:
            self.logo.setPixmap(logo.pixmap_logo(self.conn, 120))
            self.logo.setObjectName("")
        self.logo.style().unpolish(self.logo)
        self.logo.style().polish(self.logo)
        self.nome_oficina.setVisible(not personalizada)
        self.setWindowIcon(QIcon(logo.pixmap_logo(self.conn, 256)))

    def showEvent(self, evento) -> None:  # noqa: N802 (nome do Qt)
        super().showEvent(evento)
        pintar_barra_de_titulo(self, tema.AZUL_ESCURO)  # barra de título na cor do menu lateral

    def closeEvent(self, evento) -> None:  # noqa: N802 (nome do Qt)
        pendentes = [nome for nome, pagina in (("OS", self.pagina_os), ("orçamento", self.pagina_orcamento))
                     if pagina.modificado]
        if pendentes and not perguntar(
                self, f"Existem alterações não salvas ({' e '.join(pendentes)}).\nDeseja sair mesmo assim?",
                titulo="Sair do sistema", sim="Sair sem salvar", nao="Voltar"):
            evento.ignore()
            return
        try:
            backup.fazer_backup(self.conn, acoes.pasta_backups(self.conn))
        except Exception:  # noqa: BLE001 - backup não pode impedir de fechar
            logging.exception("Falha no backup ao fechar")
        evento.accept()
