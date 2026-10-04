"""Emissão dos PDFs a partir das OS/orçamentos salvos.

Estas funções não acessam o banco: recebem tudo pronto para poderem rodar em
segundo plano (a conversão pelo Excel demora alguns segundos).
Os PDFs são organizados em subpastas por mês: OS/2026-09/OS_ABC1D23_1002.pdf
"""

from datetime import datetime
from pathlib import Path

from oficina.documentos.nota import gerar_orcamento_e_pdf, gerar_os_e_pdf
from oficina.modelos import Item, Orcamento, OrdemServico


def _itens_para_nota(itens: list[Item]) -> list[dict]:
    return [
        {
            "desc": item.descricao,
            "qtd": int(item.quantidade) if float(item.quantidade).is_integer() else item.quantidade,
            "unit": item.valor_unitario / 100,
        }
        for item in itens
    ]


def _pasta_do_mes(pasta_raiz: Path, quando) -> Path:
    pasta = Path(pasta_raiz) / quando.strftime("%Y-%m")
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def emitir_os(os_: OrdemServico, oficina: dict, pasta_raiz: Path) -> tuple[bool, str]:
    """Gera o PDF da OS. Devolve (True, caminho_do_pdf) ou (False, mensagem_de_erro)."""
    cliente = {"nome": os_.cliente_nome, "documento": os_.cliente_documento, "telefone": os_.cliente_telefone}
    veiculo = {"modelo": os_.modelo, "placa": os_.placa, "ano": os_.ano, "km": os_.km}
    return gerar_os_e_pdf(
        os_.numero, cliente, os_.mecanico_nome, veiculo, _itens_para_nota(os_.itens),
        os_.desconto / 100, os_.observacoes, str(_pasta_do_mes(pasta_raiz, os_.data)),
        data_emissao=datetime.combine(os_.data, datetime.min.time()), oficina=oficina,
    )


def emitir_orcamento(orcamento: Orcamento, oficina: dict, pasta_raiz: Path) -> tuple[bool, str]:
    veiculo = {"modelo": orcamento.modelo, "placa": orcamento.placa}
    return gerar_orcamento_e_pdf(
        orcamento.numero, veiculo, _itens_para_nota(orcamento.itens), orcamento.desconto / 100,
        orcamento.observacoes, str(_pasta_do_mes(pasta_raiz, orcamento.data)),
        data_emissao=datetime.combine(orcamento.data, datetime.min.time()), oficina=oficina,
    )
