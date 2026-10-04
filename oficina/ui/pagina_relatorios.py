"""Tela de Relatórios: gráficos do período e exportação para Excel ou CSV."""

from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog, QGroupBox, QHBoxLayout, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget,
)

from oficina import caminhos
from oficina.dinheiro import formatar_compacto, formatar_quantidade, formatar_reais
from oficina.modelos import TIPO_MAO_DE_OBRA, TIPO_PECA, TIPO_TERCEIROS, TIPOS_ITEM
from oficina.servicos import painel, relatorios
from oficina.ui import tema
from oficina.ui.componentes import (
    CENTRO, DIREITA, Card, Pagina, SeletorPeriodo, Tabela, abrir_arquivo, botao, cabecalho, celula, com_rolagem,
    mostrar_erro, perguntar, rotulo,
)
from oficina.ui.graficos import (
    COR_MAO_DE_OBRA, COR_NEUTRA, COR_PECA, COR_TERCEIROS, CORES_TIPO, Barra, GraficoBarras, GraficoColunas, Serie,
)

SERIES_TIPO = [Serie("Mão de obra", COR_MAO_DE_OBRA), Serie("Peças", COR_PECA), Serie("Terceirizados", COR_TERCEIROS)]
TITULOS_FATURAMENTO = {relatorios.DIA: "Faturamento por dia", relatorios.SEMANA: "Faturamento por semana",
                       relatorios.MES: "Faturamento por mês"}
ORDEM_TIPOS = (TIPO_MAO_DE_OBRA, TIPO_PECA, TIPO_TERCEIROS)
NOMES_TIPO_LEGENDA = {TIPO_MAO_DE_OBRA: "Mão de obra", TIPO_PECA: "Peças", TIPO_TERCEIROS: "Terceirizados"}


def _quadrado(cor: str) -> str:
    """Quadradinho colorido para as dicas (a cor identifica a série; o texto continua na cor normal)."""
    return f"<span style='color:{cor}'>■</span>"


class Bloco(QGroupBox):
    """Um gráfico com o botão "Ver tabela", que mostra os mesmos números em forma de tabela."""

    def __init__(self, titulo: str, dica: str, grafico, colunas: list[str], elastica: int = 0):
        super().__init__(titulo)
        caixa = QVBoxLayout(self)
        topo = QHBoxLayout()
        self.dica = rotulo(dica, "dica", quebra=True)
        topo.addWidget(self.dica, 1)
        self.botao_alternar = botao("Ver tabela", self.alternar, pequeno=True,
                                    dica="Mostra os mesmos números em forma de tabela")
        topo.addWidget(self.botao_alternar)
        caixa.addLayout(topo)
        self.grafico = grafico
        self.grafico.setAccessibleName(titulo)
        self.tabela = Tabela(colunas, elastica=elastica)
        # A altura do bloco é a do gráfico; a tabela ocupa o mesmo espaço (com rolagem, se precisar).
        self.tabela.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.pilha = QStackedWidget()
        self.pilha.addWidget(grafico)
        self.pilha.addWidget(self.tabela)
        caixa.addWidget(self.pilha, 1)

    def mostrando_tabela(self) -> bool:
        return self.pilha.currentWidget() is self.tabela

    def alternar(self) -> None:
        tabela = not self.mostrando_tabela()
        self.pilha.setCurrentWidget(self.tabela if tabela else self.grafico)
        self.botao_alternar.setText("Ver gráfico" if tabela else "Ver tabela")


class PaginaRelatorios(Pagina):
    def __init__(self, janela):
        super().__init__(janela)
        conteudo = QWidget()
        conteudo.setObjectName("pagina")
        layout = QVBoxLayout(conteudo)
        layout.setContentsMargins(20, 16, 20, 12)
        layout.setSpacing(12)
        layout.addLayout(cabecalho(
            "Relatórios", "Como a oficina está indo no período (somente OS finalizadas).",
            botao("Exportar CSV", self._exportar_csv, dica="Lista das OS do período, para abrir no Excel"),
            botao("Exportar Excel", self._exportar_excel, primario=True,
                  dica="Planilha com resumo, faturamento, itens, mecânicos e a lista de OS"),
        ))

        self.periodo = SeletorPeriodo(modos=("12meses", "ano", "mes", "personalizado"), inicial="12meses")
        self.periodo.alterado.connect(self.atualizar)
        linha = QHBoxLayout()
        linha.addWidget(self.periodo)
        linha.addStretch()
        layout.addLayout(linha)

        cards = QHBoxLayout()
        cards.setSpacing(12)
        self.card_faturamento = Card("Faturamento")
        self.card_os = Card("OS finalizadas")
        self.card_mao = Card("Mão de obra")
        self.card_clientes = Card("Clientes atendidos")
        self.card_conversao = Card("Orçamentos aprovados")
        for card in (self.card_faturamento, self.card_os, self.card_mao, self.card_clientes, self.card_conversao):
            cards.addWidget(card)
        layout.addLayout(cards)

        self.bloco_faturamento = Bloco(
            "Faturamento por mês",
            "Soma dos itens, antes dos descontos. Passe o mouse sobre uma coluna para ver os valores.",
            GraficoColunas(), ["Período", "OS", "Mão de obra", "Peças", "Terceirizados", "Descontos", "Total",
                               "Ticket médio"])
        layout.addWidget(self.bloco_faturamento)

        lado_a_lado = QHBoxLayout()
        lado_a_lado.setSpacing(12)
        self.bloco_itens = Bloco("Itens que mais faturaram", "Os 10 itens com maior valor somado no período.",
                                 GraficoBarras(), ["Descrição", "Tipo", "Qtd.", "Nº de OS", "Total"])
        self.bloco_mecanicos = Bloco("Mão de obra por mecânico", "Passe o mouse para ver OS, ticket médio e comissão.",
                                     GraficoBarras(), ["Mecânico", "OS", "Mão de obra", "Ticket médio", "Comissão"])
        self.bloco_dias = Bloco("Movimento por dia da semana", "Quantidade de OS finalizadas em cada dia.",
                                GraficoBarras(), ["Dia", "OS", "Faturamento", "Ticket médio"])
        direita = QVBoxLayout()
        direita.setSpacing(12)
        direita.addWidget(self.bloco_mecanicos)
        direita.addWidget(self.bloco_dias)
        direita.addStretch()
        lado_a_lado.addWidget(self.bloco_itens, 3)
        lado_a_lado.addLayout(direita, 2)
        layout.addLayout(lado_a_lado)
        layout.addStretch()

        externo = QVBoxLayout(self)
        externo.setContentsMargins(0, 0, 0, 0)
        externo.addWidget(com_rolagem(conteudo), 1)

    def ao_exibir(self) -> None:
        self.atualizar()

    # ------------------------------------------------------------ dados

    def atualizar(self) -> None:
        inicio, fim = self.periodo.periodo()
        self._atualizar_cards(inicio, fim)
        self._atualizar_faturamento(inicio, fim)
        self._atualizar_itens(inicio, fim)
        self._atualizar_mecanicos(inicio, fim)
        self._atualizar_dias(inicio, fim)

    def _atualizar_cards(self, inicio, fim) -> None:
        resumo = painel.resumo_periodo(self.conn, inicio, fim)
        self.card_faturamento.definir(formatar_reais(resumo.faturamento),
                                      f"descontos: {formatar_reais(resumo.descontos)}")
        self.card_os.definir(str(resumo.quantidade_os), f"ticket médio: {formatar_reais(resumo.ticket_medio)}")
        itens = resumo.mao_de_obra + resumo.pecas + resumo.terceiros
        parte = f"{round(resumo.mao_de_obra / itens * 100)}% do valor dos itens" if itens else "—"
        self.card_mao.definir(formatar_reais(resumo.mao_de_obra), parte)

        clientes = relatorios.clientes_atendidos(self.conn, inicio, fim)
        self.card_clientes.definir(str(clientes.atendidos), f"{clientes.voltaram} voltaram mais de uma vez")
        conversao = relatorios.conversao_orcamentos(self.conn, inicio, fim)
        if conversao.taxa is None:
            self.card_conversao.definir("—", "nenhum orçamento no período")
        else:
            self.card_conversao.definir(f"{round(conversao.taxa * 100)}%",
                                        f"{conversao.aprovados} de {conversao.orcamentos} viraram OS")

    def _atualizar_faturamento(self, inicio, fim) -> None:
        agrupamento = relatorios.agrupamento_para(inicio, fim)
        fatias = relatorios.faturamento_por_periodo(self.conn, inicio, fim, agrupamento)
        self.bloco_faturamento.setTitle(TITULOS_FATURAMENTO[agrupamento])
        dicas = []
        for f in fatias:
            linhas = [f"<b>{f.titulo}</b>", f"{f.quantidade_os} OS finalizada{'s' if f.quantidade_os != 1 else ''}"]
            for serie, valor in zip(SERIES_TIPO, (f.mao_de_obra, f.pecas, f.terceiros), strict=True):
                linhas.append(f"{_quadrado(serie.cor)} {serie.nome}: {formatar_reais(valor)}")
            if f.descontos:
                linhas.append(f"Descontos: −{formatar_reais(f.descontos)}")
            linhas.append(f"<b>Total: {formatar_reais(f.total)}</b>")
            if f.quantidade_os:
                linhas.append(f"Ticket médio: {formatar_reais(f.ticket_medio)}")
            dicas.append("<br>".join(linhas))
        self.bloco_faturamento.grafico.definir(
            [f.rotulo for f in fatias], SERIES_TIPO, [[f.mao_de_obra, f.pecas, f.terceiros] for f in fatias], dicas,
            [formatar_compacto(f.bruto) for f in fatias])
        self.bloco_faturamento.tabela.definir_linhas([
            [f.titulo, celula(f.quantidade_os, CENTRO), celula(formatar_reais(f.mao_de_obra), DIREITA),
             celula(formatar_reais(f.pecas), DIREITA), celula(formatar_reais(f.terceiros), DIREITA),
             celula(formatar_reais(f.descontos), DIREITA), celula(formatar_reais(f.total), DIREITA, negrito=True),
             celula(formatar_reais(f.ticket_medio), DIREITA)]
            for f in fatias])

    def _atualizar_itens(self, inicio, fim) -> None:
        itens = relatorios.itens_mais_vendidos(self.conn, inicio, fim, limite=10)
        tipos = [t for t in ORDEM_TIPOS if any(i.tipo == t for i in itens)]
        self.bloco_itens.grafico.definir(
            [Barra(i.descricao, i.total, CORES_TIPO[i.tipo], formatar_reais(i.total),
                   f"<b>{i.descricao}</b><br>{_quadrado(CORES_TIPO[i.tipo])} {TIPOS_ITEM[i.tipo]}"
                   f"<br>Quantidade: {formatar_quantidade(i.quantidade)} em {i.vezes} OS"
                   f"<br>Total: {formatar_reais(i.total)}")
             for i in itens],
            [Serie(NOMES_TIPO_LEGENDA[t], CORES_TIPO[t]) for t in tipos])
        self.bloco_itens.tabela.definir_linhas([
            [i.descricao, celula(TIPOS_ITEM[i.tipo], CENTRO, tema.CORES_TIPO[i.tipo]),
             celula(formatar_quantidade(i.quantidade), CENTRO), celula(i.vezes, CENTRO),
             celula(formatar_reais(i.total), DIREITA, negrito=True)]
            for i in itens])

    def _atualizar_mecanicos(self, inicio, fim) -> None:
        desempenho = relatorios.desempenho_mecanicos(self.conn, inicio, fim)
        self.bloco_mecanicos.grafico.definir([
            Barra(m.nome, m.mao_de_obra, COR_MAO_DE_OBRA, formatar_reais(m.mao_de_obra),
                  f"<b>{m.nome}</b><br>{m.quantidade_os} OS · ticket médio {formatar_reais(m.ticket_medio)}"
                  f"<br>{_quadrado(COR_MAO_DE_OBRA)} Mão de obra: {formatar_reais(m.mao_de_obra)}"
                  f"<br>Comissão: {formatar_reais(m.comissao)}")
            for m in desempenho])
        self.bloco_mecanicos.tabela.definir_linhas([
            [celula(m.nome, negrito=True), celula(m.quantidade_os, CENTRO),
             celula(formatar_reais(m.mao_de_obra), DIREITA), celula(formatar_reais(m.ticket_medio), DIREITA),
             celula(formatar_reais(m.comissao), DIREITA)]
            for m in desempenho])

    def _atualizar_dias(self, inicio, fim) -> None:
        dias = relatorios.movimento_por_dia_da_semana(self.conn, inicio, fim)
        ticket = lambda d: d.faturamento // d.quantidade_os if d.quantidade_os else 0  # noqa: E731
        self.bloco_dias.grafico.definir([
            Barra(d.nome, d.quantidade_os, COR_NEUTRA, f"{d.quantidade_os} OS",
                  f"<b>{d.nome}</b><br>{d.quantidade_os} OS<br>Faturamento: {formatar_reais(d.faturamento)}"
                  f"<br>Ticket médio: {formatar_reais(ticket(d))}")
            for d in dias])
        self.bloco_dias.tabela.definir_linhas([
            [celula(d.nome, negrito=True), celula(d.quantidade_os, CENTRO),
             celula(formatar_reais(d.faturamento), DIREITA), celula(formatar_reais(ticket(d)), DIREITA)]
            for d in dias])

    # ------------------------------------------------------------ exportação

    def _nome_padrao(self, extensao: str) -> str:
        inicio, fim = self.periodo.periodo()
        return str(caminhos.pasta_documentos() / f"relatorio_{inicio:%Y-%m-%d}_a_{fim:%Y-%m-%d}.{extensao}")

    def _exportar(self, extensao: str, filtro: str, funcao) -> None:
        caminho, _ = QFileDialog.getSaveFileName(self, "Salvar relatório", self._nome_padrao(extensao), filtro)
        if not caminho:
            return
        if not caminho.lower().endswith(f".{extensao}"):
            caminho += f".{extensao}"
        inicio, fim = self.periodo.periodo()
        try:
            funcao(self.conn, inicio, fim, Path(caminho))
        except OSError as erro:
            mostrar_erro(self, f"Não foi possível salvar o arquivo:\n{erro}\n\n"
                               "Se ele estiver aberto no Excel, feche-o e tente de novo.")
            return
        self.janela.mensagem(f"Relatório salvo em {caminho}")
        if perguntar(self, f"Relatório salvo em:\n{caminho}\n\nDeseja abrir agora?", titulo="Relatório salvo",
                     sim="Abrir", nao="Agora não"):
            abrir_arquivo(caminho)

    def _exportar_excel(self) -> None:
        self._exportar("xlsx", "Planilha do Excel (*.xlsx)", relatorios.exportar_excel)

    def _exportar_csv(self) -> None:
        self._exportar("csv", "CSV (*.csv)", relatorios.exportar_csv)
