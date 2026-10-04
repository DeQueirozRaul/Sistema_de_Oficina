"""Configurações gerais guardadas no próprio banco (entram no backup)."""

import sqlite3

NOME_OFICINA = "nome_oficina"
ENDERECO_OFICINA = "endereco_oficina"
TELEFONE_OFICINA = "telefone_oficina"
CNPJ_OFICINA = "cnpj_oficina"
LOGO_ARQUIVO = "logo_arquivo"  # vazio = logo genérica do sistema
MOSTRAR_LOGO_NA_NOTA = "mostrar_logo_na_nota"
MOSTRAR_CONTATO_NA_NOTA = "mostrar_contato_na_nota"  # telefone e CNPJ no cabeçalho
PASTA_OS = "pasta_os"
PASTA_ORCAMENTOS = "pasta_orcamentos"
PASTA_BACKUPS = "pasta_backups"
PROXIMO_NUMERO_OS = "proximo_numero_os"
PROXIMO_NUMERO_ORCAMENTO = "proximo_numero_orcamento"
CONFIGURACAO_INICIAL_FEITA = "configuracao_inicial_feita"
WHATSAPP_NUMERO = "whatsapp_numero"
WHATSAPP_MODO = "whatsapp_modo"
WHATSAPP_AUTOMATICO = "whatsapp_automatico"  # abre o WhatsApp sozinho ao gerar o PDF
WHATSAPP_EXPLICACAO_VISTA = "whatsapp_explicacao_vista"
WHATSAPP_DESTINO = "whatsapp_destino"  # "cliente" (se tiver celular) ou "loja"

PADROES = {
    NOME_OFICINA: "",  # preenchidos na configuração inicial
    ENDERECO_OFICINA: "",
    TELEFONE_OFICINA: "",
    CNPJ_OFICINA: "",
    LOGO_ARQUIVO: "",
    MOSTRAR_LOGO_NA_NOTA: "0",
    MOSTRAR_CONTATO_NA_NOTA: "0",
    PASTA_OS: "",  # vazio = pasta padrão dentro de Documentos
    PASTA_ORCAMENTOS: "",
    PASTA_BACKUPS: "",
    PROXIMO_NUMERO_OS: "1000",
    PROXIMO_NUMERO_ORCAMENTO: "1000",
    CONFIGURACAO_INICIAL_FEITA: "0",
    WHATSAPP_NUMERO: "",
    WHATSAPP_MODO: "aplicativo",
    WHATSAPP_AUTOMATICO: "1",
    WHATSAPP_EXPLICACAO_VISTA: "0",
    WHATSAPP_DESTINO: "cliente",
}


def obter(conn: sqlite3.Connection, chave: str) -> str:
    linha = conn.execute("SELECT valor FROM configuracoes WHERE chave = ?", (chave,)).fetchone()
    return linha["valor"] if linha else PADROES.get(chave, "")


def definir(conn: sqlite3.Connection, chave: str, valor) -> None:
    """Grava uma configuração (não faz commit)."""
    conn.execute(
        "INSERT INTO configuracoes (chave, valor) VALUES (?, ?) "
        "ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor",
        (chave, str(valor)),
    )


def salvar(conn: sqlite3.Connection, valores: dict) -> None:
    with conn:
        for chave, valor in valores.items():
            definir(conn, chave, valor)


def dados_oficina(conn: sqlite3.Connection) -> dict:
    """Dados impressos no cabeçalho da OS e do orçamento."""
    mostrar_contato = obter(conn, MOSTRAR_CONTATO_NA_NOTA) == "1"
    return {
        "nome": obter(conn, NOME_OFICINA),
        "endereco": obter(conn, ENDERECO_OFICINA),
        "telefone": obter(conn, TELEFONE_OFICINA) if mostrar_contato else "",
        "cnpj": obter(conn, CNPJ_OFICINA) if mostrar_contato else "",
    }
