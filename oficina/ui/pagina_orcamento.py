"""Tela de criação/edição de orçamento."""

from datetime import date

from PySide6.QtCore import QStringListModel, Qt
from PySide6.QtWidgets import QCompleter, QGridLayout, QGroupBox, QHBoxLayout, QLineEdit, QPlainTextEdit, QVBoxLayout, QWidget

from oficina.modelos import ErroValidacao, Orcamento, calcular_totais
from oficina.servicos import clientes, orcamentos, ordens
from oficina.ui import acoes
from oficina.ui.componentes import (
    CampoData, CampoPlaca, Pagina, Selo, abrir_arquivo, avisar, botao, botao_whatsapp, cabecalho, com_rolagem,
    escolher, mostrar_erro, perguntar, rotulo,
)
from oficina.ui.editor_itens import EditorItens, PainelTotais


class PaginaOrcamento(Pagina):
    def __init__(self, janela):
        super().__init__(janela)
        self._orcamento: Orcamento | None = None
        self._modificado = False
        self._carregando = False

        conteudo = QWidget()
        conteudo.setObjectName("pagina")
        layout = QVBoxLayout(conteudo)
        layout.setContentsMargins(20, 16, 20, 8)
        self.selo = Selo()
        layout.addLayout(cabecalho("Orçamento", "O orçamento não gera comissão. Quando aprovado, transforme-o em OS.",
                                   self.selo, botao("Novo orçamento", lambda: self.novo())))

        grupo = QGroupBox("Dados do orçamento")
        grade = QGridLayout(grupo)
        self.numero = QLineEdit()
        self.numero.setObjectName("numeroDocumento")
        self.numero.setReadOnly(True)
        self.numero.setMaximumWidth(110)
        self.data = CampoData()
        self.placa = CampoPlaca()
        self._placas = QStringListModel(self)
        completar = QCompleter(self._placas, self)
        completar.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.placa.setCompleter(completar)
        completar.activated[str].connect(lambda _: self._buscar_placa())
        self.modelo = QLineEdit()
        for coluna, (texto, campo) in enumerate((("Orçamento Nº", self.numero), ("Data", self.data),
                                                 ("Placa", self.placa), ("Carro (modelo)", self.modelo))):
            grade.addWidget(rotulo(texto), 0, coluna * 2)
            grade.addWidget(campo, 0, coluna * 2 + 1)
        grade.setColumnStretch(7, 1)
        layout.addWidget(grupo)

        grupo_itens = QGroupBox("Peças e serviços")
        caixa = QVBoxLayout(grupo_itens)
        self.editor = EditorItens(self.conn)
        caixa.addWidget(self.editor)

        self.totais = PainelTotais(mostrar_comissao=False)
        grupo_obs = QGroupBox("Observações / validade")
        caixa = QVBoxLayout(grupo_obs)
        self.observacoes = QPlainTextEdit()
        self.observacoes.setPlaceholderText("Ex.: Orçamento válido por 7 dias.")
        self.observacoes.setMinimumHeight(60)
        caixa.addWidget(self.observacoes)
        direita = QVBoxLayout()
        direita.addWidget(self.totais)
        direita.addWidget(grupo_obs, 1)

        linha = QHBoxLayout()
        linha.addWidget(grupo_itens, 1)
        linha.addLayout(direita)
        layout.addLayout(linha, 1)

        self.botao_abrir_pdf = botao("Abrir PDF", self._abrir_pdf)
        self.botao_whatsapp = botao_whatsapp(self._enviar_whatsapp)
        self.botao_os = botao("Transformar em OS", self._transformar_em_os,
                              dica="Cria uma OS com os itens deste orçamento (use quando o cliente aprovar).")
        self.botao_gerar = botao("Gerar orçamento (PDF)", self._gerar, primario=True)
        barra = QHBoxLayout()
        barra.setContentsMargins(20, 8, 20, 12)
        barra.addWidget(self.botao_abrir_pdf)
        barra.addWidget(self.botao_whatsapp)
        barra.addStretch()
        barra.addWidget(self.botao_os)
        barra.addWidget(self.botao_gerar)

        externo = QVBoxLayout(self)
        externo.setContentsMargins(0, 0, 0, 0)
        externo.setSpacing(0)
        externo.addWidget(com_rolagem(conteudo), 1)
        externo.addLayout(barra)

        for campo in (self.placa, self.modelo):
            campo.textEdited.connect(lambda _: self._marcar_modificado())
        self.placa.editingFinished.connect(self._buscar_placa)
        self.observacoes.textChanged.connect(self._marcar_modificado)
        self.data.dateChanged.connect(lambda _: self._marcar_modificado())
        self.editor.alterado.connect(self._itens_mudaram)
        self.totais.desconto_alterado.connect(self._itens_mudaram)
        self._limpar()

    @property
    def modificado(self) -> bool:
        return self._modificado

    def ao_exibir(self) -> None:
        self._placas.setStringList(clientes.placas_cadastradas(self.conn))
        self.editor.atualizar_sugestoes()

    def pode_descartar(self) -> bool:
        if not self._modificado:
            return True
        return perguntar(self, "Existem alterações não salvas neste orçamento.\nDeseja descartá-las?",
                         titulo="Alterações não salvas", sim="Descartar alterações", nao="Voltar")

    def novo(self, confirmar: bool = True) -> None:
        if confirmar and not self.pode_descartar():
            return
        self._limpar()
        self.placa.setFocus()

    def carregar(self, orcamento_id: int) -> bool:
        if not self.pode_descartar():
            return False
        orcamento = orcamentos.carregar(self.conn, orcamento_id)
        if orcamento is None:
            return False
        self._carregando = True
        self._orcamento = orcamento
        self.numero.setText(str(orcamento.numero))
        self.data.definir(orcamento.data)
        self.placa.setText(orcamento.placa)
        self.modelo.setText(orcamento.modelo)
        self.observacoes.setPlainText(orcamento.observacoes)
        self.editor.definir_itens(orcamento.itens)
        self.totais.definir_desconto(orcamento.desconto)
        self._carregando = False
        self._modificado = False
        self._atualizar_estado()
        return True

    # ------------------------------------------------------------ interno

    def _limpar(self) -> None:
        self._carregando = True
        self._orcamento = None
        self.numero.setText(str(orcamentos.proximo_numero(self.conn)))
        self.data.definir(date.today())
        self.placa.setText("")
        self.modelo.setText("")
        self.observacoes.setPlainText("")
        self.editor.limpar()
        self.totais.definir_desconto(0)
        self._carregando = False
        self._modificado = False
        self._atualizar_estado()

    def _atualizar_estado(self) -> None:
        if self._orcamento is None:
            self.selo.definir("Novo", ("#1A365C", "#DBEAFE"))
        else:
            os_ = ordens.os_do_orcamento(self.conn, self._orcamento.id)
            if os_ is not None:
                self.selo.definir(f"Virou a OS {os_.numero}", ("#15803D", "#DCFCE7"))
            else:
                self.selo.definir("Salvo", ("#1A365C", "#DBEAFE"))
        tem_pdf = bool(self._orcamento and self._orcamento.caminho_pdf)
        self.botao_abrir_pdf.setVisible(tem_pdf)
        self.botao_whatsapp.setVisible(tem_pdf)
        self._atualizar_totais()

    def _marcar_modificado(self) -> None:
        if not self._carregando:
            self._modificado = True

    def _itens_mudaram(self) -> None:
        self._atualizar_totais()
        self._marcar_modificado()

    def _atualizar_totais(self) -> None:
        self.totais.atualizar(calcular_totais(self.editor.itens(), self.totais.desconto_ou_zero()))

    def _buscar_placa(self) -> None:
        veiculo = clientes.buscar_veiculo_por_placa(self.conn, self.placa.text())
        if veiculo is not None and veiculo.modelo and not self.modelo.text().strip():
            self.modelo.setText(veiculo.modelo)

    def _salvar(self) -> Orcamento | None:
        if not self.editor.confirmar_pendencias():
            return None
        try:
            desconto = self.totais.desconto()
        except ValueError:
            avisar(self, "O valor do desconto é inválido. Use, por exemplo, 50 ou 50,00.")
            return None
        orcamento = Orcamento(
            id=self._orcamento.id if self._orcamento else None,
            data=self.data.data(),
            placa=self.placa.text(),
            modelo=self.modelo.text(),
            itens=self.editor.itens(),
            desconto=desconto,
            observacoes=self.observacoes.toPlainText(),
        )
        try:
            salvo = orcamentos.salvar(self.conn, orcamento)
        except ErroValidacao as erro:
            avisar(self, str(erro))
            return None
        self._modificado = False
        self.carregar(salvo.id)
        self.editor.atualizar_sugestoes()
        return salvo

    def _gerar(self) -> None:
        salvo = self._salvar()
        if salvo is None:
            return
        self.botao_gerar.setEnabled(False)
        self.botao_whatsapp.setEnabled(False)
        self.botao_gerar.setText("Gerando PDF...")
        acoes.gerar_pdf_orcamento(self.janela, salvo, lambda ok, msg: self._pdf_terminou(salvo, ok, msg))

    def _pdf_terminou(self, orcamento: Orcamento, sucesso: bool, mensagem: str) -> None:
        self.botao_gerar.setEnabled(True)
        self.botao_whatsapp.setEnabled(True)
        self.botao_gerar.setText("Gerar orçamento (PDF)")
        if sucesso and self._orcamento and self._orcamento.id == orcamento.id:
            self._orcamento.caminho_pdf = mensagem
        self._atualizar_estado()
        if not sucesso:
            mostrar_erro(self, f"O orçamento {orcamento.numero} foi salvo, mas o PDF não foi gerado.\n\n"
                               f"{mensagem}\n\n{acoes.DICA_ERRO_PDF}")
            return
        documento = f"Orçamento {orcamento.numero}"
        cliente = orcamentos.cliente_do_orcamento(self.conn, orcamento)
        nome, telefone = (cliente.nome, cliente.telefone) if cliente else ("", "")
        if acoes.envio_automatico_ativo(self.conn, telefone):
            acoes.enviar_whatsapp(self.janela, mensagem, documento, nome, telefone)
            return
        escolha = escolher(self, f"{documento} salvo e PDF gerado!\n\n{mensagem}",
                           ["Enviar no WhatsApp", "Abrir PDF", "Novo orçamento", "Continuar neste orçamento"],
                           titulo="Orçamento gerado")
        if escolha == 0:
            acoes.enviar_whatsapp(self.janela, mensagem, documento, nome, telefone)
        elif escolha == 1:
            abrir_arquivo(mensagem)
        elif escolha == 2:
            self.novo(confirmar=False)

    def _transformar_em_os(self) -> None:
        if self._orcamento is None or self._modificado:
            if not perguntar(self, "O orçamento precisa ser salvo antes de virar OS. Salvar agora?",
                             sim="Salvar", nao="Voltar"):
                return
            if self._salvar() is None:
                return
        self.janela.os_a_partir_do_orcamento(self._orcamento.id)

    def _abrir_pdf(self) -> None:
        if self._orcamento:
            acoes.abrir_pdf(self, self._orcamento.caminho_pdf)

    def _enviar_whatsapp(self) -> None:
        if self._orcamento:
            acoes.enviar_whatsapp_orcamento(self.janela, self._orcamento)
