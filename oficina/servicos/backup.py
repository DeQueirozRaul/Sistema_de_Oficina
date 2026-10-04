"""Cópias de segurança do banco de dados.

É feita uma cópia por dia (ao abrir e ao fechar o sistema) e são mantidas as
últimas MANTER_BACKUPS. Para restaurar: feche o sistema, copie o backup
desejado por cima de "oficina.db" na pasta de dados e abra de novo.
"""

import os
import sqlite3
from datetime import date
from pathlib import Path

MANTER_BACKUPS = 60
PREFIXO = "oficina_"


def fazer_backup(conn: sqlite3.Connection, pasta: Path, manter: int = MANTER_BACKUPS) -> Path:
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / f"{PREFIXO}{date.today():%Y-%m-%d}.db"
    temporario = destino.with_suffix(".tmp")
    copia = sqlite3.connect(temporario)
    try:
        conn.backup(copia)  # cópia consistente mesmo com o banco aberto
    finally:
        copia.close()
    os.replace(temporario, destino)

    antigos = sorted(pasta.glob(f"{PREFIXO}*.db"))[:-manter]
    for arquivo in antigos:
        try:
            arquivo.unlink()
        except OSError:
            pass
    return destino


def ultimo_backup(pasta: Path) -> Path | None:
    backups = sorted(Path(pasta).glob(f"{PREFIXO}*.db"))
    return backups[-1] if backups else None
