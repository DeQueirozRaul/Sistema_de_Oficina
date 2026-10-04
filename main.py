"""Abre o Sistema de Oficina.

Uso:
    python main.py          # usa os dados da oficina (Documentos/Sistema Oficina)
    python main.py --demo   # abre com uma oficina fictícia, sem tocar nos dados reais
"""

import os
import sys
from pathlib import Path

if __name__ == "__main__":
    if "--demo" in sys.argv:
        from oficina.demo import preparar_pasta

        pasta = Path(__file__).resolve().parent / "dados_demo"
        print("Preparando a oficina de demonstração (só na primeira vez demora alguns segundos)...")
        preparar_pasta(pasta)
        os.environ["OFICINA_DADOS"] = str(pasta)

    from oficina.ui.aplicacao import executar

    raise SystemExit(executar())
