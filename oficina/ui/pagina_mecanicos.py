"""Cadastro de mecânicos e percentual de comissão."""

from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout

from oficina.dinheiro import formatar_percentual
from oficina.modelos import ErroValidacao
from oficina.servicos import mecanicos
from oficina.ui import tema
from oficina.ui.componentes import CENTRO, Pagina, Tabela, avisar, botao, cabecalho, celula, perguntar, rotulo
from oficina.ui.dialogos import DialogoMecanico


class PaginaMecanicos(Pagina):
    def __init__(self, janela):
        super().__init__(janela)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 12)
        layout.addLayout(cabecalho("Mecânicos", "Cada mecânico tem seu percentual de comissão sobre a mão de obra."))
        aviso = rotulo("Ao alterar o percentual, a mudança vale para as próximas OS. As OS já finalizadas continuam "
                       "com o percentual que estava valendo quando foram finalizadas.", "informacao", quebra=True)
        layout.addWidget(aviso)

        self.tabela = Tabela(["Nome", "Comissão", "Telefone", "Situação"], elastica=0)
        self.tabela.doubleClicked.connect(lambda _: self._editar())
        self.tabela.itemSelectionChanged.connect(self._botoes)
        layout.addWidget(self.tabela, 1)

        botoes = QHBoxLayout()
        botoes.addStretch()
        self.botao_excluir = botao("Excluir", self._excluir, perigo=True)
        self.botao_ativo = botao("Desativar", self._alternar_ativo)
        self.botao_comissoes = botao("Ver comissões", self._ver_comissoes)
        self.botao_editar = botao("Editar", self._editar)
        for b in (self.botao_excluir, self.botao_ativo, self.botao_comissoes, self.botao_editar):
            botoes.addWidget(b)
        botoes.addWidget(botao("Novo mecânico", self._novo, primario=True))
        layout.addLayout(botoes)

    def ao_exibir(self) -> None:
        lista = mecanicos.listar(self.conn)
        self.tabela.definir_linhas([
            [celula(m.nome, negrito=True),
             celula(formatar_percentual(m.percentual_comissao) if m.percentual_comissao else "Sem comissão", CENTRO),
             celula(m.telefone, CENTRO),
             celula("Ativo", CENTRO, tema.COR_PAGA) if m.ativo else celula("Inativo", CENTRO, ("#64748B", "#F1F5F9"))]
            for m in lista
        ], lista)
        self._botoes()

    def _botoes(self) -> None:
        m = self.tabela.dado_selecionado()
        for b in (self.botao_excluir, self.botao_ativo, self.botao_comissoes, self.botao_editar):
            b.setEnabled(m is not None)
        self.botao_ativo.setText("Reativar" if m is not None and not m.ativo else "Desativar")

    def _novo(self) -> None:
        if DialogoMecanico(self, self.conn).exec():
            self.ao_exibir()

    def _editar(self) -> None:
        m = self.tabela.dado_selecionado()
        if m is not None and DialogoMecanico(self, self.conn, mecanicos.obter(self.conn, m.id)).exec():
            self.ao_exibir()

    def _alternar_ativo(self) -> None:
        m = self.tabela.dado_selecionado()
        if m is None:
            return
        if m.ativo and not perguntar(self, f"Desativar {m.nome}?\n\nEle deixa de aparecer ao criar novas OS, "
                                           "mas o histórico e as comissões continuam guardados.",
                                     sim="Desativar", nao="Voltar"):
            return
        mecanicos.definir_ativo(self.conn, m.id, not m.ativo)
        self.ao_exibir()

    def _excluir(self) -> None:
        m = self.tabela.dado_selecionado()
        if m is None or not perguntar(self, f"Excluir o mecânico {m.nome}?", sim="Excluir", nao="Voltar"):
            return
        try:
            mecanicos.excluir(self.conn, m.id)
        except ErroValidacao as erro:
            avisar(self, str(erro))
            return
        self.ao_exibir()

    def _ver_comissoes(self) -> None:
        m = self.tabela.dado_selecionado()
        if m is not None:
            self.janela.comissoes_do_mecanico(m.id)
