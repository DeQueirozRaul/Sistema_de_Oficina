"""Ajustes visuais que só existem no Windows (fora dele as funções não fazem nada)."""

import sys

# Atributos da função DwmSetWindowAttribute (dwmapi.h)
_DWMWA_USE_IMMERSIVE_DARK_MODE = 20
_DWMWA_BORDER_COLOR = 34
_DWMWA_CAPTION_COLOR = 35
_DWMWA_TEXT_COLOR = 36


def _colorref(cor: str) -> int:
    """'#1A365C' -> 0x005C361A (o Windows usa a ordem azul-verde-vermelho)."""
    r, g, b = (int(cor.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    return r | (g << 8) | (b << 16)


def pintar_barra_de_titulo(janela, cor_fundo: str, cor_texto: str = "#FFFFFF") -> None:
    """Pinta a barra de título da janela (a faixa com o título e os botões de fechar/minimizar).

    No Windows 11 fica exatamente na cor pedida. O Windows 10 não permite
    escolher a cor: lá a barra fica escura (modo escuro), que combina melhor
    com o menu lateral do que a barra branca.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes

        janela_nativa = wintypes.HWND(int(janela.winId()))
        dwm = ctypes.windll.dwmapi

        def definir(atributo: int, valor: int) -> bool:
            dado = ctypes.c_int(valor)
            return dwm.DwmSetWindowAttribute(janela_nativa, atributo, ctypes.byref(dado), ctypes.sizeof(dado)) == 0

        if definir(_DWMWA_CAPTION_COLOR, _colorref(cor_fundo)):
            definir(_DWMWA_BORDER_COLOR, _colorref(cor_fundo))
            definir(_DWMWA_TEXT_COLOR, _colorref(cor_texto))
        else:  # Windows 10
            definir(_DWMWA_USE_IMMERSIVE_DARK_MODE, 1)
    except Exception:  # noqa: BLE001 - só estética, nunca pode impedir a janela de abrir
        pass


def identificar_aplicativo() -> None:
    """Faz a barra de tarefas do Windows mostrar a logo (e não o ícone do Python)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("SistemaOficina.App")
    except Exception:  # noqa: BLE001 - só estética
        pass
