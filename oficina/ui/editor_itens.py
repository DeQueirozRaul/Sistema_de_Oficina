"""Lista de peças e serviços da OS/orçamento, com o tipo de cada item.

O tipo precisa ser escolhido em todo item novo: só "Mão de obra" gera
comissão, então não há um padrão que possa causar erro silencioso. Ao
escolher uma descrição já usada antes (autocompletar), o tipo e o último valor
são preenchidos, e o valor pode ser alterado livremente.
"""

from PySide6.QtCore import QStringListModel, Qt, Signal
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox, QCompleter, QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMenu, QVBoxLayout, QWidget,
)

from oficina.dinheiro import formatar_quantidade, formatar_reais, texto_para_quantidade
from oficina.modelos import TIPOS_ITEM, Item, Totais
from oficina.servicos import catalogo
from oficina.ui import tema
from oficina.ui.componentes import (
    CENTRO, DIREITA, CampoDinheiro, Tabela, avisar, botao, celula, escolher, rotulo,
)


class EditorItens(QWidget):
    alterado = Signal()

    def __init__(self, conn):
        super().__init__()
        self.conn = conn
        self._itens: list[Item] = []
        self._editando: int | None = None
        self._sugestoes: dict[str, catalogo.ItemCatalogo] = {}
        self._somente_leitura = False

        # ---- linha de digitação
        self.descricao = QLineEdit()
        self.descricao.setPlaceholderText("Digite para ver sugestões")
        self._modelo_sugestoes = QStringListModel(self)
        completar = QCompleter(self._modelo_sugestoes, self)
        completar.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completar.setFilterMode(Qt.MatchFlag.MatchContains)
        completar.setMaxVisibleItems(12)
        self.descricao.setCompleter(completar)
        completar.activated[str].connect(self._sugestao_escolhida)  # depois do setCompleter
        self.descricao.editingFinished.connect(self._preencher_se_conhecido)
        self.descricao.returnPressed.connect(lambda: self.tipo.setFocus())

        self.tipo = QComboBox()
        for chave, nome in TIPOS_ITEM.items():
            self.tipo.addItem(nome, chave)
            self.tipo.setItemData(self.tipo.count() - 1, QColor(tema.CORES_TIPO[chave][0]),
                                  Qt.ItemDataRole.ForegroundRole)
        self.tipo.setPlaceholderText("Escolha o tipo...")
        self.tipo.setCurrentIndex(-1)
        self.tipo.setMinimumWidth(170)
        self.tipo.setToolTip("Só os itens de MÃO DE OBRA geram comissão para o mecânico.")

        self.quantidade = QLineEdit("1")
        self.quantidade.setAlignment(CENTRO)
        self.quantidade.setMaximumWidth(60)
        self.quantidade.returnPressed.connect(self._confirmar_item)

        self.valor = CampoDinheiro()
        self.valor.setMaximumWidth(120)
        self.valor.returnPressed.connect(self._confirmar_item)

        self.botao_adicionar = botao("Adicionar", self._confirmar_item, primario=True)
        self.botao_cancelar = botao("Cancelar", lambda: self._sair_da_edicao())
        self.botao_cancelar.hide()

        entrada = QGridLayout()
        entrada.setHorizontalSpacing(8)
        entrada.setVerticalSpacing(2)
        for coluna, texto in enumerate(("Descrição", "Tipo", "Qtd", "Valor unit. (R$)")):
            entrada.addWidget(rotulo(texto, "dica"), 0, coluna)
        entrada.addWidget(self.descricao, 1, 0)
        entrada.addWidget(self.tipo, 1, 1)
        entrada.addWidget(self.quantidade, 1, 2)
        entrada.addWidget(self.valor, 1, 3)
        entrada.addWidget(self.botao_adicionar, 1, 4)
        entrada.addWidget(self.botao_cancelar, 1, 5)
        entrada.setColumnStretch(0, 1)

        # ---- tabela
        self.tabela = Tabela(["Descrição", "Tipo", "Qtd", "Vlr. unit.", "Total"], elastica=0)
        self.tabela.setMinimumHeight(170)
        self.tabela.doubleClicked.connect(lambda _: self._editar_selecionado())
        self.tabela.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabela.customContextMenuRequested.connect(self._menu_contexto)
        self.tabela.itemSelectionChanged.connect(self._atualizar_botoes)
        atalho = QShortcut(QKeySequence(Qt.Key.Key_Delete), self.tabela)
        atalho.setContext(Qt.ShortcutContext.WidgetShortcut)
        atalho.activated.connect(self._excluir_selecionado)

        self.botao_editar = botao("Editar", self._editar_selecionado, pequeno=True)
        self.botao_excluir = botao("Excluir", self._excluir_selecionado, pequeno=True, perigo=True)
        self.botao_subir = botao("↑", lambda: self._mover(-1), pequeno=True, dica="Mover para cima")
        self.botao_descer = botao("↓", lambda: self._mover(1), pequeno=True, dica="Mover para baixo")
        acoes = QHBoxLayout()
        acoes.addWidget(rotulo("Clique duas vezes num item para editar.", "dica"))
        acoes.addStretch()
        for b in (self.botao_editar, self.botao_excluir, self.botao_subir, self.botao_descer):
            acoes.addWidget(b)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(entrada)
        layout.addWidget(self.tabela, 1)
        layout.addLayout(acoes)
        self._atualizar_botoes()
        self.atualizar_sugestoes()

    # ------------------------------------------------------------ API

    def itens(self) -> list[Item]:
        return list(self._itens)

    def definir_itens(self, itens: list[Item]) -> None:
        self._itens = [Item(i.descricao, i.tipo, i.quantidade, i.valor_unitario) for i in itens]
        self._sair_da_edicao()
        self._atualizar_tabela()

    def limpar(self) -> None:
        self.definir_itens([])

    def definir_somente_leitura(self, somente_leitura: bool) -> None:
        self._somente_leitura = somente_leitura
        for widget in (self.descricao, self.tipo, self.quantidade, self.valor, self.botao_adicionar):
            widget.setEnabled(not somente_leitura)
        self._atualizar_botoes()

    def atualizar_sugestoes(self) -> None:
        itens = catalogo.listar(self.conn)
        self._sugestoes = {item.descricao.casefold(): item for item in itens}
        self._modelo_sugestoes.setStringList([item.descricao for item in itens])

    def confirmar_pendencias(self) -> bool:
        """Chamado antes de salvar a OS. Trata item digitado e não adicionado."""
        if self._editando is not None:
            escolha = escolher(self, "Você está editando um item. Deseja salvar a alteração dele?",
                               ["Salvar item", "Descartar alteração", "Voltar"])
            if escolha == 0:
                return self._confirmar_item()
            if escolha == 1:
                self._sair_da_edicao()
                return True
            return False
        if self.descricao.text().strip():
            escolha = escolher(self, f"O item \"{self.descricao.text().strip()}\" foi digitado mas não foi adicionado.",
                               ["Adicionar item", "Ignorar item", "Voltar"])
            if escolha == 0:
                return self._confirmar_item()
            if escolha == 1:
                self._limpar_entrada()
                return True
            return False
        return True

    # ------------------------------------------------------------ digitação

    def _sugestao_escolhida(self, texto: str) -> None:
        sugestao = self._sugestoes.get(texto.casefold())
        if sugestao is None:
            return
        self.tipo.setCurrentIndex(self.tipo.findData(sugestao.tipo))
        self.valor.definir_centavos(sugestao.valor_unitario)
        if not self.quantidade.text().strip():
            self.quantidade.setText("1")
        self.valor.setFocus()
        self.valor.selectAll()

    def _preencher_se_conhecido(self) -> None:
        """Se digitou uma descrição conhecida sem usar a lista, preenche o que estiver vazio."""
        sugestao = self._sugestoes.get(self.descricao.text().strip().casefold())
        if sugestao is None:
            return
        if self.tipo.currentIndex() < 0:
            self.tipo.setCurrentIndex(self.tipo.findData(sugestao.tipo))
        if not self.valor.text().strip():
            self.valor.definir_centavos(sugestao.valor_unitario)

    def _confirmar_item(self) -> bool:
        descricao = self.descricao.text().strip()
        if not descricao:
            avisar(self, "Digite a descrição do item.")
            self.descricao.setFocus()
            return False
        tipo = self.tipo.currentData()
        if tipo is None:
            avisar(self, "Escolha o tipo do item: Peça, Mão de obra ou Serviço terceirizado.\n\n"
                         "Só os itens de Mão de obra geram comissão para o mecânico.")
            self.tipo.setFocus()
            self.tipo.showPopup()
            return False
        try:
            quantidade = texto_para_quantidade(self.quantidade.text() or "1")
        except ValueError:
            avisar(self, "A quantidade deve ser um número maior que zero (ex.: 1, 2 ou 1,5).")
            self.quantidade.setFocus()
            return False
        try:
            valor = self.valor.centavos()
        except ValueError:
            avisar(self, "Digite o valor unitário do item (ex.: 150 ou 150,50).")
            self.valor.setFocus()
            return False

        item = Item(descricao, tipo, quantidade, valor)
        if self._editando is None:
            self._itens.append(item)
            linha = len(self._itens) - 1
        else:
            linha = self._editando
            self._itens[linha] = item
        self._sair_da_edicao()
        self._atualizar_tabela()
        self.tabela.scrollToItem(self.tabela.item(linha, 0))
        self.alterado.emit()
        self.descricao.setFocus()
        return True

    def _limpar_entrada(self) -> None:
        self.descricao.clear()
        self.tipo.setCurrentIndex(-1)
        self.quantidade.setText("1")
        self.valor.clear()

    def _sair_da_edicao(self) -> None:
        self._editando = None
        self._limpar_entrada()
        self.botao_adicionar.setText("Adicionar")
        self.botao_cancelar.hide()
        self._atualizar_botoes()

    # ------------------------------------------------------------ tabela

    def _atualizar_tabela(self) -> None:
        linhas = []
        for item in self._itens:
            linhas.append([
                celula(item.descricao),
                celula(TIPOS_ITEM[item.tipo], CENTRO, tema.CORES_TIPO[item.tipo], negrito=True),
                celula(formatar_quantidade(item.quantidade), CENTRO),
                celula(formatar_reais(item.valor_unitario), DIREITA),
                celula(formatar_reais(item.total), DIREITA),
            ])
        self.tabela.definir_linhas(linhas)
        self._atualizar_botoes()

    def _linha_selecionada(self) -> int | None:
        linhas = self.tabela.linhas_selecionadas()
        return linhas[0] if linhas else None

    def _atualizar_botoes(self) -> None:
        linha = self._linha_selecionada()
        pode = linha is not None and not self._somente_leitura and self._editando is None
        self.botao_editar.setEnabled(pode)
        self.botao_excluir.setEnabled(pode)
        self.botao_subir.setEnabled(pode and linha > 0)
        self.botao_descer.setEnabled(pode and linha < len(self._itens) - 1)

    def _editar_selecionado(self) -> None:
        linha = self._linha_selecionada()
        if linha is None or self._somente_leitura:
            return
        item = self._itens[linha]
        self._editando = linha
        self.descricao.setText(item.descricao)
        self.tipo.setCurrentIndex(self.tipo.findData(item.tipo))
        self.quantidade.setText(formatar_quantidade(item.quantidade))
        self.valor.definir_centavos(item.valor_unitario)
        self.botao_adicionar.setText("Salvar item")
        self.botao_cancelar.show()
        self._atualizar_botoes()
        self.descricao.setFocus()

    def _excluir_selecionado(self) -> None:
        linha = self._linha_selecionada()
        if linha is None or self._somente_leitura or self._editando is not None:
            return
        del self._itens[linha]
        self._atualizar_tabela()
        self.alterado.emit()

    def _mover(self, passo: int) -> None:
        linha = self._linha_selecionada()
        if linha is None or self._somente_leitura:
            return
        destino = linha + passo
        if not 0 <= destino < len(self._itens):
            return
        self._itens[linha], self._itens[destino] = self._itens[destino], self._itens[linha]
        self._atualizar_tabela()
        self.tabela.selectRow(destino)
        self.alterado.emit()

    def _menu_contexto(self, posicao) -> None:
        linha = self.tabela.rowAt(posicao.y())
        if linha < 0 or self._somente_leitura:
            return
        self.tabela.selectRow(linha)
        menu = QMenu(self)
        menu.addAction("Editar", self._editar_selecionado)
        menu.addAction("Excluir", self._excluir_selecionado)
        menu.addSeparator()
        menu.addAction("Mover para cima", lambda: self._mover(-1)).setEnabled(linha > 0)
        menu.addAction("Mover para baixo", lambda: self._mover(1)).setEnabled(linha < len(self._itens) - 1)
        menu.exec(self.tabela.viewport().mapToGlobal(posicao))


class PainelTotais(QGroupBox):
    """Resumo de valores: peças, mão de obra, terceiros, desconto, total e comissão."""

    desconto_alterado = Signal()

    def __init__(self, mostrar_comissao: bool = True):
        super().__init__("Totais")
        self.setFixedWidth(330)
        grade = QGridLayout(self)
        grade.setVerticalSpacing(5)
        self._valores = {}
        linhas = [("pecas", "Peças"), ("mao_de_obra", "Mão de obra"), ("terceiros", "Serviços terceirizados")]
        for linha, (chave, texto) in enumerate(linhas):
            cor = tema.CORES_TIPO[{"pecas": "peca"}.get(chave, chave)][0]
            marcador = QLabel(f"<span style='color:{cor}'>●</span> {texto}")
            grade.addWidget(marcador, linha, 0)
            self._valores[chave] = self._valor_rotulo()
            grade.addWidget(self._valores[chave], linha, 1)

        separador = QFrame()
        separador.setFrameShape(QFrame.Shape.HLine)
        separador.setStyleSheet(f"color: {tema.LINHA};")
        grade.addWidget(separador, 3, 0, 1, 2)

        grade.addWidget(QLabel("Subtotal"), 4, 0)
        self._valores["subtotal"] = self._valor_rotulo()
        grade.addWidget(self._valores["subtotal"], 4, 1)

        grade.addWidget(QLabel("Desconto (R$)"), 5, 0)
        self.campo_desconto = CampoDinheiro()
        self.campo_desconto.setMaximumWidth(130)
        self.campo_desconto.textChanged.connect(lambda _: self.desconto_alterado.emit())
        grade.addWidget(self.campo_desconto, 5, 1, alignment=DIREITA)

        total_rotulo = QLabel("TOTAL")
        total_rotulo.setStyleSheet(f"font-weight: 700; color: {tema.AZUL_ESCURO}; font-size: 12pt;")
        grade.addWidget(total_rotulo, 6, 0)
        self._valores["total"] = self._valor_rotulo()
        self._valores["total"].setStyleSheet(f"font-weight: 700; color: {tema.AZUL_ESCURO}; font-size: 13pt;")
        grade.addWidget(self._valores["total"], 6, 1)

        self._comissao_texto = QLabel("Comissão prevista")
        self._comissao_texto.setStyleSheet(f"color: {tema.CORES_TIPO['mao_de_obra'][0]};")
        self._valores["comissao"] = self._valor_rotulo()
        self._valores["comissao"].setStyleSheet(f"color: {tema.CORES_TIPO['mao_de_obra'][0]}; font-weight: 600;")
        grade.addWidget(self._comissao_texto, 7, 0)
        grade.addWidget(self._valores["comissao"], 7, 1)
        self._comissao_texto.setVisible(mostrar_comissao)
        self._valores["comissao"].setVisible(mostrar_comissao)

    @staticmethod
    def _valor_rotulo() -> QLabel:
        r = QLabel("R$ 0,00")
        r.setAlignment(DIREITA)
        return r

    def desconto(self) -> int:
        """Desconto em centavos (vazio = 0). Levanta ValueError se inválido."""
        return self.campo_desconto.centavos(vazio=0)

    def desconto_ou_zero(self) -> int:
        try:
            return self.desconto()
        except ValueError:
            return 0

    def definir_desconto(self, centavos: int) -> None:
        self.campo_desconto.definir_centavos(centavos if centavos else None)

    def atualizar(self, totais: Totais, descricao_comissao: str = "Comissão prevista") -> None:
        self._valores["pecas"].setText(formatar_reais(totais.pecas))
        self._valores["mao_de_obra"].setText(formatar_reais(totais.mao_de_obra))
        self._valores["terceiros"].setText(formatar_reais(totais.terceiros))
        self._valores["subtotal"].setText(formatar_reais(totais.subtotal))
        self._valores["total"].setText(formatar_reais(totais.total))
        self._valores["comissao"].setText(formatar_reais(totais.comissao))
        self._comissao_texto.setText(descricao_comissao)
