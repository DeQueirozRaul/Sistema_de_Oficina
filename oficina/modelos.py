"""Estruturas de dados do sistema e as regras de cálculo de totais e comissão."""

from dataclasses import dataclass, field
from datetime import date

from oficina.dinheiro import aplicar_percentual, total_do_item


class ErroValidacao(Exception):
    """Erro de regra de negócio, com mensagem pronta para mostrar ao usuário."""


# Tipos de item. Somente MÃO DE OBRA gera comissão para o mecânico.
TIPO_PECA = "peca"
TIPO_MAO_DE_OBRA = "mao_de_obra"
TIPO_TERCEIROS = "terceiros"

TIPOS_ITEM = {
    TIPO_PECA: "Peça",
    TIPO_MAO_DE_OBRA: "Mão de obra",
    TIPO_TERCEIROS: "Serviço terceirizado",
}

# Situação da OS. Somente OS FINALIZADAS entram na comissão.
STATUS_ABERTA = "aberta"
STATUS_FINALIZADA = "finalizada"
STATUS_CANCELADA = "cancelada"

STATUS_OS = {
    STATUS_ABERTA: "Em aberto",
    STATUS_FINALIZADA: "Finalizada",
    STATUS_CANCELADA: "Cancelada",
}


@dataclass
class Item:
    descricao: str
    tipo: str
    quantidade: float
    valor_unitario: int  # centavos

    @property
    def total(self) -> int:
        return total_do_item(self.quantidade, self.valor_unitario)

    @property
    def gera_comissao(self) -> bool:
        return self.tipo == TIPO_MAO_DE_OBRA


@dataclass(frozen=True)
class Totais:
    pecas: int
    mao_de_obra: int
    terceiros: int
    subtotal: int
    desconto: int
    total: int
    comissao: int


def calcular_totais(itens: list[Item], desconto: int = 0, percentual_comissao: float = 0) -> Totais:
    """Soma os itens por tipo e calcula a comissão.

    A comissão é sobre o valor cheio da mão de obra: o desconto dado ao cliente
    não reduz a comissão do mecânico.
    """
    por_tipo = {TIPO_PECA: 0, TIPO_MAO_DE_OBRA: 0, TIPO_TERCEIROS: 0}
    for item in itens:
        por_tipo[item.tipo] += item.total
    subtotal = sum(por_tipo.values())
    return Totais(
        pecas=por_tipo[TIPO_PECA],
        mao_de_obra=por_tipo[TIPO_MAO_DE_OBRA],
        terceiros=por_tipo[TIPO_TERCEIROS],
        subtotal=subtotal,
        desconto=desconto,
        total=subtotal - desconto,
        comissao=aplicar_percentual(por_tipo[TIPO_MAO_DE_OBRA], percentual_comissao),
    )


def validar_itens(itens: list[Item], desconto: int) -> None:
    for posicao, item in enumerate(itens, start=1):
        if not item.descricao.strip():
            raise ErroValidacao(f"O item {posicao} está sem descrição.")
        if item.tipo not in TIPOS_ITEM:
            raise ErroValidacao(f"Escolha o tipo do item \"{item.descricao}\".")
        if not item.quantidade > 0:
            raise ErroValidacao(f"A quantidade do item \"{item.descricao}\" deve ser maior que zero.")
        if item.valor_unitario < 0:
            raise ErroValidacao(f"O valor do item \"{item.descricao}\" não pode ser negativo.")
    if desconto < 0:
        raise ErroValidacao("O desconto não pode ser negativo.")
    subtotal = sum(item.total for item in itens)
    if desconto > subtotal:
        raise ErroValidacao("O desconto não pode ser maior que o valor dos itens.")


@dataclass
class Mecanico:
    nome: str
    percentual_comissao: float = 0.0
    telefone: str = ""
    ativo: bool = True
    id: int | None = None


@dataclass
class Cliente:
    nome: str
    documento: str = ""
    telefone: str = ""
    observacoes: str = ""
    id: int | None = None


@dataclass
class Veiculo:
    placa: str
    modelo: str = ""
    ano: str = ""
    ultimo_km: str = ""
    cliente_id: int | None = None
    cliente_nome: str = ""  # apenas para exibição
    id: int | None = None


@dataclass
class OrdemServico:
    id: int | None = None
    numero: int | None = None
    status: str = STATUS_ABERTA
    data: date = field(default_factory=date.today)
    mecanico_id: int | None = None
    mecanico_nome: str = ""
    percentual_comissao: float = 0.0  # congelado quando a OS é finalizada
    cliente_id: int | None = None
    cliente_nome: str = ""
    cliente_documento: str = ""
    cliente_telefone: str = ""
    veiculo_id: int | None = None
    placa: str = ""
    modelo: str = ""
    ano: str = ""
    km: str = ""
    itens: list[Item] = field(default_factory=list)
    desconto: int = 0
    observacoes: str = ""
    orcamento_id: int | None = None
    comissao_paga: bool = False
    data_pagamento_comissao: date | None = None
    caminho_pdf: str = ""

    @property
    def totais(self) -> Totais:
        return calcular_totais(self.itens, self.desconto, self.percentual_comissao)


@dataclass
class Orcamento:
    id: int | None = None
    numero: int | None = None
    data: date = field(default_factory=date.today)
    veiculo_id: int | None = None
    placa: str = ""
    modelo: str = ""
    itens: list[Item] = field(default_factory=list)
    desconto: int = 0
    observacoes: str = ""
    caminho_pdf: str = ""

    @property
    def totais(self) -> Totais:
        return calcular_totais(self.itens, self.desconto)
