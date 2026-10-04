"""Cores e folha de estilo (QSS) da aplicação, nas mesmas cores da nota.

O sistema usa sempre o tema claro, mesmo com o Windows em modo escuro: sem
isso, calendário, diálogos e listas herdavam o fundo escuro do Windows e o
texto (escuro) ficava invisível.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette

from oficina.modelos import (
    STATUS_ABERTA, STATUS_CANCELADA, STATUS_FINALIZADA, TIPO_MAO_DE_OBRA, TIPO_PECA, TIPO_TERCEIROS,
)

AZUL_ESCURO = "#1A365C"
AZUL_MEDIO = "#2B5088"
AZUL_CLARO = "#F1F5F9"
LINHA = "#CBD5E1"
FUNDO = "#EEF2F6"
TEXTO = "#1E293B"
TEXTO_SUAVE = "#64748B"

# (cor do texto, cor de fundo) de cada tipo de item
CORES_TIPO = {
    TIPO_PECA: ("#1D4ED8", "#DBEAFE"),
    TIPO_MAO_DE_OBRA: ("#15803D", "#DCFCE7"),
    TIPO_TERCEIROS: ("#B45309", "#FEF3C7"),
}

CORES_STATUS = {
    STATUS_ABERTA: ("#B45309", "#FEF3C7"),
    STATUS_FINALIZADA: ("#15803D", "#DCFCE7"),
    STATUS_CANCELADA: ("#B91C1C", "#FEE2E2"),
}

COR_PAGA = ("#15803D", "#DCFCE7")
COR_PENDENTE = ("#B45309", "#FEF3C7")

QSS = f"""
QWidget {{
    font-family: "Segoe UI", "Noto Sans", "DejaVu Sans";
    font-size: 10pt;
    color: {TEXTO};
}}
QMainWindow, #conteudo, #pagina, QScrollArea, QScrollArea > QWidget > QWidget#pagina {{
    background: {FUNDO};
}}
QScrollArea {{ border: none; }}
QToolTip {{ background: white; color: {TEXTO}; border: 1px solid {LINHA}; padding: 4px; }}

/* ---------- menu lateral ---------- */
#barraLateral {{ background: {AZUL_ESCURO}; }}
#nomeOficina {{ color: white; font-size: 12pt; font-weight: 700; }}
#logoPersonalizada {{ background: white; border-radius: 12px; padding: 8px; }}
#menuLateral {{
    background: transparent; border: none; outline: none;
}}
#menuLateral::item {{
    color: #D6E0EE; padding: 9px 14px; margin: 1px 8px; border-radius: 6px;
}}
#menuLateral::item:selected {{ background: {AZUL_MEDIO}; color: white; font-weight: 600; }}
#menuLateral::item:hover:!selected {{ background: #234675; }}
#versao {{ color: #7F95B5; font-size: 8pt; }}

/* ---------- títulos ---------- */
#tituloPagina {{ font-size: 17pt; font-weight: 700; color: {AZUL_ESCURO}; }}
#subtituloPagina {{ color: {TEXTO_SUAVE}; }}
#dica {{ color: {TEXTO_SUAVE}; font-size: 9pt; }}
#rotuloForte {{ font-weight: 600; color: {AZUL_ESCURO}; }}

/* ---------- blocos ---------- */
QGroupBox {{
    background: white; border: 1px solid {LINHA}; border-radius: 8px;
    margin-top: 12px; padding: 14px 10px 10px 10px; font-weight: 600; color: {AZUL_ESCURO};
}}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 4px; }}
QGroupBox QLabel {{ font-weight: normal; color: {TEXTO}; }}
#card {{ background: white; border: 1px solid {LINHA}; border-radius: 8px; }}
#cardTitulo {{ color: {TEXTO_SUAVE}; font-size: 9pt; }}
#cardValor {{ color: {AZUL_ESCURO}; font-size: 16pt; font-weight: 700; }}
#cardDetalhe {{ color: {TEXTO_SUAVE}; font-size: 8pt; }}
#aviso {{ background: #FEF3C7; color: #92400E; border: 1px solid #FCD34D; border-radius: 6px; padding: 7px 10px; }}
#informacao {{
    background: #E0ECFA; color: {AZUL_ESCURO}; border: 1px solid #B6CCEA; border-radius: 6px; padding: 7px 10px;
}}
#selo {{ border-radius: 10px; padding: 3px 10px; font-weight: 600; }}

/* ---------- campos ---------- */
QLineEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox, QPlainTextEdit {{
    background: white; border: 1px solid {LINHA}; border-radius: 5px; padding: 4px 6px;
    selection-background-color: #BFD3EE; selection-color: {TEXTO};
}}
QLineEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox {{ min-height: 22px; }}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QPlainTextEdit:focus {{
    border: 1px solid {AZUL_ESCURO};
}}
QLineEdit:read-only, QPlainTextEdit:read-only {{ background: {AZUL_CLARO}; }}
QLineEdit:disabled, QComboBox:disabled, QDateEdit:disabled, QPlainTextEdit:disabled {{
    background: {AZUL_CLARO}; color: {TEXTO_SUAVE};
}}
QLineEdit#numeroDocumento {{ font-weight: 700; color: {AZUL_ESCURO}; background: {AZUL_CLARO}; }}
QComboBox QAbstractItemView {{
    background: white; border: 1px solid {LINHA}; selection-background-color: #DBEAFE; selection-color: {TEXTO};
}}
QCheckBox {{ spacing: 6px; }}

/* ---------- botões ---------- */
QPushButton {{
    background: white; border: 1px solid {LINHA}; border-radius: 5px; padding: 6px 14px; min-height: 20px;
}}
QPushButton:hover {{ background: {AZUL_CLARO}; border-color: #94A3B8; }}
QPushButton:pressed {{ background: #E2E8F0; }}
QPushButton:disabled {{ color: #94A3B8; background: {AZUL_CLARO}; }}
QPushButton[primario="true"] {{
    background: {AZUL_ESCURO}; color: white; border: 1px solid {AZUL_ESCURO}; font-weight: 600;
}}
QPushButton[primario="true"]:hover {{ background: {AZUL_MEDIO}; }}
QPushButton[primario="true"]:disabled {{ background: #94A3B8; border-color: #94A3B8; }}
QPushButton[perigo="true"] {{ color: #B91C1C; }}
QPushButton[perigo="true"]:hover {{ background: #FEE2E2; border-color: #FCA5A5; }}
QPushButton[pequeno="true"] {{ padding: 3px 8px; min-height: 18px; }}
QPushButton[whatsapp="true"] {{ color: #0F7A55; border-color: #86EFAC; font-weight: 600; }}
QPushButton[whatsapp="true"]:hover {{ background: #DCFCE7; border-color: #22C55E; }}
QPushButton[whatsapp="true"]:disabled {{ color: #94A3B8; border-color: {LINHA}; background: {AZUL_CLARO}; }}

/* ---------- tabelas ---------- */
QTableWidget {{
    background: white; border: 1px solid {LINHA}; border-radius: 6px; gridline-color: #E2E8F0;
    selection-background-color: #DBEAFE; selection-color: {TEXTO}; alternate-background-color: #F8FAFC;
}}
QTableWidget::item {{ padding: 2px 6px; }}
QHeaderView::section {{
    background: {AZUL_CLARO}; color: {AZUL_ESCURO}; font-weight: 600; border: none;
    border-bottom: 1px solid {LINHA}; border-right: 1px solid #E2E8F0; padding: 6px;
}}
QTableCornerButton::section {{ background: {AZUL_CLARO}; border: none; }}

/* ---------- abas ---------- */
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{
    background: transparent; color: {TEXTO_SUAVE}; padding: 8px 16px; border: none;
    border-bottom: 2px solid transparent; font-weight: 600;
}}
QTabBar::tab:selected {{ color: {AZUL_ESCURO}; border-bottom: 2px solid {AZUL_ESCURO}; }}
QTabBar::tab:hover:!selected {{ color: {TEXTO}; }}

/* ---------- diálogos, listas suspensas e calendário ---------- */
QDialog, QMessageBox {{ background: white; }}
QListView, QTreeView {{
    background: white; color: {TEXTO}; border: 1px solid {LINHA};
    selection-background-color: #DBEAFE; selection-color: {TEXTO}; outline: none;
}}
QListView::item {{ padding: 4px 6px; }}
QCalendarWidget QWidget#qt_calendar_navigationbar {{ background: {AZUL_CLARO}; border-bottom: 1px solid {LINHA}; }}
QCalendarWidget QToolButton {{
    color: {AZUL_ESCURO}; background: transparent; border: none; font-weight: 600; padding: 4px 8px;
}}
QCalendarWidget QToolButton:hover {{ background: #DBEAFE; border-radius: 4px; }}
QCalendarWidget QToolButton::menu-indicator {{ image: none; }}
QCalendarWidget QSpinBox {{ min-height: 18px; padding: 1px 4px; }}
QCalendarWidget QAbstractItemView {{
    background: white; color: {TEXTO}; border: none;
    selection-background-color: {AZUL_MEDIO}; selection-color: white; outline: none;
}}
QCalendarWidget QAbstractItemView:disabled {{ color: #94A3B8; }}

QStatusBar {{ background: white; border-top: 1px solid {LINHA}; color: {TEXTO_SUAVE}; }}
QMenu {{ background: white; border: 1px solid {LINHA}; padding: 4px; }}
QMenu::item {{ padding: 6px 20px; border-radius: 4px; }}
QMenu::item:selected {{ background: #DBEAFE; color: {TEXTO}; }}
"""


def paleta_clara() -> QPalette:
    """Paleta clara fixa (não depende do tema do Windows)."""
    paleta = QPalette(QColor("#FFFFFF"), QColor("#F8FAFC"))  # botão, janela (gera as cores de relevo)
    cores = {
        QPalette.ColorRole.Window: "#F8FAFC",
        QPalette.ColorRole.WindowText: TEXTO,
        QPalette.ColorRole.Base: "#FFFFFF",
        QPalette.ColorRole.AlternateBase: "#F8FAFC",
        QPalette.ColorRole.Text: TEXTO,
        QPalette.ColorRole.Button: "#FFFFFF",
        QPalette.ColorRole.ButtonText: TEXTO,
        QPalette.ColorRole.BrightText: "#FFFFFF",
        QPalette.ColorRole.Highlight: AZUL_MEDIO,
        QPalette.ColorRole.HighlightedText: "#FFFFFF",
        QPalette.ColorRole.ToolTipBase: "#FFFFFF",
        QPalette.ColorRole.ToolTipText: TEXTO,
        QPalette.ColorRole.PlaceholderText: "#94A3B8",
        QPalette.ColorRole.Link: AZUL_MEDIO,
    }
    for papel, cor in cores.items():
        paleta.setColor(papel, QColor(cor))
    for papel in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText):
        paleta.setColor(QPalette.ColorGroup.Disabled, papel, QColor("#94A3B8"))
    return paleta


def aplicar(app) -> None:
    """Aplica estilo Fusion, paleta clara e a folha de estilo na aplicação."""
    app.setStyle("Fusion")
    dicas = app.styleHints()
    if hasattr(dicas, "setColorScheme"):  # Qt 6.8+: também deixa a barra de título clara
        dicas.setColorScheme(Qt.ColorScheme.Light)
    app.setPalette(paleta_clara())
    app.setStyleSheet(QSS)
