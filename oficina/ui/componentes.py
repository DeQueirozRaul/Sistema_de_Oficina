"""Componentes reutilizados pelas telas: campos com máscara, tabelas, cards,
seletor de período, mensagens e execução em segundo plano."""

from datetime import date, timedelta
from pathlib import Path

from PySide6.QtCore import (
    QByteArray, QDate, QObject, QRegularExpression, QRunnable, Qt, QThreadPool, QTimer, QUrl, Signal,
)
from PySide6.QtGui import (
    QBrush, QColor, QDesktopServices, QFont, QGuiApplication, QIcon, QPainter, QPixmap, QRegularExpressionValidator,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QAbstractItemView, QCalendarWidget, QComboBox, QDateEdit, QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPushButton, QScrollArea, QSizePolicy, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from oficina.banco import somente_digitos
from oficina.dinheiro import formatar_reais, texto_para_centavos
from oficina.periodos import MESES, deslocar_mes, formatar_data, mes, nome_mes, semana

DIREITA = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
CENTRO = Qt.AlignmentFlag.AlignCenter
ESQUERDA = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter


# ---------------------------------------------------------------- básicos

def botao(texto: str, ao_clicar=None, primario=False, perigo=False, pequeno=False, dica: str = "") -> QPushButton:
    b = QPushButton(texto)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if primario:
        b.setProperty("primario", True)
    if perigo:
        b.setProperty("perigo", True)
    if pequeno:
        b.setProperty("pequeno", True)
    if dica:
        b.setToolTip(dica)
    if ao_clicar is not None:
        b.clicked.connect(ao_clicar)
    return b


def botao_whatsapp(ao_clicar) -> QPushButton:
    b = botao("Enviar no WhatsApp", ao_clicar, dica="Copia o PDF e abre a conversa do WhatsApp da empresa")
    b.setProperty("whatsapp", True)
    return b


def rotulo(texto: str, nome_objeto: str = "", quebra=False) -> QLabel:
    r = QLabel(texto)
    if nome_objeto:
        r.setObjectName(nome_objeto)
    r.setWordWrap(quebra)
    return r


def cabecalho(titulo: str, subtitulo: str = "", *direita: QWidget) -> QHBoxLayout:
    layout = QHBoxLayout()
    textos = QVBoxLayout()
    textos.setSpacing(0)
    textos.addWidget(rotulo(titulo, "tituloPagina"))
    if subtitulo:
        textos.addWidget(rotulo(subtitulo, "subtituloPagina"))
    layout.addLayout(textos)
    layout.addStretch()
    for widget in direita:
        layout.addWidget(widget)
    return layout


class Pagina(QWidget):
    """Base das telas. `ao_exibir` é chamado sempre que a tela é aberta no menu."""

    def __init__(self, janela):
        super().__init__()
        self.janela = janela
        self.conn = janela.conn
        self.setObjectName("pagina")

    def ao_exibir(self) -> None:
        pass


_OLHO = '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>'
ICONE_OLHO_ABERTO = _OLHO
ICONE_OLHO_FECHADO = _OLHO + '<line x1="3" y1="3" x2="21" y2="21"/>'


def icone(desenho: str, cor: str = "#1A365C", tamanho: int = 18) -> QIcon:
    """Ícone de traço a partir de um desenho SVG 24x24 (nítido em qualquer zoom de tela)."""
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{cor}" '
           f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{desenho}</svg>')
    tela = QGuiApplication.primaryScreen()
    escala = tela.devicePixelRatio() if tela else 1.0
    imagem = QPixmap(round(tamanho * escala), round(tamanho * escala))
    imagem.fill(Qt.GlobalColor.transparent)
    pintor = QPainter(imagem)
    QSvgRenderer(QByteArray(svg.encode())).render(pintor)
    pintor.end()
    imagem.setDevicePixelRatio(escala)
    return QIcon(imagem)


def com_rolagem(widget: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setWidget(widget)
    return area


class Selo(QLabel):
    """Etiqueta colorida (ex.: situação da OS)."""

    def __init__(self, texto: str = "", cores: tuple[str, str] | None = None):
        super().__init__()
        self.setObjectName("selo")
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.definir(texto, cores)

    def definir(self, texto: str, cores: tuple[str, str] | None = None) -> None:
        self.setText(texto)
        self.setVisible(bool(texto))
        if cores:
            self.setStyleSheet(f"color: {cores[0]}; background: {cores[1]};")


class Card(QFrame):
    """Quadro com um número em destaque, usado no painel e nas comissões."""

    def __init__(self, titulo: str, detalhe: str = ""):
        super().__init__()
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(2)
        self._titulo = rotulo(titulo, "cardTitulo")
        self._valor = rotulo("—", "cardValor")
        self._detalhe = rotulo(detalhe, "cardDetalhe")
        layout.addWidget(self._titulo)
        layout.addWidget(self._valor)
        layout.addWidget(self._detalhe)

    def definir(self, valor: str, detalhe: str | None = None) -> None:
        self._valor.setText(valor)
        if detalhe is not None:
            self._detalhe.setText(detalhe)


# ---------------------------------------------------------------- campos

class CampoDinheiro(QLineEdit):
    """Campo de valor em R$. Aceita '150', '150,50', '1.234,56'."""

    def __init__(self, placeholder: str = "0,00"):
        super().__init__()
        self.setPlaceholderText(placeholder)
        self.setAlignment(DIREITA)
        self.setValidator(QRegularExpressionValidator(QRegularExpression(r"[0-9.,]{0,15}")))
        self.editingFinished.connect(self._formatar)

    def _formatar(self) -> None:
        try:
            self.setText(formatar_reais(texto_para_centavos(self.text()), simbolo=False))
        except ValueError:
            pass

    def centavos(self, vazio: int | None = None) -> int:
        """Valor em centavos. Se vazio devolve `vazio` (ou levanta ValueError se None)."""
        if not self.text().strip() and vazio is not None:
            return vazio
        return texto_para_centavos(self.text())

    def definir_centavos(self, centavos: int | None) -> None:
        self.setText("" if centavos is None else formatar_reais(centavos, simbolo=False))


class _CampoComMascara(QLineEdit):
    """Base das máscaras de CPF/CNPJ e telefone: formata enquanto digita."""

    maximo_digitos = 11

    def __init__(self):
        super().__init__()
        self._anterior = ""
        self.textEdited.connect(self._reformatar)

    def setText(self, texto: str) -> None:  # noqa: N802 (nome do Qt)
        super().setText(texto)
        self._anterior = texto

    def formatar(self, digitos: str) -> str:
        raise NotImplementedError

    def _reformatar(self, texto: str) -> None:
        cursor = self.cursorPosition()
        digitos_antes = len(somente_digitos(texto[:cursor]))
        digitos = somente_digitos(texto)
        apagou_separador = len(texto) < len(self._anterior) and digitos == somente_digitos(self._anterior)
        if apagou_separador and digitos_antes > 0:
            digitos = digitos[:digitos_antes - 1] + digitos[digitos_antes:]
            digitos_antes -= 1
        formatado = self.formatar(digitos[:self.maximo_digitos])
        self.setText(formatado)
        posicao = contados = 0
        while posicao < len(formatado) and contados < digitos_antes:
            if formatado[posicao].isdigit():
                contados += 1
            posicao += 1
        self.setCursorPosition(posicao)


class CampoDocumento(_CampoComMascara):
    """CPF (000.000.000-00) ou CNPJ (00.000.000/0000-00), conforme a quantidade de dígitos."""

    maximo_digitos = 14

    def formatar(self, digitos: str) -> str:
        saida = ""
        if len(digitos) <= 11:
            for i, d in enumerate(digitos):
                if i in (3, 6):
                    saida += "."
                if i == 9:
                    saida += "-"
                saida += d
        else:
            for i, d in enumerate(digitos):
                if i in (2, 5):
                    saida += "."
                if i == 8:
                    saida += "/"
                if i == 12:
                    saida += "-"
                saida += d
        return saida


class CampoTelefone(_CampoComMascara):
    """(61) 9999-9999 ou (61) 99999-9999."""

    maximo_digitos = 11

    def formatar(self, digitos: str) -> str:
        saida = ""
        for i, d in enumerate(digitos):
            if i == 0:
                saida += "("
            if i == 2:
                saida += ") "
            if (len(digitos) <= 10 and i == 6) or (len(digitos) > 10 and i == 7):
                saida += "-"
            saida += d
        return saida


def campo_busca(texto: str, ao_mudar) -> QLineEdit:
    """Campo de busca que chama `ao_mudar` um instante depois que a pessoa para de digitar."""
    campo = QLineEdit()
    campo.setPlaceholderText(texto)
    campo.setClearButtonEnabled(True)
    temporizador = QTimer(campo)
    temporizador.setSingleShot(True)
    temporizador.setInterval(250)
    temporizador.timeout.connect(ao_mudar)
    campo.textChanged.connect(lambda _: temporizador.start())
    return campo


class CampoPlaca(QLineEdit):
    def __init__(self):
        super().__init__()
        self.setMaxLength(8)
        self.setPlaceholderText("ABC1D23")
        self.setValidator(QRegularExpressionValidator(QRegularExpression(r"[A-Za-z0-9\- ]{0,8}")))
        self.textEdited.connect(self._maiusculas)

    def _maiusculas(self, texto: str) -> None:
        if texto != texto.upper():
            cursor = self.cursorPosition()
            self.setText(texto.upper())
            self.setCursorPosition(cursor)


class CampoData(QDateEdit):
    def __init__(self, valor: date | None = None):
        super().__init__()
        self.setCalendarPopup(True)
        self.setDisplayFormat("dd/MM/yyyy")
        self.calendarWidget().setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.definir(valor or date.today())

    def data(self) -> date:
        return self.date().toPython()

    def definir(self, valor: date) -> None:
        self.setDate(QDate(valor.year, valor.month, valor.day))


# ---------------------------------------------------------------- tabela

def celula(texto, alinhamento=None, cores: tuple[str, str] | None = None, negrito=False,
           dica: str = "") -> QTableWidgetItem:
    item = QTableWidgetItem("" if texto is None else str(texto))
    if alinhamento is not None:
        item.setTextAlignment(alinhamento)
    if cores:
        item.setForeground(QBrush(QColor(cores[0])))
        item.setBackground(QBrush(QColor(cores[1])))
    if negrito:
        fonte = QFont(item.font())
        fonte.setBold(True)
        item.setFont(fonte)
    if dica:
        item.setToolTip(dica)
    return item


class Tabela(QTableWidget):
    """Tabela somente leitura com seleção por linha. Cada linha guarda um objeto
    (ex.: o id da OS) que pode ser recuperado com `dado_selecionado()`."""

    def __init__(self, colunas: list[str], elastica: int = 0, multipla=False):
        super().__init__(0, len(colunas))
        self.setHorizontalHeaderLabels(colunas)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(30)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection if multipla
                              else QAbstractItemView.SelectionMode.SingleSelection)
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.setWordWrap(False)
        cabecalho_ = self.horizontalHeader()
        cabecalho_.setHighlightSections(False)
        cabecalho_.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        cabecalho_.setSectionResizeMode(elastica, QHeaderView.ResizeMode.Stretch)
        cabecalho_.setMinimumSectionSize(60)

    def definir_linhas(self, linhas: list[list], dados: list | None = None) -> None:
        self.clearSelection()
        self.setRowCount(len(linhas))
        for r, linha in enumerate(linhas):
            for c, valor in enumerate(linha):
                self.setItem(r, c, valor if isinstance(valor, QTableWidgetItem) else celula(valor))
            if dados is not None:
                self.item(r, 0).setData(Qt.ItemDataRole.UserRole, dados[r])

    def dado_da_linha(self, linha: int):
        item = self.item(linha, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def linhas_selecionadas(self) -> list[int]:
        return sorted({indice.row() for indice in self.selectionModel().selectedRows()})

    def dados_selecionados(self) -> list:
        return [self.dado_da_linha(linha) for linha in self.linhas_selecionadas()]

    def dado_selecionado(self):
        dados = self.dados_selecionados()
        return dados[0] if dados else None


# ---------------------------------------------------------------- período

class SeletorPeriodo(QWidget):
    """Escolha de período: semana, mês, período específico ou tudo.

    Nas opções semana/mês as setas navegam para a anterior/próxima.
    """

    alterado = Signal()

    NOMES = {"semana": "Semanal", "mes": "Mensal", "12meses": "Últimos 12 meses", "ano": "Anual",
             "personalizado": "Período específico", "tudo": "Todas as datas"}
    NAVEGAVEIS = ("semana", "mes", "12meses", "ano")

    def __init__(self, modos=("semana", "mes", "personalizado"), inicial="mes"):
        super().__init__()
        self._referencia = date.today()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.combo = QComboBox()
        for modo in modos:
            self.combo.addItem(self.NOMES[modo], modo)
        self.combo.setCurrentIndex(max(0, self.combo.findData(inicial)))
        self.combo.currentIndexChanged.connect(self._modo_mudou)

        self.anterior = botao("‹", lambda: self._navegar(-1), pequeno=True, dica="Período anterior")
        self.proximo = botao("›", lambda: self._navegar(1), pequeno=True, dica="Próximo período")
        self.hoje = botao("Atual", self._voltar_para_hoje, pequeno=True, dica="Voltar para o período atual")
        self.descricao = rotulo("", "rotuloForte")
        self.descricao.setMinimumWidth(190)
        self.descricao.setAlignment(CENTRO)

        self.de = CampoData(mes(date.today())[0])
        self.ate = CampoData(date.today())
        self.rotulo_ate = QLabel("até")
        for campo in (self.de, self.ate):
            campo.dateChanged.connect(lambda _: self.alterado.emit())

        for widget in (self.combo, self.anterior, self.descricao, self.proximo, self.hoje, self.de, self.rotulo_ate,
                       self.ate):
            layout.addWidget(widget)
        self._atualizar()

    def modo(self) -> str:
        return self.combo.currentData()

    def definir_modo(self, modo: str) -> None:
        self.combo.setCurrentIndex(self.combo.findData(modo))

    def definir_personalizado(self, inicio: date, fim: date) -> None:
        self.blockSignals(True)
        self.de.definir(inicio)
        self.ate.definir(fim)
        self.definir_modo("personalizado")
        self.blockSignals(False)
        self._atualizar()
        self.alterado.emit()

    def periodo(self) -> tuple[date | None, date | None]:
        modo = self.modo()
        if modo == "semana":
            return semana(self._referencia)
        if modo == "mes":
            return mes(self._referencia)
        if modo == "12meses":
            return deslocar_mes(self._referencia, -11), mes(self._referencia)[1]
        if modo == "ano":
            return date(self._referencia.year, 1, 1), date(self._referencia.year, 12, 31)
        if modo == "personalizado":
            inicio, fim = self.de.data(), self.ate.data()
            return (inicio, fim) if inicio <= fim else (fim, inicio)
        return None, None

    def descricao_periodo(self) -> str:
        inicio, fim = self.periodo()
        if inicio is None:
            return "todas as datas"
        if self.modo() == "mes":
            return nome_mes(inicio)
        if self.modo() == "ano":
            return str(inicio.year)
        if self.modo() == "12meses":
            return f"{_mes_abreviado(inicio)} a {_mes_abreviado(fim)}"
        return f"{formatar_data(inicio)} a {formatar_data(fim)}"

    def _modo_mudou(self) -> None:
        self._atualizar()
        self.alterado.emit()

    def _navegar(self, passo: int) -> None:
        if self.modo() == "semana":
            self._referencia += timedelta(days=7 * passo)
        elif self.modo() == "ano":
            self._referencia = date(self._referencia.year + passo, self._referencia.month, 1)
        else:
            self._referencia = deslocar_mes(self._referencia, passo)
        self._atualizar()
        self.alterado.emit()

    def _voltar_para_hoje(self) -> None:
        self._referencia = date.today()
        self._atualizar()
        self.alterado.emit()

    def _atualizar(self) -> None:
        modo = self.modo()
        navegavel = modo in self.NAVEGAVEIS
        for widget in (self.anterior, self.proximo, self.hoje, self.descricao):
            widget.setVisible(navegavel)
        for widget in (self.de, self.ate, self.rotulo_ate):
            widget.setVisible(modo == "personalizado")
        if navegavel:
            inicio, fim = self.periodo()
            if modo == "mes":
                self.descricao.setText(nome_mes(inicio).capitalize())
            elif modo in ("ano", "12meses"):
                self.descricao.setText(self.descricao_periodo().capitalize())
            else:
                self.descricao.setText(f"{inicio:%d/%m} a {fim:%d/%m/%Y}")


def _mes_abreviado(dia: date) -> str:
    """date(2026, 10, 1) -> 'out/2026'."""
    return f"{MESES[dia.month - 1][:3]}/{dia.year}"


# ---------------------------------------------------------------- mensagens

def _caixa(parent, icone, titulo, texto) -> QMessageBox:
    caixa = QMessageBox(icone, titulo, texto, parent=parent)
    caixa.setTextFormat(Qt.TextFormat.PlainText)
    return caixa


def perguntar(parent, texto: str, titulo: str = "Confirmar", sim: str = "Sim", nao: str = "Não") -> bool:
    caixa = _caixa(parent, QMessageBox.Icon.Question, titulo, texto)
    botao_sim = caixa.addButton(sim, QMessageBox.ButtonRole.YesRole)
    botao_nao = caixa.addButton(nao, QMessageBox.ButtonRole.NoRole)
    caixa.setDefaultButton(botao_sim)
    caixa.setEscapeButton(botao_nao)
    caixa.exec()
    return caixa.clickedButton() is botao_sim


def escolher(parent, texto: str, opcoes: list[str], titulo: str = "Sistema de Oficina",
             icone=QMessageBox.Icon.Information) -> int | None:
    """Mostra uma mensagem com vários botões e devolve o índice do escolhido."""
    caixa = _caixa(parent, icone, titulo, texto)
    botoes = [caixa.addButton(opcao, QMessageBox.ButtonRole.AcceptRole) for opcao in opcoes]
    caixa.setDefaultButton(botoes[0])
    caixa.exec()
    clicado = caixa.clickedButton()
    return botoes.index(clicado) if clicado in botoes else None


def informar(parent, texto: str, titulo: str = "Sistema de Oficina") -> None:
    caixa = _caixa(parent, QMessageBox.Icon.Information, titulo, texto)
    caixa.addButton("OK", QMessageBox.ButtonRole.AcceptRole)
    caixa.exec()


def avisar(parent, texto: str, titulo: str = "Atenção") -> None:
    caixa = _caixa(parent, QMessageBox.Icon.Warning, titulo, texto)
    caixa.addButton("OK", QMessageBox.ButtonRole.AcceptRole)
    caixa.exec()


def mostrar_erro(parent, texto: str, titulo: str = "Erro") -> None:
    caixa = _caixa(parent, QMessageBox.Icon.Critical, titulo, texto)
    caixa.addButton("OK", QMessageBox.ButtonRole.AcceptRole)
    caixa.exec()


# ---------------------------------------------------------------- arquivos

def abrir_arquivo(caminho: str | Path) -> bool:
    caminho = Path(caminho)
    if not caminho.exists():
        return False
    return QDesktopServices.openUrl(QUrl.fromLocalFile(str(caminho)))


# ---------------------------------------------------------------- segundo plano

class _Sinais(QObject):
    terminou = Signal(object)


class _Tarefa(QRunnable):
    def __init__(self, funcao):
        super().__init__()
        self.setAutoDelete(False)
        self.funcao = funcao
        self.sinais = _Sinais()

    def run(self) -> None:
        try:
            resultado = self.funcao()
        except Exception as erro:  # noqa: BLE001 - o erro vira mensagem na tela
            resultado = (False, f"{type(erro).__name__}: {erro}")
        self.sinais.terminou.emit(resultado)


_tarefas_em_andamento: set = set()


def executar_em_segundo_plano(funcao, ao_terminar) -> None:
    """Roda `funcao` numa thread (sem travar a tela) e chama `ao_terminar(resultado)`
    de volta na thread da interface."""
    tarefa = _Tarefa(funcao)

    def finalizar(resultado):
        _tarefas_em_andamento.discard(tarefa)
        ao_terminar(resultado)

    tarefa.sinais.terminou.connect(finalizar, Qt.ConnectionType.QueuedConnection)
    _tarefas_em_andamento.add(tarefa)
    QThreadPool.globalInstance().start(tarefa)
