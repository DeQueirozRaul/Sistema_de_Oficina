"""Histórico de OS e orçamentos: busca, reimpressão, cancelamento."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QMenu, QTabWidget, QVBoxLayout, QWidget

from oficina.dinheiro import formatar_reais
from oficina.modelos import STATUS_ABERTA, STATUS_CANCELADA, STATUS_FINALIZADA
from oficina.periodos import formatar_data
from oficina.servicos import orcamentos, ordens
from oficina.ui import acoes, tema
from oficina.ui.componentes import (
    CENTRO, DIREITA, Pagina, SeletorPeriodo, Tabela, abrir_arquivo, botao, botao_whatsapp, cabecalho, campo_busca,
    celula, mostrar_erro, perguntar, rotulo,
)


class PaginaHistorico(Pagina):
    def __init__(self, janela):
        super().__init__(janela)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 12)
        layout.addLayout(cabecalho("Histórico", "Todas as OS e orçamentos salvos. Clique duas vezes para abrir."))
        self.abas = QTabWidget()
        self.abas.addTab(self._montar_aba_os(), "Ordens de serviço")
        self.abas.addTab(self._montar_aba_orcamentos(), "Orçamentos")
        self.abas.currentChanged.connect(lambda _: self.ao_exibir())
        layout.addWidget(self.abas, 1)

    # ================================================================ OS

    def _montar_aba_os(self) -> QWidget:
        aba = QWidget()
        layout = QVBoxLayout(aba)
        layout.setContentsMargins(0, 10, 0, 0)
        filtros = QHBoxLayout()
        self.busca_os = campo_busca("Buscar por nº, placa, cliente, modelo ou mecânico", self._atualizar_os)
        self.status_os = QComboBox()
        for texto, valor in (("Todas as situações", None), ("Em aberto", STATUS_ABERTA),
                             ("Finalizadas", STATUS_FINALIZADA), ("Canceladas", STATUS_CANCELADA)):
            self.status_os.addItem(texto, valor)
        self.status_os.currentIndexChanged.connect(self._atualizar_os)
        self.periodo_os = SeletorPeriodo(modos=("tudo", "semana", "mes", "personalizado"), inicial="tudo")
        self.periodo_os.alterado.connect(self._atualizar_os)
        filtros.addWidget(self.busca_os, 1)
        filtros.addWidget(self.status_os)
        filtros.addWidget(self.periodo_os)
        layout.addLayout(filtros)

        self.tabela_os = Tabela(["Nº", "Data", "Situação", "Placa", "Modelo", "Cliente", "Mecânico", "Total"],
                                elastica=5)
        self.tabela_os.doubleClicked.connect(lambda _: self._abrir_os())
        self.tabela_os.itemSelectionChanged.connect(self._botoes_os)
        self.tabela_os.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabela_os.customContextMenuRequested.connect(self._menu_os)
        layout.addWidget(self.tabela_os, 1)

        rodape = QHBoxLayout()
        self.resumo_os = rotulo("", "dica")
        rodape.addWidget(self.resumo_os)
        rodape.addStretch()
        self.botao_os_abrir = botao("Abrir", self._abrir_os, primario=True)
        self.botao_os_pdf = botao("Abrir PDF", self._abrir_pdf_os)
        self.botao_os_whatsapp = botao_whatsapp(self._whatsapp_os)
        self.botao_os_gerar = botao("Refazer PDF", self._gerar_pdf_os, dica="Gera o PDF da OS novamente")
        self.botao_os_cancelar = botao("Cancelar OS", self._cancelar_os, perigo=True)
        self.botao_os_reativar = botao("Reativar OS", self._reativar_os)
        for b in (self.botao_os_cancelar, self.botao_os_reativar, self.botao_os_gerar, self.botao_os_whatsapp,
                  self.botao_os_pdf, self.botao_os_abrir):
            rodape.addWidget(b)
        layout.addLayout(rodape)
        return aba

    def _atualizar_os(self) -> None:
        inicio, fim = self.periodo_os.periodo()
        resultados = ordens.buscar(self.conn, self.busca_os.text(), self.status_os.currentData(), inicio, fim)
        linhas = []
        for r in resultados:
            linhas.append([
                celula(r.numero, CENTRO, negrito=True),
                celula(formatar_data(r.data), CENTRO),
                celula(r.status_texto, CENTRO, tema.CORES_STATUS[r.status]),
                celula(r.placa, CENTRO),
                r.modelo,
                r.cliente_nome,
                r.mecanico_nome,
                celula(formatar_reais(r.total), DIREITA),
            ])
        self.tabela_os.definir_linhas(linhas, resultados)
        finalizadas = [r for r in resultados if r.status == STATUS_FINALIZADA]
        self.resumo_os.setText(
            f"{len(resultados)} OS encontradas  •  {len(finalizadas)} finalizadas somando "
            f"{formatar_reais(sum(r.total for r in finalizadas))}")
        self._botoes_os()

    def _botoes_os(self) -> None:
        r = self.tabela_os.dado_selecionado()
        for b in (self.botao_os_abrir, self.botao_os_gerar):
            b.setEnabled(r is not None and (b is self.botao_os_abrir or r.status != STATUS_CANCELADA))
        self.botao_os_pdf.setEnabled(bool(r and r.caminho_pdf))
        self.botao_os_whatsapp.setEnabled(bool(r and r.caminho_pdf and r.status != STATUS_CANCELADA))
        self.botao_os_cancelar.setVisible(r is None or r.status != STATUS_CANCELADA)
        self.botao_os_cancelar.setEnabled(r is not None)
        self.botao_os_reativar.setVisible(r is not None and r.status == STATUS_CANCELADA)

    def _menu_os(self, posicao) -> None:
        linha = self.tabela_os.rowAt(posicao.y())
        if linha < 0:
            return
        self.tabela_os.selectRow(linha)
        r = self.tabela_os.dado_selecionado()
        menu = QMenu(self)
        menu.addAction("Abrir", self._abrir_os)
        menu.addAction("Abrir PDF", self._abrir_pdf_os).setEnabled(bool(r.caminho_pdf))
        if r.status != STATUS_CANCELADA:
            menu.addAction("Enviar no WhatsApp", self._whatsapp_os).setEnabled(bool(r.caminho_pdf))
            menu.addAction("Gerar PDF novamente", self._gerar_pdf_os)
            menu.addSeparator()
            menu.addAction("Cancelar OS", self._cancelar_os)
        else:
            menu.addAction("Reativar OS", self._reativar_os)
        if r.placa:
            menu.addSeparator()
            menu.addAction(f"Ver todas as OS da placa {r.placa}", lambda: self.filtrar_placa(r.placa))
        menu.exec(self.tabela_os.viewport().mapToGlobal(posicao))

    def _abrir_os(self) -> None:
        r = self.tabela_os.dado_selecionado()
        if r is not None:
            self.janela.abrir_os(r.id)

    def _abrir_pdf_os(self) -> None:
        r = self.tabela_os.dado_selecionado()
        if r is not None:
            acoes.abrir_pdf(self, r.caminho_pdf)

    def _whatsapp_os(self) -> None:
        r = self.tabela_os.dado_selecionado()
        if r is not None:
            acoes.enviar_whatsapp_os(self.janela, ordens.carregar(self.conn, r.id))

    def _gerar_pdf_os(self) -> None:
        r = self.tabela_os.dado_selecionado()
        if r is None:
            return
        os_ = ordens.carregar(self.conn, r.id)
        if os_.status == STATUS_ABERTA and not perguntar(
                self, f"A OS {os_.numero} ainda está em aberto. Gerar o PDF mesmo assim?",
                sim="Gerar PDF", nao="Voltar"):
            return
        acoes.gerar_pdf_os(self.janela, os_, lambda ok, msg: self._pdf_gerado(f"OS {os_.numero}", ok, msg))

    def _pdf_gerado(self, documento: str, sucesso: bool, mensagem: str) -> None:
        self.ao_exibir()
        if not sucesso:
            mostrar_erro(self, f"Não foi possível gerar o PDF da {documento}.\n\n{mensagem}\n\n{acoes.DICA_ERRO_PDF}")
            return
        self.janela.mensagem(f"PDF da {documento} gerado: {mensagem}")
        abrir_arquivo(mensagem)

    def _cancelar_os(self) -> None:
        r = self.tabela_os.dado_selecionado()
        if r is None:
            return
        if self.janela.os_em_edicao() == r.id and not self.janela.pagina_os.pode_descartar():
            return
        texto = (f"Cancelar a OS {r.numero} ({r.placa} - {r.cliente_nome})?\n\n"
                 "Ela deixa de contar no faturamento e na comissão.")
        if r.comissao_paga:
            texto += f"\n\nAtenção: a comissão desta OS ({formatar_reais(r.comissao)}) já foi paga ao mecânico."
        if not perguntar(self, texto, sim="Cancelar OS", nao="Voltar"):
            return
        ordens.cancelar(self.conn, r.id)
        self.janela.recarregar_os_em_edicao(r.id)
        self._atualizar_os()
        self.janela.mensagem(f"OS {r.numero} cancelada.")

    def _reativar_os(self) -> None:
        r = self.tabela_os.dado_selecionado()
        if r is None:
            return
        if not perguntar(self, f"Reativar a OS {r.numero}?\n\nEla volta a ficar \"Em aberto\". Confira os dados e "
                               "finalize novamente para contar no faturamento e na comissão.",
                         sim="Reativar", nao="Voltar"):
            return
        ordens.reativar(self.conn, r.id)
        self.janela.recarregar_os_em_edicao(r.id)
        self._atualizar_os()

    def filtrar_placa(self, placa: str) -> None:
        self.abas.setCurrentIndex(0)
        self.status_os.setCurrentIndex(0)
        self.periodo_os.definir_modo("tudo")
        self.busca_os.setText(placa)
        self._atualizar_os()

    # ================================================================ orçamentos

    def _montar_aba_orcamentos(self) -> QWidget:
        aba = QWidget()
        layout = QVBoxLayout(aba)
        layout.setContentsMargins(0, 10, 0, 0)
        filtros = QHBoxLayout()
        self.busca_orc = campo_busca("Buscar por nº, placa ou modelo", self._atualizar_orcamentos)
        self.periodo_orc = SeletorPeriodo(modos=("tudo", "semana", "mes", "personalizado"), inicial="tudo")
        self.periodo_orc.alterado.connect(self._atualizar_orcamentos)
        filtros.addWidget(self.busca_orc, 1)
        filtros.addWidget(self.periodo_orc)
        layout.addLayout(filtros)

        self.tabela_orc = Tabela(["Nº", "Data", "Placa", "Modelo", "Total", "Situação"], elastica=3)
        self.tabela_orc.doubleClicked.connect(lambda _: self._abrir_orcamento())
        self.tabela_orc.itemSelectionChanged.connect(self._botoes_orc)
        self.tabela_orc.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabela_orc.customContextMenuRequested.connect(self._menu_orcamento)
        layout.addWidget(self.tabela_orc, 1)

        rodape = QHBoxLayout()
        self.resumo_orc = rotulo("", "dica")
        rodape.addWidget(self.resumo_orc)
        rodape.addStretch()
        self.botao_orc_os = botao("Transformar em OS", self._transformar_em_os)
        self.botao_orc_gerar = botao("Refazer PDF", self._gerar_pdf_orcamento, dica="Gera o PDF do orçamento novamente")
        self.botao_orc_whatsapp = botao_whatsapp(self._whatsapp_orcamento)
        self.botao_orc_pdf = botao("Abrir PDF", self._abrir_pdf_orcamento)
        self.botao_orc_abrir = botao("Abrir", self._abrir_orcamento, primario=True)
        for b in (self.botao_orc_os, self.botao_orc_gerar, self.botao_orc_whatsapp, self.botao_orc_pdf,
                  self.botao_orc_abrir):
            rodape.addWidget(b)
        layout.addLayout(rodape)
        return aba

    def _atualizar_orcamentos(self) -> None:
        inicio, fim = self.periodo_orc.periodo()
        resultados = orcamentos.buscar(self.conn, self.busca_orc.text(), inicio, fim)
        linhas = []
        for r in resultados:
            if r.os_numero:
                situacao = celula(f"Virou a OS {r.os_numero}", CENTRO, tema.CORES_STATUS[STATUS_FINALIZADA])
            else:
                situacao = celula("Aguardando aprovação", CENTRO)
            linhas.append([celula(r.numero, CENTRO, negrito=True), celula(formatar_data(r.data), CENTRO),
                           celula(r.placa, CENTRO), r.modelo, celula(formatar_reais(r.total), DIREITA), situacao])
        self.tabela_orc.definir_linhas(linhas, resultados)
        aprovados = sum(1 for r in resultados if r.os_numero)
        self.resumo_orc.setText(f"{len(resultados)} orçamentos encontrados  •  {aprovados} viraram OS")
        self._botoes_orc()

    def _botoes_orc(self) -> None:
        r = self.tabela_orc.dado_selecionado()
        for b in (self.botao_orc_abrir, self.botao_orc_gerar, self.botao_orc_os):
            b.setEnabled(r is not None)
        self.botao_orc_pdf.setEnabled(bool(r and r.caminho_pdf))
        self.botao_orc_whatsapp.setEnabled(bool(r and r.caminho_pdf))

    def _menu_orcamento(self, posicao) -> None:
        linha = self.tabela_orc.rowAt(posicao.y())
        if linha < 0:
            return
        self.tabela_orc.selectRow(linha)
        r = self.tabela_orc.dado_selecionado()
        menu = QMenu(self)
        menu.addAction("Abrir", self._abrir_orcamento)
        menu.addAction("Abrir PDF", self._abrir_pdf_orcamento).setEnabled(bool(r.caminho_pdf))
        menu.addAction("Enviar no WhatsApp", self._whatsapp_orcamento).setEnabled(bool(r.caminho_pdf))
        menu.addAction("Gerar PDF novamente", self._gerar_pdf_orcamento)
        menu.addSeparator()
        menu.addAction("Transformar em OS", self._transformar_em_os)
        menu.exec(self.tabela_orc.viewport().mapToGlobal(posicao))

    def _whatsapp_orcamento(self) -> None:
        r = self.tabela_orc.dado_selecionado()
        if r is not None:
            acoes.enviar_whatsapp_orcamento(self.janela, orcamentos.carregar(self.conn, r.id))

    def _abrir_orcamento(self) -> None:
        r = self.tabela_orc.dado_selecionado()
        if r is not None:
            self.janela.abrir_orcamento(r.id)

    def _abrir_pdf_orcamento(self) -> None:
        r = self.tabela_orc.dado_selecionado()
        if r is not None:
            acoes.abrir_pdf(self, r.caminho_pdf)

    def _gerar_pdf_orcamento(self) -> None:
        r = self.tabela_orc.dado_selecionado()
        if r is None:
            return
        orcamento = orcamentos.carregar(self.conn, r.id)
        acoes.gerar_pdf_orcamento(self.janela, orcamento,
                                  lambda ok, msg: self._pdf_gerado(f"orçamento {orcamento.numero}", ok, msg))

    def _transformar_em_os(self) -> None:
        r = self.tabela_orc.dado_selecionado()
        if r is not None:
            self.janela.os_a_partir_do_orcamento(r.id)

    # ================================================================

    def ao_exibir(self) -> None:
        if self.abas.currentIndex() == 0:
            self._atualizar_os()
        else:
            self._atualizar_orcamentos()
