"""Configurações: dados e logo da oficina, numeração, pastas, WhatsApp, backup e itens salvos."""

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QSpinBox, QTabWidget,
    QVBoxLayout, QWidget,
)

from oficina import caminhos, whatsapp
from oficina.dinheiro import formatar_reais
from oficina.modelos import TIPOS_ITEM, ErroValidacao
from oficina.periodos import formatar_data
from oficina.servicos import backup, catalogo, numeracao
from oficina.servicos import configuracoes as cfg
from oficina.ui import acoes, logo, tema
from oficina.ui.componentes import (
    CENTRO, DIREITA, CampoDocumento, CampoTelefone, Pagina, Tabela, abrir_arquivo, avisar, botao, cabecalho,
    campo_busca, celula, com_rolagem, mostrar_erro, perguntar, rotulo,
)
from oficina.ui.dialogos import DialogoItemCatalogo


class _CampoPasta(QWidget):
    def __init__(self, padrao: Path):
        super().__init__()
        self.padrao = padrao
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.campo = QLineEdit()
        self.campo.setPlaceholderText(str(padrao))
        layout.addWidget(self.campo, 1)
        layout.addWidget(botao("Escolher...", self._escolher, pequeno=True))
        layout.addWidget(botao("Abrir", self._abrir, pequeno=True))

    def caminho(self) -> Path:
        return Path(self.campo.text().strip() or self.padrao)

    def _escolher(self) -> None:
        pasta = QFileDialog.getExistingDirectory(self, "Escolha a pasta", str(self.caminho()))
        if pasta:
            self.campo.setText(str(Path(pasta)))

    def _abrir(self) -> None:
        pasta = self.caminho()
        pasta.mkdir(parents=True, exist_ok=True)
        abrir_arquivo(pasta)


class PaginaConfiguracoes(Pagina):
    def __init__(self, janela):
        super().__init__(janela)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 12)
        layout.addLayout(cabecalho("Configurações"))
        self.abas = QTabWidget()
        self.abas.addTab(com_rolagem(self._montar_geral()), "Geral")
        self.abas.addTab(self._montar_catalogo(), "Itens salvos (autocompletar)")
        self.abas.currentChanged.connect(lambda _: self.ao_exibir())
        layout.addWidget(self.abas, 1)

    # ------------------------------------------------------------ geral

    def _montar_geral(self) -> QWidget:
        aba = QWidget()
        aba.setObjectName("pagina")
        layout = QVBoxLayout(aba)
        layout.setContentsMargins(0, 6, 8, 0)

        grupo = QGroupBox("Dados da oficina (aparecem no cabeçalho da OS e do orçamento)")
        form = QFormLayout(grupo)
        self.nome = QLineEdit()
        self.endereco = QLineEdit()
        self.telefone = CampoTelefone()
        self.telefone.setMaximumWidth(220)
        self.cnpj = CampoDocumento()
        self.cnpj.setMaximumWidth(220)
        self.mostrar_contato = QCheckBox("Mostrar telefone e CNPJ no cabeçalho da OS e do orçamento")
        form.addRow("Nome:", self.nome)
        form.addRow("Endereço:", self.endereco)
        form.addRow("Telefone:", self.telefone)
        form.addRow("CNPJ:", self.cnpj)
        form.addRow("", self.mostrar_contato)
        layout.addWidget(grupo)

        grupo = QGroupBox("Logo da oficina")
        linha = QHBoxLayout(grupo)
        self.previa_logo = QLabel()
        self.previa_logo.setFixedSize(110, 110)
        self.previa_logo.setAlignment(CENTRO)
        self.previa_logo.setStyleSheet(f"background: {tema.AZUL_CLARO}; border-radius: 8px;")
        linha.addWidget(self.previa_logo)
        coluna = QVBoxLayout()
        botoes = QHBoxLayout()
        botoes.addWidget(botao("Escolher imagem...", self._escolher_logo))
        self.botao_logo_padrao = botao("Usar a logo padrão", self._logo_padrao)
        botoes.addWidget(self.botao_logo_padrao)
        botoes.addStretch()
        coluna.addLayout(botoes)
        self.mostrar_logo = QCheckBox("Mostrar a logo no cabeçalho da OS e do orçamento")
        coluna.addWidget(self.mostrar_logo)
        coluna.addWidget(rotulo("PNG ou JPG, de preferência com fundo branco ou transparente. A imagem é copiada "
                                "para a pasta de dados do sistema e aparece no menu lateral.", "dica", quebra=True))
        coluna.addStretch()
        linha.addLayout(coluna, 1)
        layout.addWidget(grupo)

        grupo = QGroupBox("Numeração")
        form = QFormLayout(grupo)
        self.proxima_os = QSpinBox()
        self.proximo_orcamento = QSpinBox()
        for campo in (self.proxima_os, self.proximo_orcamento):
            campo.setRange(1, 99_999_999)
            campo.setGroupSeparatorShown(False)
            campo.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
            campo.setMaximumWidth(150)
        form.addRow("Número da próxima OS:", self.proxima_os)
        form.addRow("Número do próximo orçamento:", self.proximo_orcamento)
        form.addRow("", rotulo("Só é possível avançar a numeração, nunca repetir um número já usado.", "dica"))
        layout.addWidget(grupo)

        grupo = QGroupBox("Pastas")
        form = QFormLayout(grupo)
        self.pasta_os = _CampoPasta(caminhos.pasta_padrao_os())
        self.pasta_orcamentos = _CampoPasta(caminhos.pasta_padrao_orcamentos())
        self.pasta_backups = _CampoPasta(caminhos.pasta_padrao_backups())
        form.addRow("PDFs das OS:", self.pasta_os)
        form.addRow("PDFs dos orçamentos:", self.pasta_orcamentos)
        form.addRow("Backups:", self.pasta_backups)
        form.addRow("", rotulo("Os PDFs são organizados em subpastas por mês (ex.: 2026-09). "
                               "Dica: coloque a pasta de backups dentro do Google Drive/OneDrive para ter uma cópia "
                               "fora do notebook.", "dica", quebra=True))
        layout.addWidget(grupo)

        grupo = QGroupBox("WhatsApp (botão \"Enviar no WhatsApp\" da OS e do orçamento)")
        form = QFormLayout(grupo)
        self.whatsapp_numero = CampoTelefone()
        self.whatsapp_numero.setPlaceholderText("(61) 99999-0000")
        self.whatsapp_numero.setMaximumWidth(220)
        self.whatsapp_modo = QComboBox()
        for chave, nome in whatsapp.MODOS.items():
            self.whatsapp_modo.addItem(nome, chave)
        self.whatsapp_modo.setMaximumWidth(320)
        self.whatsapp_destino = QComboBox()
        for chave, nome in whatsapp.DESTINOS.items():
            self.whatsapp_destino.addItem(nome, chave)
        self.whatsapp_destino.setMaximumWidth(420)
        self.whatsapp_automatico = QCheckBox("Ao gerar o PDF, já abrir o WhatsApp com a nota copiada")
        linha_numero = QHBoxLayout()
        linha_numero.addWidget(self.whatsapp_numero)
        linha_numero.addWidget(botao("Testar", self._testar_whatsapp, pequeno=True,
                                     dica="Abre a conversa com este número, sem enviar nada"))
        linha_numero.addStretch()
        form.addRow("Enviar para:", self.whatsapp_destino)
        form.addRow("Número da loja:", linha_numero)
        form.addRow("Abrir no:", self.whatsapp_modo)
        form.addRow("", self.whatsapp_automatico)
        form.addRow("", rotulo("O sistema copia o PDF e abre a conversa: no WhatsApp é só apertar Ctrl+V e Enter. "
                               "Com \"Cliente\", a OS vai para o celular informado nela e o orçamento "
                               "para o dono do carro (pela placa); telefone fixo ou sem telefone vai para a loja. "
                               "O número da loja pode ser o da própria empresa (o WhatsApp abre a conversa \"Você\").",
                               "dica", quebra=True))
        layout.addWidget(grupo)

        grupo = QGroupBox("Backup e dados")
        caixa = QVBoxLayout(grupo)
        self.rotulo_backup = rotulo("", quebra=True)
        caixa.addWidget(self.rotulo_backup)
        caixa.addWidget(rotulo(f"Banco de dados: {caminhos.caminho_banco()}", "dica", quebra=True))
        caixa.addWidget(rotulo("Um backup é feito automaticamente todo dia, ao abrir e ao fechar o sistema. "
                               "Para restaurar um backup: feche o sistema, copie o arquivo do backup para a pasta de "
                               "dados com o nome \"oficina.db\" (substituindo o atual) e abra o sistema de novo.",
                               "dica", quebra=True))
        botoes = QHBoxLayout()
        botoes.addWidget(botao("Fazer backup agora", self._fazer_backup))
        botoes.addWidget(botao("Abrir pasta de dados", lambda: abrir_arquivo(caminhos.pasta_dados())))
        botoes.addStretch()
        caixa.addLayout(botoes)
        layout.addWidget(grupo)

        salvar = QHBoxLayout()
        salvar.addStretch()
        salvar.addWidget(botao("Salvar configurações", self._salvar, primario=True))
        layout.addLayout(salvar)
        layout.addStretch()
        return aba

    def _carregar_geral(self) -> None:
        self.nome.setText(cfg.obter(self.conn, cfg.NOME_OFICINA))
        self.endereco.setText(cfg.obter(self.conn, cfg.ENDERECO_OFICINA))
        self.telefone.setText(cfg.obter(self.conn, cfg.TELEFONE_OFICINA))
        self.cnpj.setText(cfg.obter(self.conn, cfg.CNPJ_OFICINA))
        self.mostrar_contato.setChecked(cfg.obter(self.conn, cfg.MOSTRAR_CONTATO_NA_NOTA) == "1")
        self.mostrar_logo.setChecked(cfg.obter(self.conn, cfg.MOSTRAR_LOGO_NA_NOTA) == "1")
        self._atualizar_previa_logo()
        self.proxima_os.setValue(numeracao.proximo_numero(self.conn, cfg.PROXIMO_NUMERO_OS))
        self.proximo_orcamento.setValue(numeracao.proximo_numero(self.conn, cfg.PROXIMO_NUMERO_ORCAMENTO))
        self.pasta_os.campo.setText(cfg.obter(self.conn, cfg.PASTA_OS))
        self.pasta_orcamentos.campo.setText(cfg.obter(self.conn, cfg.PASTA_ORCAMENTOS))
        self.pasta_backups.campo.setText(cfg.obter(self.conn, cfg.PASTA_BACKUPS))
        self.whatsapp_numero.setText(cfg.obter(self.conn, cfg.WHATSAPP_NUMERO))
        self.whatsapp_modo.setCurrentIndex(max(0, self.whatsapp_modo.findData(cfg.obter(self.conn, cfg.WHATSAPP_MODO))))
        self.whatsapp_automatico.setChecked(cfg.obter(self.conn, cfg.WHATSAPP_AUTOMATICO) == "1")
        self.whatsapp_destino.setCurrentIndex(
            max(0, self.whatsapp_destino.findData(cfg.obter(self.conn, cfg.WHATSAPP_DESTINO))))
        self._atualizar_rotulo_backup()

    def _atualizar_rotulo_backup(self) -> None:
        ultimo = backup.ultimo_backup(acoes.pasta_backups(self.conn))
        self.rotulo_backup.setText(f"Último backup: {ultimo.name}" if ultimo else "Nenhum backup feito ainda.")

    def _salvar(self) -> None:
        if not self.nome.text().strip():
            avisar(self, "Informe o nome da oficina.")
            return
        numero = self.whatsapp_numero.text().strip()
        if numero and not whatsapp.numero_internacional(numero):
            avisar(self, "O número do WhatsApp deve ter DDD, por exemplo (61) 99999-0000.")
            return
        try:
            with self.conn:
                cfg.definir(self.conn, cfg.NOME_OFICINA, self.nome.text().strip())
                cfg.definir(self.conn, cfg.ENDERECO_OFICINA, self.endereco.text().strip())
                cfg.definir(self.conn, cfg.TELEFONE_OFICINA, self.telefone.text().strip())
                cfg.definir(self.conn, cfg.CNPJ_OFICINA, self.cnpj.text().strip())
                cfg.definir(self.conn, cfg.MOSTRAR_CONTATO_NA_NOTA, "1" if self.mostrar_contato.isChecked() else "0")
                cfg.definir(self.conn, cfg.MOSTRAR_LOGO_NA_NOTA, "1" if self.mostrar_logo.isChecked() else "0")
                numeracao.definir_proximo_numero(self.conn, cfg.PROXIMO_NUMERO_OS, self.proxima_os.value())
                numeracao.definir_proximo_numero(self.conn, cfg.PROXIMO_NUMERO_ORCAMENTO,
                                                 self.proximo_orcamento.value())
                cfg.definir(self.conn, cfg.PASTA_OS, self.pasta_os.campo.text().strip())
                cfg.definir(self.conn, cfg.PASTA_ORCAMENTOS, self.pasta_orcamentos.campo.text().strip())
                cfg.definir(self.conn, cfg.PASTA_BACKUPS, self.pasta_backups.campo.text().strip())
                cfg.definir(self.conn, cfg.WHATSAPP_NUMERO, numero)
                cfg.definir(self.conn, cfg.WHATSAPP_MODO, self.whatsapp_modo.currentData())
                cfg.definir(self.conn, cfg.WHATSAPP_DESTINO, self.whatsapp_destino.currentData())
                cfg.definir(self.conn, cfg.WHATSAPP_AUTOMATICO, "1" if self.whatsapp_automatico.isChecked() else "0")
        except ErroValidacao as erro:
            avisar(self, str(erro))
            return
        self.janela.configuracoes_alteradas()
        self.janela.mensagem("Configurações salvas.")
        self._carregar_geral()

    def _atualizar_previa_logo(self) -> None:
        self.previa_logo.setPixmap(logo.pixmap_logo(self.conn, 96))
        self.botao_logo_padrao.setEnabled(logo.caminho_logo_personalizada(self.conn) is not None)

    def _escolher_logo(self) -> None:
        arquivo, _ = QFileDialog.getOpenFileName(self, "Escolha a logo da oficina", str(Path.home()), logo.FORMATOS)
        if not arquivo:
            return
        try:
            logo.salvar_logo(self.conn, arquivo)
        except ErroValidacao as erro:
            avisar(self, str(erro))
            return
        self._atualizar_previa_logo()
        self.janela.configuracoes_alteradas()
        self.janela.mensagem("Logo atualizada.")

    def _logo_padrao(self) -> None:
        logo.usar_logo_padrao(self.conn)
        self._atualizar_previa_logo()
        self.janela.configuracoes_alteradas()

    def _testar_whatsapp(self) -> None:
        numero = whatsapp.numero_internacional(self.whatsapp_numero.text())
        if not numero:
            avisar(self, "Digite o número com DDD, por exemplo (61) 99999-0000.")
            return
        modo = self.whatsapp_modo.currentData()
        if not acoes.abrir_url(whatsapp.url_conversa(numero, modo)):
            avisar(self, "Não foi possível abrir o WhatsApp. Se o aplicativo não estiver instalado, "
                         "escolha \"WhatsApp Web (navegador)\".")

    def _fazer_backup(self) -> None:
        try:
            destino = backup.fazer_backup(self.conn, acoes.pasta_backups(self.conn))
        except OSError as erro:
            mostrar_erro(self, f"Não foi possível fazer o backup:\n{erro}")
            return
        self._atualizar_rotulo_backup()
        self.janela.mensagem(f"Backup salvo em {destino}")

    # ------------------------------------------------------------ catálogo

    def _montar_catalogo(self) -> QWidget:
        aba = QWidget()
        layout = QVBoxLayout(aba)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.addWidget(rotulo("Esta lista é montada sozinha com os itens lançados nas OS e orçamentos, e alimenta o "
                                "autocompletar. O valor é apenas uma sugestão: ele pode ser alterado em cada OS. "
                                "Corrija aqui descrições digitadas errado ou exclua itens que não são mais usados.",
                                "informacao", quebra=True))
        self.busca_catalogo = campo_busca("Buscar item", self._atualizar_catalogo)
        layout.addWidget(self.busca_catalogo)
        self.tabela_catalogo = Tabela(["Descrição", "Tipo", "Último valor", "Último uso"], elastica=0, multipla=True)
        self.tabela_catalogo.doubleClicked.connect(lambda _: self._editar_item())
        self.tabela_catalogo.itemSelectionChanged.connect(self._botoes_catalogo)
        layout.addWidget(self.tabela_catalogo, 1)
        botoes = QHBoxLayout()
        botoes.addStretch()
        self.botao_excluir_item = botao("Excluir", self._excluir_itens, perigo=True)
        self.botao_editar_item = botao("Editar", self._editar_item, primario=True)
        botoes.addWidget(self.botao_excluir_item)
        botoes.addWidget(self.botao_editar_item)
        layout.addLayout(botoes)
        return aba

    def _atualizar_catalogo(self) -> None:
        itens = catalogo.listar(self.conn, self.busca_catalogo.text())
        self.tabela_catalogo.definir_linhas([
            [i.descricao, celula(TIPOS_ITEM[i.tipo], CENTRO, tema.CORES_TIPO[i.tipo], negrito=True),
             celula(formatar_reais(i.valor_unitario), DIREITA), celula(formatar_data(i.ultimo_uso), CENTRO)]
            for i in itens
        ], itens)
        self._botoes_catalogo()

    def _botoes_catalogo(self) -> None:
        selecionados = self.tabela_catalogo.dados_selecionados()
        self.botao_editar_item.setEnabled(len(selecionados) == 1)
        self.botao_excluir_item.setEnabled(bool(selecionados))

    def _editar_item(self) -> None:
        selecionados = self.tabela_catalogo.dados_selecionados()
        if len(selecionados) == 1 and DialogoItemCatalogo(self, self.conn, selecionados[0]).exec():
            self._atualizar_catalogo()

    def _excluir_itens(self) -> None:
        selecionados = self.tabela_catalogo.dados_selecionados()
        if not selecionados or not perguntar(
                self, f"Remover {len(selecionados)} item(ns) do autocompletar?\n\nAs OS já feitas não são alteradas.",
                sim="Remover", nao="Voltar"):
            return
        for item in selecionados:
            catalogo.excluir(self.conn, item.id)
        self._atualizar_catalogo()

    # ------------------------------------------------------------

    def ao_exibir(self) -> None:
        if self.abas.currentIndex() == 0:
            self._carregar_geral()
        else:
            self._atualizar_catalogo()
