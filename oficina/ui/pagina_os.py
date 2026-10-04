"""Tela de criação/edição de Ordem de Serviço."""

from datetime import date

from PySide6.QtCore import QStringListModel, Qt
from PySide6.QtWidgets import (
    QComboBox, QCompleter, QGridLayout, QGroupBox, QHBoxLayout, QLineEdit, QPlainTextEdit, QVBoxLayout, QWidget,
)

from oficina.dinheiro import formatar_percentual, formatar_reais
from oficina.modelos import (
    STATUS_ABERTA, STATUS_CANCELADA, STATUS_FINALIZADA, STATUS_OS, ErroValidacao, OrdemServico, calcular_totais,
)
from oficina.periodos import formatar_data
from oficina.servicos import clientes, mecanicos, orcamentos, ordens
from oficina.ui import acoes, tema
from oficina.ui.componentes import (
    CampoData, CampoDocumento, CampoPlaca, CampoTelefone, Pagina, Selo, abrir_arquivo, avisar, botao,
    botao_whatsapp, cabecalho, com_rolagem, escolher, mostrar_erro, perguntar, rotulo,
)
from oficina.ui.dialogos import DialogoMecanico
from oficina.ui.editor_itens import EditorItens, PainelTotais


class PaginaOS(Pagina):
    def __init__(self, janela):
        super().__init__(janela)
        self._os: OrdemServico | None = None       # OS carregada do banco (None = nova)
        self._orcamento_id: int | None = None     # quando veio de um orçamento
        self._cliente_id: int | None = None
        self._percentuais: dict[int, float] = {}
        self._auto_preenchidos: set = set()       # campos preenchidos pela busca da placa
        self._ultima_placa_buscada = ""
        self._modificado = False
        self._carregando = False

        conteudo = QWidget()
        conteudo.setObjectName("pagina")
        layout = QVBoxLayout(conteudo)
        layout.setContentsMargins(20, 16, 20, 8)

        self.selo = Selo()
        layout.addLayout(cabecalho("Ordem de Serviço", "Preencha os dados e finalize ao terminar o serviço.",
                                   self.selo, botao("Nova OS", lambda: self.nova())))
        self.faixa = rotulo("", "informacao", quebra=True)
        self.faixa.hide()
        layout.addWidget(self.faixa)

        # ---- atendimento
        self.grupo_atendimento = QGroupBox("Atendimento")
        grade = QGridLayout(self.grupo_atendimento)
        self.numero = QLineEdit()
        self.numero.setObjectName("numeroDocumento")
        self.numero.setReadOnly(True)
        self.numero.setMaximumWidth(110)
        self.data = CampoData()
        self.mecanico = QComboBox()
        self.mecanico.setMinimumWidth(240)
        self.mecanico.setPlaceholderText("Escolha o mecânico...")
        self.botao_novo_mecanico = botao("+", self._cadastrar_mecanico, pequeno=True, dica="Cadastrar novo mecânico")
        self.rotulo_percentual = rotulo("", "dica")
        grade.addWidget(rotulo("OS Nº"), 0, 0)
        grade.addWidget(self.numero, 0, 1)
        grade.addWidget(rotulo("Data"), 0, 2)
        grade.addWidget(self.data, 0, 3)
        grade.addWidget(rotulo("Mecânico"), 0, 4)
        grade.addWidget(self.mecanico, 0, 5)
        grade.addWidget(self.botao_novo_mecanico, 0, 6)
        grade.addWidget(self.rotulo_percentual, 0, 7)
        grade.setColumnStretch(8, 1)
        layout.addWidget(self.grupo_atendimento)

        # ---- veículo e cliente
        self.grupo_veiculo = QGroupBox("Veículo")
        grade = QGridLayout(self.grupo_veiculo)
        self.placa = CampoPlaca()
        self.placa.setToolTip("Digite a placa: se o carro já veio antes, o resto é preenchido sozinho.")
        self._completar_placas = QStringListModel(self)
        completar = QCompleter(self._completar_placas, self)
        completar.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.placa.setCompleter(completar)
        completar.activated[str].connect(lambda _: self._buscar_placa())  # depois do setCompleter
        self.modelo = QLineEdit()
        self.ano = QLineEdit()
        self.ano.setMaximumWidth(90)
        self.km = QLineEdit()
        self.km.setMaximumWidth(120)
        grade.addWidget(rotulo("Placa"), 0, 0)
        grade.addWidget(self.placa, 0, 1)
        grade.addWidget(rotulo("Modelo"), 0, 2)
        grade.addWidget(self.modelo, 0, 3, 1, 3)
        grade.addWidget(rotulo("Ano"), 1, 0)
        grade.addWidget(self.ano, 1, 1)
        grade.addWidget(rotulo("KM"), 1, 2)
        grade.addWidget(self.km, 1, 3)
        grade.setColumnStretch(3, 1)

        self.grupo_cliente = QGroupBox("Cliente")
        grade = QGridLayout(self.grupo_cliente)
        self.cliente = QLineEdit()
        self.cliente.setPlaceholderText("Nome do cliente")
        self._completar_clientes = QStringListModel(self)
        self._ids_clientes: dict[str, int] = {}
        completar = QCompleter(self._completar_clientes, self)
        completar.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completar.setFilterMode(Qt.MatchFlag.MatchContains)
        self.cliente.setCompleter(completar)
        completar.activated[str].connect(self._cliente_escolhido)  # depois do setCompleter
        self.documento = CampoDocumento()
        self.telefone = CampoTelefone()
        grade.addWidget(rotulo("Nome"), 0, 0)
        grade.addWidget(self.cliente, 0, 1, 1, 3)
        grade.addWidget(rotulo("CPF/CNPJ"), 1, 0)
        grade.addWidget(self.documento, 1, 1)
        grade.addWidget(rotulo("Telefone"), 1, 2)
        grade.addWidget(self.telefone, 1, 3)

        linha = QHBoxLayout()
        linha.addWidget(self.grupo_veiculo, 1)
        linha.addWidget(self.grupo_cliente, 1)
        layout.addLayout(linha)

        # ---- itens (esquerda) + totais e observações (direita)
        self.grupo_itens = QGroupBox("Peças e serviços")
        caixa = QVBoxLayout(self.grupo_itens)
        self.editor = EditorItens(self.conn)
        caixa.addWidget(self.editor)

        self.totais = PainelTotais(mostrar_comissao=True)
        self.grupo_obs = QGroupBox("Observações gerais")
        caixa = QVBoxLayout(self.grupo_obs)
        self.observacoes = QPlainTextEdit()
        self.observacoes.setPlaceholderText("Aparecem na OS impressa.")
        self.observacoes.setMinimumHeight(60)
        caixa.addWidget(self.observacoes)
        direita = QVBoxLayout()
        direita.addWidget(self.totais)
        direita.addWidget(self.grupo_obs, 1)

        linha = QHBoxLayout()
        linha.addWidget(self.grupo_itens, 1)
        linha.addLayout(direita)
        layout.addLayout(linha, 1)

        # ---- barra de botões (fora da rolagem, sempre visível)
        self.botao_abrir_pdf = botao("Abrir PDF", self._abrir_pdf)
        self.botao_whatsapp = botao_whatsapp(self._enviar_whatsapp)
        self.botao_salvar = botao("Salvar em aberto", lambda: self._salvar(finalizar=False, gerar_pdf=False))
        self.botao_principal = botao("Finalizar e gerar PDF", lambda: self._salvar(finalizar=True, gerar_pdf=True),
                                     primario=True)
        barra = QHBoxLayout()
        barra.setContentsMargins(20, 8, 20, 12)
        barra.addWidget(self.botao_abrir_pdf)
        barra.addWidget(self.botao_whatsapp)
        barra.addStretch()
        barra.addWidget(self.botao_salvar)
        barra.addWidget(self.botao_principal)

        externo = QVBoxLayout(self)
        externo.setContentsMargins(0, 0, 0, 0)
        externo.setSpacing(0)
        externo.addWidget(com_rolagem(conteudo), 1)
        externo.addLayout(barra)

        # ---- sinais
        for campo in (self.modelo, self.ano, self.km, self.documento, self.telefone):
            campo.textEdited.connect(lambda _, c=campo: self._editado_pelo_usuario(c))
        self.cliente.textEdited.connect(self._cliente_digitado)
        self.placa.textEdited.connect(lambda _: self._marcar_modificado())
        self.placa.editingFinished.connect(self._buscar_placa)
        self.observacoes.textChanged.connect(self._marcar_modificado)
        self.data.dateChanged.connect(lambda _: self._marcar_modificado())
        self.mecanico.currentIndexChanged.connect(self._mecanico_mudou)
        self.editor.alterado.connect(self._itens_mudaram)
        self.totais.desconto_alterado.connect(self._itens_mudaram)

        self._carregar_listas()
        self._limpar()

    # ================================================================ API usada pela janela

    @property
    def modificado(self) -> bool:
        return self._modificado

    @property
    def os_carregada(self) -> OrdemServico | None:
        return self._os

    def recarregar(self) -> None:
        """Relê do banco a OS aberta (ex.: foi cancelada pelo Histórico)."""
        if self._os is not None:
            self._modificado = False
            self.carregar(self._os.id)

    def ao_exibir(self) -> None:
        self._carregar_listas()
        self.editor.atualizar_sugestoes()

    def pode_descartar(self) -> bool:
        if not self._modificado:
            return True
        numero = f"da OS {self._os.numero}" if self._os else "desta nova OS"
        return perguntar(self, f"Existem alterações não salvas {numero}.\nDeseja descartá-las?",
                         titulo="Alterações não salvas", sim="Descartar alterações", nao="Voltar")

    def nova(self, confirmar: bool = True) -> None:
        if confirmar and not self.pode_descartar():
            return
        self._limpar()
        self.placa.setFocus()

    def carregar(self, os_id: int) -> bool:
        if not self.pode_descartar():
            return False
        os_ = ordens.carregar(self.conn, os_id)
        if os_ is None:
            avisar(self, "OS não encontrada.")
            return False
        self._preencher(os_)
        return True

    def carregar_de_orcamento(self, orcamento_id: int) -> bool:
        existente = ordens.os_do_orcamento(self.conn, orcamento_id)
        if existente is not None:
            escolha = escolher(self, f"Este orçamento já foi transformado na OS nº {existente.numero}.",
                               [f"Abrir a OS {existente.numero}", "Criar outra OS mesmo assim", "Cancelar"])
            if escolha == 0:
                return self.carregar(existente.id)
            if escolha != 1:
                return False
        if not self.pode_descartar():
            return False
        rascunho = orcamentos.montar_os(self.conn, orcamento_id)
        numero_orcamento = orcamentos.carregar(self.conn, orcamento_id).numero
        self._limpar()
        self._carregando = True
        self._preencher_campos(rascunho)
        self._carregando = False
        self._orcamento_id = orcamento_id
        self._mostrar_faixa(f"OS criada a partir do orçamento nº {numero_orcamento}. Confira os dados, "
                            "escolha o mecânico e clique em \"Finalizar e gerar PDF\".", "informacao")
        self._atualizar_totais()
        self._modificado = True
        return True

    # ================================================================ preenchimento

    def _carregar_listas(self) -> None:
        selecionado = self.mecanico.currentData()
        self._carregando, carregando_antes = True, self._carregando
        self.mecanico.clear()
        self._percentuais = {}
        for mecanico in mecanicos.listar(self.conn):
            self._percentuais[mecanico.id] = mecanico.percentual_comissao
            manter = mecanico.id in (selecionado, self._os.mecanico_id if self._os else None)
            if mecanico.ativo or manter:
                nome = mecanico.nome if mecanico.ativo else f"{mecanico.nome} (inativo)"
                self.mecanico.addItem(nome, mecanico.id)
        self.mecanico.setCurrentIndex(self.mecanico.findData(selecionado) if selecionado is not None else -1)
        self._carregando = carregando_antes

        self._completar_placas.setStringList(clientes.placas_cadastradas(self.conn))
        nomes = clientes.nomes_clientes(self.conn)
        contagem: dict[str, int] = {}
        for _, nome in nomes:
            contagem[nome.casefold()] = contagem.get(nome.casefold(), 0) + 1
        self._ids_clientes = {}
        for id_, nome in nomes:
            chave = nome if contagem[nome.casefold()] == 1 else f"{nome} (cód. {id_})"
            self._ids_clientes[chave] = id_
        self._completar_clientes.setStringList(list(self._ids_clientes))
        self._atualizar_percentual()

    def _limpar(self) -> None:
        self._carregando = True
        self._os = None
        self._orcamento_id = None
        self._cliente_id = None
        self._auto_preenchidos.clear()
        self._ultima_placa_buscada = ""
        self.numero.setText(str(ordens.proximo_numero(self.conn)))
        self.data.definir(date.today())
        self.mecanico.setCurrentIndex(-1)
        for campo in (self.placa, self.modelo, self.ano, self.km, self.cliente, self.documento, self.telefone):
            campo.setText("")
        self.km.setPlaceholderText("")
        self.observacoes.setPlainText("")
        self.editor.limpar()
        self.totais.definir_desconto(0)
        self._carregando = False
        self._modificado = False
        self._atualizar_estado()

    def _preencher_campos(self, os_: OrdemServico) -> None:
        self.data.definir(os_.data)
        self.mecanico.setCurrentIndex(self.mecanico.findData(os_.mecanico_id) if os_.mecanico_id else -1)
        self.placa.setText(os_.placa)
        self.modelo.setText(os_.modelo)
        self.ano.setText(os_.ano)
        self.km.setText(os_.km)
        self.cliente.setText(os_.cliente_nome)
        self.documento.setText(os_.cliente_documento)
        self.telefone.setText(os_.cliente_telefone)
        self.observacoes.setPlainText(os_.observacoes)
        self.editor.definir_itens(os_.itens)
        self.totais.definir_desconto(os_.desconto)
        self._cliente_id = os_.cliente_id
        self._ultima_placa_buscada = clientes.normalizar_placa(os_.placa)

    def _preencher(self, os_: OrdemServico) -> None:
        self._carregando = True
        self._os = os_
        self._orcamento_id = os_.orcamento_id
        self._auto_preenchidos.clear()
        self._carregar_listas()
        self.numero.setText(str(os_.numero))
        self._preencher_campos(os_)
        self._carregando = False
        self._modificado = False
        self._atualizar_estado()

    def _atualizar_estado(self) -> None:
        """Ajusta selo, faixa de aviso e botões conforme a situação da OS."""
        status = self._os.status if self._os else None
        cancelada = status == STATUS_CANCELADA
        if status:
            self.selo.definir(STATUS_OS[status], tema.CORES_STATUS[status])
        else:
            self.selo.definir("Nova", (tema.AZUL_ESCURO, "#DBEAFE"))

        if cancelada:
            self._mostrar_faixa("Esta OS está cancelada e não pode ser alterada. "
                                "Para editar, reative-a no Histórico.", "aviso")
        elif self._os and self._os.comissao_paga:
            self._mostrar_faixa(f"A comissão desta OS ({formatar_reais(self._os.totais.comissao)}) já foi paga ao "
                                f"mecânico em {formatar_data(self._os.data_pagamento_comissao)}.", "informacao")
        else:
            self.faixa.hide()

        for widget in (self.grupo_atendimento, self.grupo_veiculo, self.grupo_cliente, self.grupo_obs, self.totais):
            widget.setEnabled(not cancelada)
        self.editor.definir_somente_leitura(cancelada)

        tem_pdf = bool(self._os and self._os.caminho_pdf)
        self.botao_abrir_pdf.setVisible(tem_pdf)
        self.botao_whatsapp.setVisible(tem_pdf and not cancelada)
        self.botao_salvar.setVisible(not cancelada)
        self.botao_principal.setVisible(not cancelada)
        if status == STATUS_FINALIZADA:
            self.botao_salvar.setText("Salvar alterações")
            self.botao_principal.setText("Salvar e gerar PDF")
        else:
            self.botao_salvar.setText("Salvar em aberto")
            self.botao_principal.setText("Finalizar e gerar PDF")
        self._atualizar_totais()

    def _mostrar_faixa(self, texto: str, estilo: str) -> None:
        self.faixa.setObjectName(estilo)
        self.faixa.style().unpolish(self.faixa)  # reaplica o QSS do novo objectName
        self.faixa.style().polish(self.faixa)
        self.faixa.setText(texto)
        self.faixa.show()

    # ================================================================ reações a edição

    def _marcar_modificado(self) -> None:
        if not self._carregando:
            self._modificado = True

    def _editado_pelo_usuario(self, campo) -> None:
        self._auto_preenchidos.discard(campo)
        self._marcar_modificado()

    def _cliente_digitado(self, _texto: str) -> None:
        # Nome alterado à mão: deixa o sistema identificar o cliente ao salvar
        # (por CPF/CNPJ ou nome), para não renomear o cadastro de outra pessoa.
        self._cliente_id = None
        self._editado_pelo_usuario(self.cliente)

    def _cliente_escolhido(self, texto: str) -> None:
        cliente_id = self._ids_clientes.get(texto)
        cliente = clientes.obter_cliente(self.conn, cliente_id) if cliente_id else None
        if cliente is None:
            return
        self._cliente_id = cliente.id
        self.cliente.setText(cliente.nome)
        self.documento.setText(cliente.documento)
        self.telefone.setText(cliente.telefone)
        self._marcar_modificado()

    def _buscar_placa(self) -> None:
        normalizada = clientes.normalizar_placa(self.placa.text())
        if not normalizada or normalizada == self._ultima_placa_buscada:
            return
        self._ultima_placa_buscada = normalizada
        veiculo = clientes.buscar_veiculo_por_placa(self.conn, normalizada)
        if veiculo is None:
            self.km.setPlaceholderText("")
            return
        valores = [(self.modelo, veiculo.modelo), (self.ano, veiculo.ano)]
        cliente = clientes.obter_cliente(self.conn, veiculo.cliente_id) if veiculo.cliente_id else None
        pode_trocar_cliente = not self.cliente.text().strip() or self.cliente in self._auto_preenchidos
        if cliente is not None and pode_trocar_cliente:
            valores += [(self.cliente, cliente.nome), (self.documento, cliente.documento),
                        (self.telefone, cliente.telefone)]
            self._cliente_id = cliente.id
        for campo, valor in valores:
            if valor and (not campo.text().strip() or campo in self._auto_preenchidos):
                campo.setText(valor)
                self._auto_preenchidos.add(campo)
        self.km.setPlaceholderText(f"último: {veiculo.ultimo_km}" if veiculo.ultimo_km else "")
        self.janela.mensagem(f"Veículo {veiculo.placa} encontrado: dados preenchidos automaticamente.")

    def _mecanico_mudou(self) -> None:
        self._atualizar_percentual()
        self._atualizar_totais()
        self._marcar_modificado()

    def _itens_mudaram(self) -> None:
        self._atualizar_totais()
        self._marcar_modificado()

    def _percentual(self) -> float:
        mecanico_id = self.mecanico.currentData()
        if mecanico_id is None:
            return 0.0
        return ordens.percentual_para(self._os, mecanico_id, self._percentuais.get(mecanico_id, 0.0))

    def _atualizar_percentual(self) -> None:
        if self.mecanico.currentData() is None:
            self.rotulo_percentual.setText("")
        elif self._percentual() == 0:
            self.rotulo_percentual.setText("Sem comissão")
        else:
            self.rotulo_percentual.setText(f"Comissão: {formatar_percentual(self._percentual())} da mão de obra")

    def _atualizar_totais(self) -> None:
        totais = calcular_totais(self.editor.itens(), self.totais.desconto_ou_zero(), self._percentual())
        if self.mecanico.currentData() is None:
            texto = "Comissão prevista"
        elif self._percentual() == 0:
            texto = "Sem comissão (0%)"
        else:
            texto = f"Comissão prevista ({formatar_percentual(self._percentual())})"
        self.totais.atualizar(totais, texto)

    def _cadastrar_mecanico(self) -> None:
        dialogo = DialogoMecanico(self, self.conn)
        if dialogo.exec():
            self._carregar_listas()
            self.mecanico.setCurrentIndex(self.mecanico.findData(dialogo.mecanico.id))

    # ================================================================ salvar

    def _coletar(self) -> OrdemServico:
        desconto = self.totais.desconto()  # ValueError se inválido
        return OrdemServico(
            id=self._os.id if self._os else None,
            numero=self._os.numero if self._os else None,
            data=self.data.data(),
            mecanico_id=self.mecanico.currentData(),
            cliente_id=self._cliente_id,
            cliente_nome=self.cliente.text(),
            cliente_documento=self.documento.text(),
            cliente_telefone=self.telefone.text(),
            placa=self.placa.text(),
            modelo=self.modelo.text(),
            ano=self.ano.text(),
            km=self.km.text(),
            itens=self.editor.itens(),
            desconto=desconto,
            observacoes=self.observacoes.toPlainText(),
            orcamento_id=self._orcamento_id,
        )

    def _salvar(self, finalizar: bool, gerar_pdf: bool) -> None:
        if not self.editor.confirmar_pendencias():
            return
        try:
            os_ = self._coletar()
        except ValueError:
            avisar(self, "O valor do desconto é inválido. Use, por exemplo, 50 ou 50,00.")
            return

        status_atual = self._os.status if self._os else None
        status = STATUS_FINALIZADA if (finalizar or status_atual == STATUS_FINALIZADA) else STATUS_ABERTA

        hoje = date.today()
        if finalizar and status_atual == STATUS_ABERTA and os_.data < hoje:
            escolha = escolher(
                self, f"Esta OS foi aberta em {formatar_data(os_.data)}.\n"
                      "Qual data deve ficar na OS finalizada? (É a data usada na comissão.)",
                [f"Usar hoje ({formatar_data(hoje)})", f"Manter {formatar_data(os_.data)}", "Voltar"])
            if escolha == 0:
                os_.data = hoje
                self.data.definir(hoje)
            elif escolha != 1:
                return

        if self._os and self._os.comissao_paga:
            nova_comissao = calcular_totais(os_.itens, os_.desconto, self._percentual()).comissao
            if nova_comissao != self._os.totais.comissao or os_.mecanico_id != self._os.mecanico_id:
                if not perguntar(self, "A comissão desta OS já foi paga "
                                       f"({formatar_reais(self._os.totais.comissao)}).\n"
                                       f"Com esta alteração ela passa a ser {formatar_reais(nova_comissao)}.\n\n"
                                       "Deseja salvar mesmo assim?", sim="Salvar", nao="Voltar"):
                    return

        try:
            salva = ordens.salvar(self.conn, os_, status)
        except ErroValidacao as erro:
            avisar(self, str(erro))
            return

        self._preencher(salva)
        self.editor.atualizar_sugestoes()
        if not gerar_pdf:
            situacao = "finalizada" if salva.status == STATUS_FINALIZADA else "salva em aberto"
            self.janela.mensagem(f"OS {salva.numero} {situacao}.")
            return
        self._definir_botoes_habilitados(False)
        acoes.gerar_pdf_os(self.janela, salva, lambda ok, msg: self._pdf_terminou(salva, ok, msg))

    def _definir_botoes_habilitados(self, habilitar: bool) -> None:
        for b in (self.botao_salvar, self.botao_principal, self.botao_abrir_pdf, self.botao_whatsapp):
            b.setEnabled(habilitar)
        if habilitar:
            self._atualizar_estado()
        else:
            self.botao_principal.setText("Gerando PDF...")

    def _pdf_terminou(self, os_: OrdemServico, sucesso: bool, mensagem: str) -> None:
        if sucesso and self._os and self._os.id == os_.id:
            self._os.caminho_pdf = mensagem
        self._definir_botoes_habilitados(True)
        if not sucesso:
            mostrar_erro(self, f"A OS {os_.numero} foi salva, mas o PDF não foi gerado.\n\n{mensagem}"
                               f"\n\n{acoes.DICA_ERRO_PDF}")
            return
        self.janela.mensagem(f"OS {os_.numero} finalizada. PDF salvo em {mensagem}")
        if acoes.envio_automatico_ativo(self.conn, os_.cliente_telefone):
            acoes.enviar_whatsapp(self.janela, mensagem, f"OS {os_.numero}", os_.cliente_nome, os_.cliente_telefone)
            return
        escolha = escolher(self, f"OS {os_.numero} salva e PDF gerado!\n\n{mensagem}",
                           ["Enviar no WhatsApp", "Abrir PDF", "Nova OS", "Continuar nesta OS"], titulo="OS gerada")
        if escolha == 0:
            acoes.enviar_whatsapp(self.janela, mensagem, f"OS {os_.numero}", os_.cliente_nome, os_.cliente_telefone)
        elif escolha == 1:
            abrir_arquivo(mensagem)
        elif escolha == 2:
            self.nova(confirmar=False)

    def _abrir_pdf(self) -> None:
        if self._os:
            acoes.abrir_pdf(self, self._os.caminho_pdf)

    def _enviar_whatsapp(self) -> None:
        if self._os:
            acoes.enviar_whatsapp_os(self.janela, self._os)
