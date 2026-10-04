"""Conexão com o banco SQLite e criação/atualização das tabelas.

As alterações de estrutura ficam na lista MIGRACOES. Cada item é aplicado uma
única vez, em ordem, e o número da última aplicada fica guardado em
`PRAGMA user_version`. Para mudar o banco no futuro, ADICIONE um novo item no
final da lista (nunca edite um item que já foi aplicado no notebook da loja).

Transações: as funções públicas dos serviços usam `with conn:` (commit no
final, rollback em caso de erro). Funções auxiliares chamadas por elas não
abrem transação própria, para que tudo seja gravado de uma vez só.
"""

import re
import sqlite3
import unicodedata
from datetime import date, datetime

MIGRACOES = [
    # 1 - estrutura inicial
    """
    CREATE TABLE configuracoes (
        chave TEXT PRIMARY KEY,
        valor TEXT NOT NULL
    );

    CREATE TABLE mecanicos (
        id INTEGER PRIMARY KEY,
        nome TEXT NOT NULL,
        percentual_comissao REAL NOT NULL DEFAULT 0
            CHECK (percentual_comissao BETWEEN 0 AND 100),
        telefone TEXT NOT NULL DEFAULT '',
        ativo INTEGER NOT NULL DEFAULT 1
    );

    CREATE TABLE clientes (
        id INTEGER PRIMARY KEY,
        nome TEXT NOT NULL,
        documento TEXT NOT NULL DEFAULT '',
        telefone TEXT NOT NULL DEFAULT '',
        observacoes TEXT NOT NULL DEFAULT ''
    );

    CREATE TABLE veiculos (
        id INTEGER PRIMARY KEY,
        placa TEXT NOT NULL,
        placa_normalizada TEXT NOT NULL UNIQUE,
        modelo TEXT NOT NULL DEFAULT '',
        ano TEXT NOT NULL DEFAULT '',
        ultimo_km TEXT NOT NULL DEFAULT '',
        cliente_id INTEGER REFERENCES clientes(id) ON DELETE SET NULL
    );

    CREATE TABLE ordens_servico (
        id INTEGER PRIMARY KEY,
        numero INTEGER NOT NULL UNIQUE,
        status TEXT NOT NULL CHECK (status IN ('aberta', 'finalizada', 'cancelada')),
        data TEXT NOT NULL,
        mecanico_id INTEGER REFERENCES mecanicos(id),
        mecanico_nome TEXT NOT NULL DEFAULT '',
        percentual_comissao REAL NOT NULL DEFAULT 0,
        cliente_id INTEGER REFERENCES clientes(id) ON DELETE SET NULL,
        cliente_nome TEXT NOT NULL DEFAULT '',
        cliente_documento TEXT NOT NULL DEFAULT '',
        cliente_telefone TEXT NOT NULL DEFAULT '',
        veiculo_id INTEGER REFERENCES veiculos(id) ON DELETE SET NULL,
        placa TEXT NOT NULL DEFAULT '',
        modelo TEXT NOT NULL DEFAULT '',
        ano TEXT NOT NULL DEFAULT '',
        km TEXT NOT NULL DEFAULT '',
        desconto INTEGER NOT NULL DEFAULT 0,
        total_pecas INTEGER NOT NULL DEFAULT 0,
        total_mao_de_obra INTEGER NOT NULL DEFAULT 0,
        total_terceiros INTEGER NOT NULL DEFAULT 0,
        total INTEGER NOT NULL DEFAULT 0,
        comissao INTEGER NOT NULL DEFAULT 0,
        comissao_paga INTEGER NOT NULL DEFAULT 0,
        data_pagamento_comissao TEXT,
        observacoes TEXT NOT NULL DEFAULT '',
        orcamento_id INTEGER REFERENCES orcamentos(id) ON DELETE SET NULL,
        caminho_pdf TEXT NOT NULL DEFAULT '',
        criado_em TEXT NOT NULL,
        atualizado_em TEXT NOT NULL
    );
    CREATE INDEX idx_os_data ON ordens_servico(data);
    CREATE INDEX idx_os_mecanico ON ordens_servico(mecanico_id);

    CREATE TABLE itens_os (
        id INTEGER PRIMARY KEY,
        os_id INTEGER NOT NULL REFERENCES ordens_servico(id) ON DELETE CASCADE,
        posicao INTEGER NOT NULL,
        descricao TEXT NOT NULL,
        tipo TEXT NOT NULL CHECK (tipo IN ('peca', 'mao_de_obra', 'terceiros')),
        quantidade REAL NOT NULL,
        valor_unitario INTEGER NOT NULL,
        total INTEGER NOT NULL
    );
    CREATE INDEX idx_itens_os ON itens_os(os_id);

    CREATE TABLE orcamentos (
        id INTEGER PRIMARY KEY,
        numero INTEGER NOT NULL UNIQUE,
        data TEXT NOT NULL,
        veiculo_id INTEGER REFERENCES veiculos(id) ON DELETE SET NULL,
        placa TEXT NOT NULL DEFAULT '',
        modelo TEXT NOT NULL DEFAULT '',
        desconto INTEGER NOT NULL DEFAULT 0,
        total INTEGER NOT NULL DEFAULT 0,
        observacoes TEXT NOT NULL DEFAULT '',
        caminho_pdf TEXT NOT NULL DEFAULT '',
        criado_em TEXT NOT NULL,
        atualizado_em TEXT NOT NULL
    );
    CREATE INDEX idx_orcamentos_data ON orcamentos(data);

    CREATE TABLE itens_orcamento (
        id INTEGER PRIMARY KEY,
        orcamento_id INTEGER NOT NULL REFERENCES orcamentos(id) ON DELETE CASCADE,
        posicao INTEGER NOT NULL,
        descricao TEXT NOT NULL,
        tipo TEXT NOT NULL CHECK (tipo IN ('peca', 'mao_de_obra', 'terceiros')),
        quantidade REAL NOT NULL,
        valor_unitario INTEGER NOT NULL,
        total INTEGER NOT NULL
    );
    CREATE INDEX idx_itens_orcamento ON itens_orcamento(orcamento_id);

    -- Itens já lançados, usados no autocompletar (último tipo e valor usados).
    CREATE TABLE catalogo_itens (
        id INTEGER PRIMARY KEY,
        descricao TEXT NOT NULL UNIQUE COLLATE NOCASE,
        tipo TEXT NOT NULL CHECK (tipo IN ('peca', 'mao_de_obra', 'terceiros')),
        valor_unitario INTEGER NOT NULL,
        ultimo_uso TEXT NOT NULL
    );
    """,
]


def conectar(caminho: str = ":memory:") -> sqlite3.Connection:
    """Abre o banco, liga as chaves estrangeiras e aplica migrações pendentes."""
    conn = sqlite3.connect(str(caminho))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.create_function("normalizar", 1, normalizar_texto, deterministic=True)
    conn.create_function("digitos", 1, somente_digitos, deterministic=True)
    migrar(conn)
    return conn


def migrar(conn: sqlite3.Connection) -> None:
    versao_atual = conn.execute("PRAGMA user_version").fetchone()[0]
    for versao, script in enumerate(MIGRACOES[versao_atual:], start=versao_atual + 1):
        conn.executescript(f"BEGIN;\n{script}\nPRAGMA user_version = {versao};\nCOMMIT;")


def normalizar_texto(texto: str | None) -> str:
    """Minúsculas e sem acento, para buscas: 'João' -> 'joao'."""
    if not texto:
        return ""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sem_acento.casefold()


def somente_digitos(texto: str | None) -> str:
    return re.sub(r"\D", "", texto or "")


def agora() -> str:
    return datetime.now().isoformat(sep=" ", timespec="seconds")


def para_data(texto: str | None) -> date | None:
    return date.fromisoformat(texto) if texto else None
