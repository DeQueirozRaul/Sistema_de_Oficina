"""Gera as capturas de tela do README (docs/*.png) com a oficina de demonstração.

Uso:
    python ferramentas/gerar_capturas.py

Roda sem abrir janelas (Qt "offscreen") e não toca nos dados reais: o banco de
demonstração é criado numa pasta temporária, com o movimento terminando no
último dia do mês passado (para os gráficos mostrarem só meses completos).
"""

import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from oficina import demo  # noqa: E402
from oficina.banco import conectar  # noqa: E402
from oficina.documentos import nota_pdf  # noqa: E402
from oficina.servicos import configuracoes as cfg  # noqa: E402
from oficina.servicos import ordens  # noqa: E402

DESTINO = RAIZ / "docs"
LARGURA, ALTURA = 1440, 900


def _esperar(app: QApplication) -> None:
    for _ in range(5):
        app.processEvents()


def _fim_do_conteudo(imagem) -> int:
    """Última linha da imagem que não é toda branca."""
    branco = imagem.pixel(0, 0)
    for y in range(imagem.height() - 1, 0, -1):
        if any(imagem.pixel(x, y) != branco for x in range(0, imagem.width(), 4)):
            return y
    return imagem.height()


def main() -> None:
    DESTINO.mkdir(exist_ok=True)
    pasta = Path(tempfile.mkdtemp(prefix="oficina_capturas_"))
    os.environ["OFICINA_DADOS"] = str(pasta)

    app = QApplication(sys.argv[:1])
    from oficina.ui import acoes, tema
    from oficina.ui.aplicacao import _traduzir_qt
    from oficina.ui.janela_principal import JanelaPrincipal

    tema.aplicar(app)
    _traduzir_qt(app)

    fim = date.today().replace(day=1) - timedelta(days=1)  # último dia do mês passado
    conn = conectar(pasta / "oficina.db")
    demo.gerar(conn, meses=12, hoje=fim)

    janela = JanelaPrincipal(conn)
    janela.resize(LARGURA, ALTURA)
    janela.show()

    def salvar(nome: str, altura: int = ALTURA) -> None:
        janela.resize(LARGURA, altura)
        _esperar(app)
        janela.grab().save(str(DESTINO / f"{nome}.png"))
        print("docs/" + nome + ".png")

    # Painel do mês passado, com os valores visíveis.
    janela.ir_para("inicio")
    janela.pagina_inicio.periodo._navegar(-1)
    janela.pagina_inicio._alternar_valores()
    salvar("inicio")

    # Uma OS com vários itens.
    escolhida = max(ordens.buscar(conn, status="finalizada", inicio=fim.replace(day=1), fim=fim),
                    key=lambda r: (len(ordens.carregar(conn, r.id).itens), r.numero))
    janela.abrir_os(escolhida.id)
    salvar("ordem_de_servico")

    janela.ir_para("comissoes")
    janela.pagina_comissoes.periodo._navegar(-1)
    salvar("comissoes")

    janela.ir_para("relatorios")
    janela.pagina_relatorios.periodo._navegar(-1)  # 12 meses completos
    salvar("relatorios", 1060)

    # A nota em PDF dessa mesma OS, como imagem.
    os_ = ordens.carregar(conn, escolhida.id)
    nota = nota_pdf.montar_os(os_, cfg.dados_oficina(conn), acoes.logo_da_nota(conn))
    imagem = nota_pdf.imagem_previa(nota, dpi=110)
    imagem = imagem.copy(0, 0, imagem.width(), _fim_do_conteudo(imagem) + 40)  # sem o resto da página em branco
    imagem.scaledToWidth(820, Qt.TransformationMode.SmoothTransformation).save(str(DESTINO / "nota_os.png"))
    print("docs/nota_os.png")

    janela.pagina_os._modificado = False
    janela.close()
    conn.close()


if __name__ == "__main__":
    main()
