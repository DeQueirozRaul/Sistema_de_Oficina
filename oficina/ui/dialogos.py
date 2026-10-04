"""Janelas de cadastro (mecânico, cliente, veículo, item salvo) e de configuração inicial."""

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QCompleter, QDialog, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QPlainTextEdit, QSpinBox, QVBoxLayout,
)
from PySide6.QtCore import Qt

from oficina import whatsapp
from oficina.modelos import TIPOS_ITEM, Cliente, ErroValidacao, Mecanico, Veiculo
from oficina.servicos import catalogo, clientes, mecanicos, numeracao
from oficina.servicos import configuracoes as cfg
from oficina.ui import logo
from oficina.ui.componentes import (
    CampoDinheiro, CampoDocumento, CampoPlaca, CampoTelefone, avisar, botao, rotulo,
)


class _DialogoBase(QDialog):
    def __init__(self, parent, titulo: str, largura: int = 420):
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.setMinimumWidth(largura)
        self.formulario = QFormLayout()
        self.formulario.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.formulario.setVerticalSpacing(10)
        self.layout_principal = QVBoxLayout(self)
        self.layout_principal.addLayout(self.formulario)
        self.layout_principal.addSpacing(8)
        botoes = QHBoxLayout()
        botoes.addStretch()
        self.botao_cancelar = botao("Cancelar", self.reject)
        botoes.addWidget(self.botao_cancelar)
        self.botao_salvar = botao("Salvar", self._salvar, primario=True)
        self.botao_salvar.setDefault(True)
        botoes.addWidget(self.botao_salvar)
        self.layout_principal.addLayout(botoes)

    def _salvar(self) -> None:
        try:
            self.salvar()
        except ErroValidacao as erro:
            avisar(self, str(erro))
            return
        self.accept()

    def salvar(self) -> None:
        raise NotImplementedError


class DialogoMecanico(_DialogoBase):
    def __init__(self, parent, conn, mecanico: Mecanico | None = None):
        super().__init__(parent, "Editar mecânico" if mecanico else "Novo mecânico")
        self.conn = conn
        self.mecanico = mecanico or Mecanico(nome="", percentual_comissao=0)
        self.nome = QLineEdit(self.mecanico.nome)
        self.percentual = QDoubleSpinBox()
        self.percentual.setRange(0, 100)
        self.percentual.setDecimals(1)
        self.percentual.setSuffix(" %")
        self.percentual.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.percentual.setMaximumWidth(120)
        self.percentual.setValue(self.mecanico.percentual_comissao)
        self.telefone = CampoTelefone()
        self.telefone.setText(self.mecanico.telefone)
        self.ativo = QCheckBox("Ativo (aparece na lista ao criar OS)")
        self.ativo.setChecked(self.mecanico.ativo)
        self.formulario.addRow("Nome:", self.nome)
        self.formulario.addRow("Comissão sobre mão de obra:", self.percentual)
        self.formulario.addRow("", rotulo("Use 0% para quem não recebe comissão (ex.: sócio da oficina).", "dica"))
        self.formulario.addRow("Telefone:", self.telefone)
        self.formulario.addRow("", self.ativo)
        if mecanico is not None:
            self.formulario.addRow("", rotulo("Uma alteração no percentual vale para as próximas OS.\n"
                                              "As OS já finalizadas mantêm o percentual da época.", "dica"))
        self.nome.setFocus()

    def salvar(self) -> None:
        self.mecanico.nome = self.nome.text()
        self.mecanico.percentual_comissao = round(self.percentual.value(), 2)
        self.mecanico.telefone = self.telefone.text()
        self.mecanico.ativo = self.ativo.isChecked()
        self.mecanico.id = mecanicos.salvar(self.conn, self.mecanico)


class DialogoCliente(_DialogoBase):
    def __init__(self, parent, conn, cliente: Cliente | None = None):
        super().__init__(parent, "Editar cliente" if cliente else "Novo cliente", 460)
        self.conn = conn
        self.cliente = cliente or Cliente(nome="")
        self.nome = QLineEdit(self.cliente.nome)
        self.documento = CampoDocumento()
        self.documento.setText(self.cliente.documento)
        self.telefone = CampoTelefone()
        self.telefone.setText(self.cliente.telefone)
        self.observacoes = QPlainTextEdit(self.cliente.observacoes)
        self.observacoes.setFixedHeight(70)
        self.formulario.addRow("Nome:", self.nome)
        self.formulario.addRow("CPF/CNPJ:", self.documento)
        self.formulario.addRow("Telefone:", self.telefone)
        self.formulario.addRow("Observações:", self.observacoes)

    def salvar(self) -> None:
        self.cliente.nome = self.nome.text()
        self.cliente.documento = self.documento.text()
        self.cliente.telefone = self.telefone.text()
        self.cliente.observacoes = self.observacoes.toPlainText()
        self.cliente.id = clientes.salvar_cliente(self.conn, self.cliente)


class DialogoVeiculo(_DialogoBase):
    def __init__(self, parent, conn, veiculo: Veiculo | None = None, cliente_id: int | None = None):
        super().__init__(parent, "Editar veículo" if veiculo else "Novo veículo")
        self.conn = conn
        self.veiculo = veiculo or Veiculo(placa="", cliente_id=cliente_id)
        self.placa = CampoPlaca()
        self.placa.setText(self.veiculo.placa)
        self.modelo = QLineEdit(self.veiculo.modelo)
        self.ano = QLineEdit(self.veiculo.ano)
        self.km = QLineEdit(self.veiculo.ultimo_km)
        self.cliente = QComboBox()
        self.cliente.setEditable(True)
        self.cliente.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.cliente.completer().setFilterMode(Qt.MatchFlag.MatchContains)
        self.cliente.completer().setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.cliente.addItem("(sem cliente)", None)
        for id_, nome in clientes.nomes_clientes(conn):
            self.cliente.addItem(nome, id_)
        self.cliente.setCurrentIndex(max(0, self.cliente.findData(self.veiculo.cliente_id)))
        self.formulario.addRow("Placa:", self.placa)
        self.formulario.addRow("Modelo:", self.modelo)
        self.formulario.addRow("Ano:", self.ano)
        self.formulario.addRow("Último KM:", self.km)
        self.formulario.addRow("Cliente:", self.cliente)

    def salvar(self) -> None:
        indice = self.cliente.findText(self.cliente.currentText(), Qt.MatchFlag.MatchExactly)
        if indice < 0:
            raise ErroValidacao("Escolha um cliente da lista (ou \"(sem cliente)\"). Para um cliente novo, cadastre-o antes.")
        self.veiculo.placa = self.placa.text()
        self.veiculo.modelo = self.modelo.text()
        self.veiculo.ano = self.ano.text()
        self.veiculo.ultimo_km = self.km.text()
        self.veiculo.cliente_id = self.cliente.itemData(indice)
        self.veiculo.id = clientes.salvar_veiculo(self.conn, self.veiculo)


class DialogoItemCatalogo(_DialogoBase):
    def __init__(self, parent, conn, item: catalogo.ItemCatalogo):
        super().__init__(parent, "Editar item salvo", 460)
        self.conn = conn
        self.item = item
        self.descricao = QLineEdit(item.descricao)
        self.tipo = QComboBox()
        for chave, nome in TIPOS_ITEM.items():
            self.tipo.addItem(nome, chave)
        self.tipo.setCurrentIndex(self.tipo.findData(item.tipo))
        self.valor = CampoDinheiro()
        self.valor.definir_centavos(item.valor_unitario)
        self.formulario.addRow("Descrição:", self.descricao)
        self.formulario.addRow("Tipo:", self.tipo)
        self.formulario.addRow("Valor sugerido (R$):", self.valor)

    def salvar(self) -> None:
        try:
            valor = self.valor.centavos()
        except ValueError:
            raise ErroValidacao("Digite um valor válido (ex.: 150 ou 150,50).") from None
        catalogo.atualizar(self.conn, self.item.id, self.descricao.text(), self.tipo.currentData(), valor)


class DialogoConfiguracaoInicial(_DialogoBase):
    """Mostrado na primeira vez que o sistema é aberto."""

    def __init__(self, parent, conn):
        super().__init__(parent, "Bem-vindo(a) ao Sistema de Oficina", 520)
        self.conn = conn
        self.botao_salvar.setText("Começar")
        self.botao_cancelar.hide()  # a numeração precisa ser confirmada antes do primeiro uso

        introducao = rotulo(
            "Antes de começar, preencha os dados da oficina. Eles aparecem na OS e no orçamento "
            "e podem ser alterados depois em Configurações (onde também dá para trocar a logo).", quebra=True)
        self.layout_principal.insertWidget(0, introducao)
        self.layout_principal.insertSpacing(1, 6)
        imagem_logo = QLabel()
        imagem_logo.setPixmap(logo.pixmap_logo(conn, 110))
        imagem_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout_principal.insertWidget(0, imagem_logo)

        self.nome = QLineEdit(cfg.obter(conn, cfg.NOME_OFICINA))
        self.nome.setPlaceholderText("Ex.: AUTO CENTER SILVA")
        self.endereco = QLineEdit(cfg.obter(conn, cfg.ENDERECO_OFICINA))
        self.endereco.setPlaceholderText("Rua, número, bairro, cidade")
        self.telefone = CampoTelefone()
        self.telefone.setText(cfg.obter(conn, cfg.TELEFONE_OFICINA))
        self.cnpj = CampoDocumento()
        self.cnpj.setText(cfg.obter(conn, cfg.CNPJ_OFICINA))
        self.cnpj.setPlaceholderText("opcional")
        self.proxima_os = QSpinBox()
        self.proximo_orcamento = QSpinBox()
        for campo, chave in ((self.proxima_os, cfg.PROXIMO_NUMERO_OS),
                             (self.proximo_orcamento, cfg.PROXIMO_NUMERO_ORCAMENTO)):
            campo.setRange(1, 99_999_999)
            campo.setGroupSeparatorShown(False)
            campo.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
            campo.setValue(numeracao.proximo_numero(conn, chave))

        dica = ("Se a oficina já emitia OS em outro sistema ou no papel, coloque o número seguinte ao da "
                "última emitida, para não repetir numeração.")
        self.formulario.addRow("Nome da oficina:", self.nome)
        self.formulario.addRow("Endereço:", self.endereco)
        self.formulario.addRow("Telefone:", self.telefone)
        self.formulario.addRow("CNPJ:", self.cnpj)
        self.formulario.addRow("Número da próxima OS:", self.proxima_os)
        self.formulario.addRow("Número do próximo orçamento:", self.proximo_orcamento)
        self.formulario.addRow("", rotulo(dica, "dica", quebra=True))
        self.formulario.addRow("", rotulo("Depois, cadastre os mecânicos e o percentual de comissão de cada um "
                                          "no menu Mecânicos.", "dica", quebra=True))

    def reject(self) -> None:
        pass  # só fecha pelo botão "Começar" (Esc e o X da janela são ignorados)

    def salvar(self) -> None:
        if not self.nome.text().strip():
            raise ErroValidacao("Informe o nome da oficina.")
        with self.conn:
            cfg.definir(self.conn, cfg.NOME_OFICINA, self.nome.text().strip())
            cfg.definir(self.conn, cfg.ENDERECO_OFICINA, self.endereco.text().strip())
            cfg.definir(self.conn, cfg.TELEFONE_OFICINA, self.telefone.text().strip())
            cfg.definir(self.conn, cfg.CNPJ_OFICINA, self.cnpj.text().strip())
            numeracao.definir_proximo_numero(self.conn, cfg.PROXIMO_NUMERO_OS, self.proxima_os.value())
            numeracao.definir_proximo_numero(self.conn, cfg.PROXIMO_NUMERO_ORCAMENTO, self.proximo_orcamento.value())
            cfg.definir(self.conn, cfg.CONFIGURACAO_INICIAL_FEITA, "1")


class DialogoWhatsApp(_DialogoBase):
    """Pede o número do WhatsApp da empresa (usado no botão "Enviar no WhatsApp")."""

    def __init__(self, parent, conn):
        super().__init__(parent, "WhatsApp da loja", 470)
        self.conn = conn
        explicacao = rotulo("Qual é o WhatsApp da loja? As notas vão para ele quando o cliente não tem celular "
                            "cadastrado (ou se as Configurações mandarem sempre para a loja). Pode ser o número da "
                            "própria empresa: o WhatsApp abre a conversa \"Você\" (mensagens para si mesmo).",
                            quebra=True)
        self.layout_principal.insertWidget(0, explicacao)
        self.numero = CampoTelefone()
        self.numero.setText(cfg.obter(conn, cfg.WHATSAPP_NUMERO))
        self.numero.setPlaceholderText("(61) 99999-0000")
        self.modo = QComboBox()
        for chave, nome in whatsapp.MODOS.items():
            self.modo.addItem(nome, chave)
        self.modo.setCurrentIndex(max(0, self.modo.findData(cfg.obter(conn, cfg.WHATSAPP_MODO))))
        self.formulario.addRow("Número com DDD:", self.numero)
        self.formulario.addRow("Abrir no:", self.modo)
        self.numero.setFocus()

    def salvar(self) -> None:
        if not whatsapp.numero_internacional(self.numero.text()):
            raise ErroValidacao("Digite o número com DDD, por exemplo (61) 99999-0000.")
        cfg.salvar(self.conn, {cfg.WHATSAPP_NUMERO: self.numero.text(), cfg.WHATSAPP_MODO: self.modo.currentData()})
