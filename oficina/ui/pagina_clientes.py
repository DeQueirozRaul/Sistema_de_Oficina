"""Cadastro de clientes e veículos."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGroupBox, QHBoxLayout, QSplitter, QTabWidget, QVBoxLayout, QWidget

from oficina.servicos import clientes
from oficina.ui.componentes import CENTRO, Pagina, Tabela, botao, cabecalho, campo_busca, celula, perguntar, rotulo
from oficina.ui.dialogos import DialogoCliente, DialogoVeiculo


class PaginaClientes(Pagina):
    def __init__(self, janela):
        super().__init__(janela)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 12)
        layout.addLayout(cabecalho("Clientes e veículos",
                                   "Os cadastros são criados automaticamente ao salvar uma OS. Aqui você pode corrigir ou completar."))
        self.abas = QTabWidget()
        self.abas.addTab(self._montar_aba_clientes(), "Clientes")
        self.abas.addTab(self._montar_aba_veiculos(), "Veículos")
        self.abas.currentChanged.connect(lambda _: self.ao_exibir())
        layout.addWidget(self.abas, 1)

    # ------------------------------------------------------------ clientes

    def _montar_aba_clientes(self) -> QWidget:
        aba = QWidget()
        layout = QVBoxLayout(aba)
        layout.setContentsMargins(0, 10, 0, 0)
        self.busca_clientes = campo_busca("Buscar por nome, CPF/CNPJ ou telefone", self._atualizar_clientes)
        layout.addWidget(self.busca_clientes)

        divisor = QSplitter(Qt.Orientation.Horizontal)
        esquerda = QWidget()
        caixa = QVBoxLayout(esquerda)
        caixa.setContentsMargins(0, 0, 6, 0)
        self.tabela_clientes = Tabela(["Nome", "CPF/CNPJ", "Telefone", "Veículos"], elastica=0)
        self.tabela_clientes.itemSelectionChanged.connect(self._cliente_selecionado)
        self.tabela_clientes.doubleClicked.connect(lambda _: self._editar_cliente())
        caixa.addWidget(self.tabela_clientes, 1)
        botoes = QHBoxLayout()
        botoes.addStretch()
        self.botao_excluir_cliente = botao("Excluir", self._excluir_cliente, perigo=True)
        self.botao_editar_cliente = botao("Editar", self._editar_cliente)
        botoes.addWidget(self.botao_excluir_cliente)
        botoes.addWidget(self.botao_editar_cliente)
        botoes.addWidget(botao("Novo cliente", self._novo_cliente, primario=True))
        caixa.addLayout(botoes)

        direita = QGroupBox("Veículos do cliente")
        caixa = QVBoxLayout(direita)
        self.tabela_veiculos_cliente = Tabela(["Placa", "Modelo", "Ano", "Último KM"], elastica=1)
        self.tabela_veiculos_cliente.doubleClicked.connect(lambda _: self._editar_veiculo(self.tabela_veiculos_cliente))
        self.tabela_veiculos_cliente.itemSelectionChanged.connect(self._botoes)
        caixa.addWidget(self.tabela_veiculos_cliente, 1)
        botoes = QHBoxLayout()
        self.botao_os_veiculo_cliente = botao("Ver OS", lambda: self._ver_os(self.tabela_veiculos_cliente))
        self.botao_editar_veiculo_cliente = botao("Editar", lambda: self._editar_veiculo(self.tabela_veiculos_cliente))
        self.botao_add_veiculo = botao("Adicionar veículo", self._adicionar_veiculo_ao_cliente)
        botoes.addStretch()
        botoes.addWidget(self.botao_os_veiculo_cliente)
        botoes.addWidget(self.botao_editar_veiculo_cliente)
        botoes.addWidget(self.botao_add_veiculo)
        caixa.addLayout(botoes)

        divisor.addWidget(esquerda)
        divisor.addWidget(direita)
        divisor.setStretchFactor(0, 3)
        divisor.setStretchFactor(1, 2)
        layout.addWidget(divisor, 1)
        return aba

    def _atualizar_clientes(self) -> None:
        selecionado = self.tabela_clientes.dado_selecionado()
        lista = clientes.listar_clientes(self.conn, self.busca_clientes.text())
        self.tabela_clientes.definir_linhas(
            [[c.nome, c.documento, c.telefone, celula(qtd, CENTRO)] for c, qtd in lista], [c.id for c, _ in lista])
        linha_selecionada = 0
        for linha in range(self.tabela_clientes.rowCount()):
            if self.tabela_clientes.dado_da_linha(linha) == selecionado:
                linha_selecionada = linha
        if self.tabela_clientes.rowCount():
            self.tabela_clientes.selectRow(linha_selecionada)
        self._cliente_selecionado()

    def _cliente_selecionado(self) -> None:
        cliente_id = self.tabela_clientes.dado_selecionado()
        veiculos = clientes.listar_veiculos(self.conn, cliente_id=cliente_id) if cliente_id else []
        self.tabela_veiculos_cliente.definir_linhas(
            [[celula(v.placa, CENTRO, negrito=True), v.modelo, celula(v.ano, CENTRO), celula(v.ultimo_km, CENTRO)]
             for v in veiculos], [v.id for v in veiculos])
        self._botoes()

    def _botoes(self) -> None:
        tem_cliente = self.tabela_clientes.dado_selecionado() is not None
        tem_veiculo = self.tabela_veiculos_cliente.dado_selecionado() is not None
        self.botao_editar_cliente.setEnabled(tem_cliente)
        self.botao_excluir_cliente.setEnabled(tem_cliente)
        self.botao_add_veiculo.setEnabled(tem_cliente)
        self.botao_editar_veiculo_cliente.setEnabled(tem_veiculo)
        self.botao_os_veiculo_cliente.setEnabled(tem_veiculo)

    def _novo_cliente(self) -> None:
        dialogo = DialogoCliente(self, self.conn)
        if dialogo.exec():
            self.busca_clientes.clear()
            self._atualizar_clientes()

    def _editar_cliente(self) -> None:
        cliente_id = self.tabela_clientes.dado_selecionado()
        if cliente_id is not None and DialogoCliente(self, self.conn, clientes.obter_cliente(self.conn, cliente_id)).exec():
            self._atualizar_clientes()

    def _excluir_cliente(self) -> None:
        cliente_id = self.tabela_clientes.dado_selecionado()
        if cliente_id is None:
            return
        cliente = clientes.obter_cliente(self.conn, cliente_id)
        if perguntar(self, f"Excluir o cadastro de {cliente.nome}?\n\nAs OS já feitas continuam com os dados dele, "
                           "e os veículos ficam sem cliente.", sim="Excluir", nao="Voltar"):
            clientes.excluir_cliente(self.conn, cliente_id)
            self._atualizar_clientes()

    def _adicionar_veiculo_ao_cliente(self) -> None:
        cliente_id = self.tabela_clientes.dado_selecionado()
        if cliente_id is not None and DialogoVeiculo(self, self.conn, cliente_id=cliente_id).exec():
            self._atualizar_clientes()

    # ------------------------------------------------------------ veículos

    def _montar_aba_veiculos(self) -> QWidget:
        aba = QWidget()
        layout = QVBoxLayout(aba)
        layout.setContentsMargins(0, 10, 0, 0)
        self.busca_veiculos = campo_busca("Buscar por placa, modelo ou cliente", self._atualizar_veiculos)
        layout.addWidget(self.busca_veiculos)
        self.tabela_veiculos = Tabela(["Placa", "Modelo", "Ano", "Último KM", "Cliente"], elastica=4)
        self.tabela_veiculos.doubleClicked.connect(lambda _: self._editar_veiculo(self.tabela_veiculos))
        self.tabela_veiculos.itemSelectionChanged.connect(self._botoes_veiculos)
        layout.addWidget(self.tabela_veiculos, 1)
        botoes = QHBoxLayout()
        botoes.addWidget(rotulo("Veículos de orçamentos aparecem sem cliente até virarem OS.", "dica"))
        botoes.addStretch()
        self.botao_excluir_veiculo = botao("Excluir", self._excluir_veiculo, perigo=True)
        self.botao_os_veiculo = botao("Ver OS", lambda: self._ver_os(self.tabela_veiculos))
        self.botao_editar_veiculo = botao("Editar", lambda: self._editar_veiculo(self.tabela_veiculos))
        for b in (self.botao_excluir_veiculo, self.botao_os_veiculo, self.botao_editar_veiculo):
            botoes.addWidget(b)
        botoes.addWidget(botao("Novo veículo", self._novo_veiculo, primario=True))
        layout.addLayout(botoes)
        return aba

    def _atualizar_veiculos(self) -> None:
        veiculos = clientes.listar_veiculos(self.conn, busca=self.busca_veiculos.text())
        self.tabela_veiculos.definir_linhas(
            [[celula(v.placa, CENTRO, negrito=True), v.modelo, celula(v.ano, CENTRO), celula(v.ultimo_km, CENTRO),
              v.cliente_nome or "—"] for v in veiculos], [v.id for v in veiculos])
        self._botoes_veiculos()

    def _botoes_veiculos(self) -> None:
        tem = self.tabela_veiculos.dado_selecionado() is not None
        for b in (self.botao_excluir_veiculo, self.botao_os_veiculo, self.botao_editar_veiculo):
            b.setEnabled(tem)

    def _novo_veiculo(self) -> None:
        if DialogoVeiculo(self, self.conn).exec():
            self._atualizar_veiculos()

    def _editar_veiculo(self, tabela: Tabela) -> None:
        veiculo_id = tabela.dado_selecionado()
        if veiculo_id is not None and DialogoVeiculo(self, self.conn, clientes.obter_veiculo(self.conn, veiculo_id)).exec():
            self.ao_exibir()

    def _excluir_veiculo(self) -> None:
        veiculo_id = self.tabela_veiculos.dado_selecionado()
        if veiculo_id is None:
            return
        veiculo = clientes.obter_veiculo(self.conn, veiculo_id)
        if perguntar(self, f"Excluir o veículo {veiculo.placa}?\n\nAs OS já feitas continuam com os dados dele.",
                     sim="Excluir", nao="Voltar"):
            clientes.excluir_veiculo(self.conn, veiculo_id)
            self._atualizar_veiculos()

    def _ver_os(self, tabela: Tabela) -> None:
        veiculo_id = tabela.dado_selecionado()
        if veiculo_id is not None:
            self.janela.historico_da_placa(clientes.obter_veiculo(self.conn, veiculo_id).placa)

    # ------------------------------------------------------------

    def ao_exibir(self) -> None:
        if self.abas.currentIndex() == 0:
            self._atualizar_clientes()
        else:
            self._atualizar_veiculos()
