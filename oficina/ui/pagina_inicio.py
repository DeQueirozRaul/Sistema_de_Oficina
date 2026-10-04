"""Painel inicial com o resumo do período."""

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QGridLayout, QGroupBox, QHBoxLayout, QVBoxLayout

from oficina.dinheiro import formatar_reais
from oficina.modelos import STATUS_ABERTA
from oficina.periodos import formatar_data
from oficina.servicos import comissoes, ordens, painel
from oficina.ui import tema
from oficina.ui.componentes import (
    CENTRO, DIREITA, ICONE_OLHO_ABERTO, ICONE_OLHO_FECHADO, Card, Pagina, SeletorPeriodo, Tabela, botao, cabecalho,
    celula, icone, rotulo,
)

VALOR_OCULTO = "R$ ••••••"


class PaginaInicio(Pagina):
    def __init__(self, janela):
        super().__init__(janela)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 12)
        layout.setSpacing(12)
        layout.addLayout(cabecalho(
            "Painel", "Resumo das OS finalizadas no período.",
            botao("Novo orçamento", self.janela.novo_orcamento),
            botao("Nova OS", self.janela.nova_os, primario=True),
        ))

        self.periodo = SeletorPeriodo(modos=("mes", "semana", "personalizado"), inicial="mes")
        self.periodo.alterado.connect(self._atualizar)
        self._ocultar_valores = True  # por segurança, a tela sempre abre com os valores escondidos
        self.botao_valores = botao("", self._alternar_valores)
        self.botao_valores.setIconSize(QSize(18, 18))
        self.botao_valores.setMinimumWidth(165)
        linha = QHBoxLayout()
        linha.addWidget(self.periodo)
        linha.addStretch()
        linha.addWidget(self.botao_valores)
        layout.addLayout(linha)

        cards = QGridLayout()
        cards.setSpacing(12)
        self.card_faturamento = Card("Faturamento")
        self.card_mao = Card("Mão de obra")
        self.card_pecas = Card("Peças")
        self.card_os = Card("OS finalizadas")
        self.card_comissao = Card("Comissões do período")
        todos = (self.card_faturamento, self.card_mao, self.card_pecas, self.card_os, self.card_comissao)
        for coluna, card in enumerate(todos):
            cards.addWidget(card, 0, coluna)
        layout.addLayout(cards)

        tabelas = QHBoxLayout()
        tabelas.setSpacing(12)

        grupo_comissoes = QGroupBox("Comissões a pagar (todas as datas)")
        caixa = QVBoxLayout(grupo_comissoes)
        self.tabela_comissoes = Tabela(["Mecânico", "OS", "A pagar"], elastica=0)
        self.tabela_comissoes.doubleClicked.connect(lambda _: self._abrir_comissoes())
        caixa.addWidget(self.tabela_comissoes, 1)
        rodape = QHBoxLayout()
        self.total_pendente = rotulo("", "rotuloForte")
        rodape.addWidget(self.total_pendente)
        rodape.addStretch()
        rodape.addWidget(botao("Ver comissões", self._abrir_comissoes))
        caixa.addLayout(rodape)
        tabelas.addWidget(grupo_comissoes, 2)

        grupo_abertas = QGroupBox("OS em aberto")
        caixa = QVBoxLayout(grupo_abertas)
        self.tabela_abertas = Tabela(["Nº", "Data", "Placa", "Modelo", "Cliente"], elastica=4)
        self.tabela_abertas.doubleClicked.connect(lambda _: self._abrir_os(self.tabela_abertas))
        caixa.addWidget(self.tabela_abertas, 1)
        caixa.addWidget(rotulo("Clique duas vezes para abrir e finalizar.", "dica"))
        tabelas.addWidget(grupo_abertas, 3)
        layout.addLayout(tabelas, 1)

        grupo_ultimas = QGroupBox("Últimas OS")
        caixa = QVBoxLayout(grupo_ultimas)
        self.tabela_ultimas = Tabela(["Nº", "Data", "Situação", "Placa", "Modelo", "Cliente", "Mecânico", "Total"],
                                     elastica=5)
        self.tabela_ultimas.doubleClicked.connect(lambda _: self._abrir_os(self.tabela_ultimas))
        caixa.addWidget(self.tabela_ultimas, 1)
        layout.addWidget(grupo_ultimas, 1)

    def _reais(self, centavos: int) -> str:
        """Valor em R$, ou mascarado se o "olhinho" estiver fechado."""
        return VALOR_OCULTO if self._ocultar_valores else formatar_reais(centavos)

    def _alternar_valores(self) -> None:
        self._ocultar_valores = not self._ocultar_valores
        self._atualizar()

    def _atualizar_botao_valores(self) -> None:
        if self._ocultar_valores:
            self.botao_valores.setIcon(icone(ICONE_OLHO_FECHADO))
            self.botao_valores.setText(" Mostrar valores")
            self.botao_valores.setToolTip("Os valores em R$ estão escondidos. Clique para mostrar.")
        else:
            self.botao_valores.setIcon(icone(ICONE_OLHO_ABERTO))
            self.botao_valores.setText(" Ocultar valores")
            self.botao_valores.setToolTip("Esconde os valores em R$ desta tela (para não ficarem à vista).")

    def ao_exibir(self) -> None:
        """Sempre que a tela Início é aberta, os valores voltam a ficar escondidos."""
        self._ocultar_valores = True
        self._atualizar()

    def _atualizar(self) -> None:
        self._atualizar_botao_valores()
        inicio, fim = self.periodo.periodo()
        resumo = painel.resumo_periodo(self.conn, inicio, fim)
        descricao = self.periodo.descricao_periodo()
        self.card_faturamento.definir(self._reais(resumo.faturamento), f"descontos: {self._reais(resumo.descontos)}")
        self.card_mao.definir(self._reais(resumo.mao_de_obra), descricao)
        self.card_pecas.definir(self._reais(resumo.pecas), f"terceirizados: {self._reais(resumo.terceiros)}")
        self.card_os.definir(str(resumo.quantidade_os), f"ticket médio: {self._reais(resumo.ticket_medio)}")
        self.card_comissao.definir(self._reais(resumo.comissao), descricao)

        pendentes = comissoes.pendentes_por_mecanico(self.conn)
        self.tabela_comissoes.definir_linhas(
            [[celula(p.mecanico_nome, negrito=True), celula(p.quantidade_os, CENTRO),
              celula(self._reais(p.pendente), DIREITA, negrito=True)] for p in pendentes],
            [p.mecanico_id for p in pendentes])
        self.total_pendente.setText(f"Total: {self._reais(sum(p.pendente for p in pendentes))}")

        abertas = ordens.buscar(self.conn, status=STATUS_ABERTA)
        self.tabela_abertas.definir_linhas(
            [[celula(r.numero, CENTRO, negrito=True), celula(formatar_data(r.data), CENTRO), celula(r.placa, CENTRO),
              r.modelo, r.cliente_nome] for r in abertas], [r.id for r in abertas])

        ultimas = ordens.buscar(self.conn, limite=8)
        self.tabela_ultimas.definir_linhas(
            [[celula(r.numero, CENTRO, negrito=True), celula(formatar_data(r.data), CENTRO),
              celula(r.status_texto, CENTRO, tema.CORES_STATUS[r.status]), celula(r.placa, CENTRO), r.modelo,
              r.cliente_nome, r.mecanico_nome, celula(self._reais(r.total), DIREITA)] for r in ultimas],
            [r.id for r in ultimas])

    def _abrir_os(self, tabela: Tabela) -> None:
        os_id = tabela.dado_selecionado()
        if os_id is not None:
            self.janela.abrir_os(os_id)

    def _abrir_comissoes(self) -> None:
        self.janela.comissoes_do_mecanico(self.tabela_comissoes.dado_selecionado(), pendentes=True)
