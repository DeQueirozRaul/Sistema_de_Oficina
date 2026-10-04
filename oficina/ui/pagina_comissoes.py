"""Tela de comissões: filtro por período/mecânico e controle de pagamento."""

from datetime import date

from PySide6.QtWidgets import QComboBox, QGridLayout, QGroupBox, QHBoxLayout, QVBoxLayout

from oficina.dinheiro import formatar_percentual, formatar_reais
from oficina.periodos import formatar_data
from oficina.servicos import comissoes, mecanicos
from oficina.ui import tema
from oficina.ui.componentes import (
    CENTRO, DIREITA, Card, Pagina, SeletorPeriodo, Tabela, avisar, botao, cabecalho, celula, perguntar, rotulo,
)


class PaginaComissoes(Pagina):
    def __init__(self, janela):
        super().__init__(janela)
        self._linhas: list[comissoes.LinhaComissao] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 12)
        layout.addLayout(cabecalho(
            "Comissões",
            "Calculadas sobre os itens de mão de obra das OS finalizadas, com o percentual de cada mecânico."))

        filtros = QHBoxLayout()
        self.periodo = SeletorPeriodo(modos=("semana", "mes", "personalizado"), inicial="semana")
        self.periodo.alterado.connect(self.atualizar)
        self.mecanico = QComboBox()
        self.mecanico.setMinimumWidth(180)
        self.mecanico.currentIndexChanged.connect(self.atualizar)
        self.situacao = QComboBox()
        for texto, valor in (("Pagas e pendentes", comissoes.SITUACAO_TODAS),
                             ("Somente pendentes", comissoes.SITUACAO_PENDENTES),
                             ("Somente pagas", comissoes.SITUACAO_PAGAS)):
            self.situacao.addItem(texto, valor)
        self.situacao.currentIndexChanged.connect(self.atualizar)
        filtros.addWidget(self.periodo)
        filtros.addStretch()
        filtros.addWidget(rotulo("Mecânico:"))
        filtros.addWidget(self.mecanico)
        filtros.addWidget(self.situacao)
        layout.addLayout(filtros)

        cards = QHBoxLayout()
        self.card_mao = Card("Mão de obra com comissão")
        self.card_total = Card("Comissão do período")
        self.card_paga = Card("Já paga")
        self.card_pendente = Card("A pagar")
        for card in (self.card_mao, self.card_total, self.card_paga, self.card_pendente):
            cards.addWidget(card)
        layout.addLayout(cards)

        grupo_resumo = QGroupBox("Resumo por mecânico")
        caixa = QVBoxLayout(grupo_resumo)
        self.tabela_resumo = Tabela(["Mecânico", "OS", "Mão de obra", "Comissão", "Já paga", "A pagar"], elastica=0)
        self.tabela_resumo.itemSelectionChanged.connect(self._resumo_selecionado)
        caixa.addWidget(self.tabela_resumo)
        layout.addWidget(grupo_resumo)

        grupo = QGroupBox("OS do período")
        grade = QGridLayout(grupo)
        self.tabela = Tabela(["OS", "Data", "Mecânico", "Veículo", "Cliente", "Mão de obra", "%", "Comissão", "Situação"],
                             elastica=4, multipla=True)
        self.tabela.doubleClicked.connect(lambda _: self._abrir_os())
        self.tabela.itemSelectionChanged.connect(self._selecao_mudou)
        grade.addWidget(self.tabela, 0, 0, 1, 6)
        self.rotulo_selecao = rotulo("", "dica")
        grade.addWidget(self.rotulo_selecao, 1, 0)
        grade.setColumnStretch(1, 1)
        self.botao_pagar_selecionadas = botao("Marcar selecionadas como pagas", self._pagar_selecionadas, primario=True)
        self.botao_pagar_todas = botao("Marcar todas as pendentes como pagas", self._pagar_todas)
        self.botao_desfazer = botao("Desfazer pagamento", self._desfazer)
        self.botao_abrir = botao("Abrir OS", self._abrir_os)
        grade.addWidget(self.botao_abrir, 1, 2)
        grade.addWidget(self.botao_desfazer, 1, 3)
        grade.addWidget(self.botao_pagar_todas, 1, 4)
        grade.addWidget(self.botao_pagar_selecionadas, 1, 5)
        layout.addWidget(grupo, 1)
        layout.addWidget(rotulo("Dica: selecione várias OS segurando Ctrl (uma a uma) ou Shift (em sequência). "
                                "Clique duas vezes numa OS para abri-la.", "dica"))

    def ao_exibir(self) -> None:
        atual = self.mecanico.currentData()
        self.mecanico.blockSignals(True)
        self.mecanico.clear()
        self.mecanico.addItem("Todos", None)
        com_comissao = comissoes.mecanicos_com_comissao(self.conn)
        for m in mecanicos.listar(self.conn):
            if m.percentual_comissao == 0 and m.id not in com_comissao:
                continue  # quem não recebe comissão (0%) não precisa aparecer no filtro
            self.mecanico.addItem(m.nome if m.ativo else f"{m.nome} (inativo)", m.id)
        self.mecanico.setCurrentIndex(max(0, self.mecanico.findData(atual)))
        self.mecanico.blockSignals(False)
        self.atualizar()

    def filtrar_mecanico(self, mecanico_id: int | None) -> None:
        self.mecanico.setCurrentIndex(max(0, self.mecanico.findData(mecanico_id)))

    def mostrar_pendentes(self, mecanico_id: int | None = None) -> None:
        """Todas as comissões pendentes, desde a mais antiga até hoje."""
        self.filtrar_mecanico(mecanico_id)
        self.situacao.setCurrentIndex(self.situacao.findData(comissoes.SITUACAO_PENDENTES))
        inicio = comissoes.data_mais_antiga_pendente(self.conn, mecanico_id) or date.today()
        self.periodo.definir_personalizado(min(inicio, date.today()), date.today())

    def atualizar(self) -> None:
        inicio, fim = self.periodo.periodo()
        self._linhas = comissoes.listar(self.conn, inicio, fim, self.mecanico.currentData(), self.situacao.currentData())
        resumos = comissoes.resumir_por_mecanico(self._linhas)

        self.card_mao.definir(formatar_reais(sum(l.mao_de_obra for l in self._linhas)),
                              f"{len(self._linhas)} OS com comissão")
        self.card_total.definir(formatar_reais(sum(r.comissao for r in resumos)), self.periodo.descricao_periodo())
        self.card_paga.definir(formatar_reais(sum(r.paga for r in resumos)))
        self.card_pendente.definir(formatar_reais(sum(r.pendente for r in resumos)))

        self.tabela_resumo.definir_linhas([
            [celula(r.mecanico_nome, negrito=True), celula(r.quantidade_os, CENTRO),
             celula(formatar_reais(r.mao_de_obra), DIREITA), celula(formatar_reais(r.comissao), DIREITA, negrito=True),
             celula(formatar_reais(r.paga), DIREITA),
             celula(formatar_reais(r.pendente), DIREITA, tema.COR_PENDENTE if r.pendente else None)]
            for r in resumos
        ], [r.mecanico_id for r in resumos])
        altura = self.tabela_resumo.horizontalHeader().height() + 30 * max(1, min(len(resumos), 5)) + 4
        self.tabela_resumo.setFixedHeight(altura)

        linhas = []
        for l in self._linhas:
            if l.paga:
                situacao = celula(f"Paga em {formatar_data(l.data_pagamento)}", CENTRO, tema.COR_PAGA)
            else:
                situacao = celula("Pendente", CENTRO, tema.COR_PENDENTE)
            veiculo = " - ".join(p for p in (l.placa, l.modelo) if p)
            linhas.append([
                celula(l.numero, CENTRO, negrito=True), celula(formatar_data(l.data), CENTRO), l.mecanico_nome,
                veiculo, l.cliente_nome, celula(formatar_reais(l.mao_de_obra), DIREITA),
                celula(formatar_percentual(l.percentual), CENTRO), celula(formatar_reais(l.comissao), DIREITA, negrito=True),
                situacao,
            ])
        self.tabela.definir_linhas(linhas, self._linhas)
        self._selecao_mudou()

    def _resumo_selecionado(self) -> None:
        mecanico_id = self.tabela_resumo.dado_selecionado()
        if mecanico_id is not None and self.mecanico.currentData() is None:
            self.filtrar_mecanico(mecanico_id)

    def _selecao_mudou(self) -> None:
        selecionadas = self.tabela.dados_selecionados()
        pendentes = [l for l in selecionadas if not l.paga]
        pagas = [l for l in selecionadas if l.paga]
        self.botao_pagar_selecionadas.setEnabled(bool(pendentes))
        self.botao_desfazer.setEnabled(bool(pagas))
        self.botao_abrir.setEnabled(len(selecionadas) == 1)
        self.botao_pagar_todas.setEnabled(any(not l.paga for l in self._linhas))
        if selecionadas:
            self.rotulo_selecao.setText(f"{len(selecionadas)} OS selecionadas  •  comissão "
                                        f"{formatar_reais(sum(l.comissao for l in selecionadas))}")
        else:
            self.rotulo_selecao.setText("")

    def _confirmar_pagamento(self, linhas: list[comissoes.LinhaComissao]) -> None:
        por_mecanico: dict[str, int] = {}
        for l in linhas:
            por_mecanico[l.mecanico_nome] = por_mecanico.get(l.mecanico_nome, 0) + l.comissao
        detalhes = "\n".join(f"  • {nome}: {formatar_reais(valor)}" for nome, valor in sorted(por_mecanico.items()))
        hoje = date.today()
        if not perguntar(self, f"Marcar {len(linhas)} OS como pagas em {formatar_data(hoje)}?\n\n{detalhes}\n\n"
                               f"Total: {formatar_reais(sum(por_mecanico.values()))}",
                         titulo="Pagamento de comissão", sim="Marcar como pagas", nao="Voltar"):
            return
        alteradas = comissoes.marcar_como_pagas(self.conn, [l.os_id for l in linhas], hoje)
        self.janela.mensagem(f"{alteradas} OS marcadas com comissão paga.")
        self.atualizar()

    def _pagar_selecionadas(self) -> None:
        pendentes = [l for l in self.tabela.dados_selecionados() if not l.paga]
        if pendentes:
            self._confirmar_pagamento(pendentes)

    def _pagar_todas(self) -> None:
        pendentes = [l for l in self._linhas if not l.paga]
        if not pendentes:
            avisar(self, "Não há comissões pendentes neste filtro.")
            return
        self._confirmar_pagamento(pendentes)

    def _desfazer(self) -> None:
        pagas = [l for l in self.tabela.dados_selecionados() if l.paga]
        if not pagas:
            return
        if not perguntar(self, f"Voltar {len(pagas)} OS para \"Pendente\"?\n\n"
                               f"Total: {formatar_reais(sum(l.comissao for l in pagas))}",
                         sim="Desfazer pagamento", nao="Voltar"):
            return
        comissoes.desfazer_pagamento(self.conn, [l.os_id for l in pagas])
        self.atualizar()

    def _abrir_os(self) -> None:
        linhas = self.tabela.dados_selecionados()
        if len(linhas) == 1:
            self.janela.abrir_os(linhas[0].os_id)
