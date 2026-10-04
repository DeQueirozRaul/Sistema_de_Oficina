"""Dados de demonstração: uma oficina fictícia com meses de movimento.

Uso:
    python -m oficina.demo --pasta dados_demo     # só gera o banco
    python main.py --demo                         # gera (se precisar) e abre o sistema

Os dados são inventados, mas seguem padrões de uma oficina de suspensão de
verdade, para que os relatórios e o notebook de análise tenham o que mostrar:
sazonalidade (fim de ano mais fraco), mais movimento no início da semana,
clientes que voltam, orçamentos que viram OS e mecânicos com ritmos
diferentes. Telefones usam o DDD 00 (inexistente), para nunca coincidir com o
número de alguém.
"""

import argparse
import random
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from oficina.banco import conectar
from oficina.modelos import (
    STATUS_FINALIZADA, TIPO_MAO_DE_OBRA, TIPO_PECA, TIPO_TERCEIROS, Item, Mecanico, Orcamento, OrdemServico,
)
from oficina.periodos import semana
from oficina.servicos import comissoes, mecanicos, orcamentos, ordens
from oficina.servicos import configuracoes as cfg

SEMENTE = 42

PRIMEIROS_NOMES = ["Ana", "Bruno", "Camila", "Diego", "Eduarda", "Felipe", "Gabriela", "Henrique", "Isabela",
                   "João", "Karina", "Lucas", "Mariana", "Nicolas", "Olívia", "Paulo", "Renata", "Samuel",
                   "Tatiane", "Vinícius", "Larissa", "Rodrigo", "Patrícia", "Gustavo", "Fernanda", "André"]
SOBRENOMES = ["Almeida", "Barbosa", "Cardoso", "Dias", "Ferreira", "Gomes", "Lima", "Martins", "Nunes",
              "Oliveira", "Pereira", "Ribeiro", "Santos", "Souza", "Teixeira", "Vieira", "Rocha", "Costa",
              "Araújo", "Batista", "Campos", "Duarte", "Freitas", "Lopes", "Machado", "Mendes", "Moura",
              "Pinto", "Ramos", "Sales"]
EMPRESAS = ["Transportes Rápido Ltda", "Entregas Expressa ME", "Locadora Bom Caminho Ltda", "Frota Fácil Ltda"]
MODELOS = ["Gol 1.0", "Onix 1.4", "HB20 1.6", "Palio 1.0", "Strada 1.4", "Corolla 2.0", "Civic 2.0", "Fox 1.6",
           "Ka 1.0", "Sandero 1.6", "Saveiro 1.6", "Fiorino 1.4", "Hilux 2.8", "Kwid 1.0", "Argo 1.3", "Polo 1.0"]


@dataclass(frozen=True)
class Servico:
    """Um tipo de serviço: peças + mão de obra (+ terceiros), com preços de referência em centavos."""
    nome: str
    itens: tuple[tuple[str, str, int, int], ...]  # (descrição, tipo, quantidade, valor unitário)
    peso: int  # frequência relativa


SERVICOS = [
    Servico("amortecedor dianteiro", (("Amortecedor dianteiro", TIPO_PECA, 2, 28500),
                                       ("Kit batente e coifa dianteiro", TIPO_PECA, 2, 6500),
                                       ("Troca de amortecedor dianteiro", TIPO_MAO_DE_OBRA, 1, 18000)), 14),
    Servico("amortecedor traseiro", (("Amortecedor traseiro", TIPO_PECA, 2, 24000),
                                      ("Troca de amortecedor traseiro", TIPO_MAO_DE_OBRA, 1, 15000)), 9),
    Servico("pivô", (("Pivô de suspensão", TIPO_PECA, 2, 7800),
                     ("Troca de pivô", TIPO_MAO_DE_OBRA, 1, 12000)), 12),
    Servico("bieleta", (("Bieleta dianteira", TIPO_PECA, 2, 4500),
                        ("Troca de bieleta", TIPO_MAO_DE_OBRA, 1, 8000)), 11),
    Servico("bandeja", (("Bandeja de suspensão", TIPO_PECA, 1, 32000),
                        ("Bucha da bandeja", TIPO_PECA, 2, 3500),
                        ("Troca de bandeja", TIPO_MAO_DE_OBRA, 1, 16000)), 6),
    Servico("terminal de direção", (("Terminal de direção", TIPO_PECA, 2, 5500),
                                     ("Troca de terminal de direção", TIPO_MAO_DE_OBRA, 1, 9000)), 8),
    Servico("freio dianteiro", (("Pastilha de freio dianteira", TIPO_PECA, 1, 18000),
                                ("Disco de freio", TIPO_PECA, 2, 21000),
                                ("Revisão de freio dianteiro", TIPO_MAO_DE_OBRA, 1, 15000)), 10),
    Servico("molas", (("Mola dianteira", TIPO_PECA, 2, 21000),
                      ("Troca de molas", TIPO_MAO_DE_OBRA, 1, 16000)), 4),
    Servico("coxim", (("Coxim do amortecedor", TIPO_PECA, 2, 9500),
                      ("Troca de coxim", TIPO_MAO_DE_OBRA, 1, 9000)), 5),
    Servico("óleo e filtros", (("Óleo do motor 5W30 (litro)", TIPO_PECA, 4, 4500),
                               ("Filtro de óleo", TIPO_PECA, 1, 4000),
                               ("Troca de óleo e filtro", TIPO_MAO_DE_OBRA, 1, 6000)), 9),
    Servico("diagnóstico", (("Diagnóstico de suspensão", TIPO_MAO_DE_OBRA, 1, 8000),), 5),
]
ALINHAMENTO = (("Alinhamento e balanceamento", TIPO_TERCEIROS, 1, 12000),)

# Movimento relativo por mês (jan a dez): fim de ano e janeiro mais fracos, março e outubro mais fortes.
SAZONALIDADE = [0.70, 0.90, 1.10, 1.00, 1.00, 0.95, 1.00, 1.05, 1.00, 1.15, 1.05, 0.75]
# Movimento relativo por dia da semana (seg a sex); fim de semana fechado.
DIAS_DA_SEMANA = [1.30, 1.10, 1.00, 0.95, 0.85]
OS_POR_DIA = 2.4


@dataclass
class _Cliente:
    nome: str
    telefone: str
    placa: str
    modelo: str
    ano: str
    km: int
    frota: bool = False
    documento: str = ""  # só as empresas (frotas) têm CNPJ, fictício e diferente para cada uma


def _placa(r: random.Random) -> str:
    letras = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return f"{''.join(r.choices(letras, k=3))}{r.randint(0, 9)}{r.choice(letras)}{r.randint(10, 99)}"


def _telefone(r: random.Random) -> str:
    return f"(00) 9{r.randint(1000, 9999)}-{r.randint(1000, 9999)}"  # DDD 00 não existe


def _clientes(r: random.Random, quantidade: int) -> list[_Cliente]:
    # Nomes sem repetição: o sistema reconhece o cliente pelo nome, e dois "João Silva" virariam um só.
    pessoas = [f"{nome} {sobrenome}" for nome in PRIMEIROS_NOMES for sobrenome in SOBRENOMES]
    r.shuffle(pessoas)
    if quantidade > len(EMPRESAS) + len(pessoas):
        raise ValueError(f"No máximo {len(EMPRESAS) + len(pessoas)} clientes de demonstração.")
    lista = []
    for i in range(quantidade):
        frota = i < len(EMPRESAS)
        nome = EMPRESAS[i] if frota else pessoas[i - len(EMPRESAS)]
        lista.append(_Cliente(nome=nome, telefone=_telefone(r), placa=_placa(r), modelo=r.choice(MODELOS),
                              ano=str(r.randint(2008, 2024)), km=r.randint(20_000, 180_000), frota=frota,
                              documento=f"00.000.000/000{i + 1}-00" if frota else ""))
    return lista


def _variar(r: random.Random, centavos: int, variacao: float = 0.15) -> int:
    """Preço varia de carro para carro (e com a inflação ao longo do ano)."""
    return int(round(centavos * r.uniform(1 - variacao, 1 + variacao) / 500)) * 500


def _itens_do_servico(r: random.Random, inflacao: float) -> list[Item]:
    servicos = r.choices(SERVICOS, weights=[s.peso for s in SERVICOS], k=1 if r.random() < 0.7 else 2)
    itens: list[Item] = []
    for servico in dict.fromkeys(servicos):  # sem repetir o mesmo serviço
        for descricao, tipo, quantidade, valor in servico.itens:
            itens.append(Item(descricao, tipo, quantidade, _variar(r, round(valor * inflacao))))
    if any(i.descricao.startswith(("Troca de amort", "Troca de pivô", "Troca de bandeja", "Troca de terminal"))
           for i in itens) and r.random() < 0.6:
        itens += [Item(d, t, q, _variar(r, round(v * inflacao), 0.05)) for d, t, q, v in ALINHAMENTO]
    return itens


def gerar(conn, meses: int = 12, hoje: date | None = None, semente: int = SEMENTE) -> dict:
    """Preenche o banco com uma oficina fictícia. Devolve um resumo do que foi criado."""
    r = random.Random(semente)
    hoje = hoje or date.today()
    cfg.salvar(conn, {
        cfg.NOME_OFICINA: "AUTO CENTER MODELO",
        cfg.ENDERECO_OFICINA: "Av. das Oficinas, 1000 - Centro, Cidade Exemplo/UF",
        cfg.TELEFONE_OFICINA: "(00) 3000-0000",
        cfg.CNPJ_OFICINA: "00.000.000/0001-00",
        cfg.MOSTRAR_CONTATO_NA_NOTA: "1",
        cfg.MOSTRAR_LOGO_NA_NOTA: "1",
        cfg.CONFIGURACAO_INICIAL_FEITA: "1",
        cfg.PROXIMO_NUMERO_OS: "1000",
        cfg.PROXIMO_NUMERO_ORCAMENTO: "500",
    })
    equipe = [
        (Mecanico("Marcos Pereira", 30), 1.35),  # mais experiente: pega mais OS
        (Mecanico("Bruno Almeida", 25), 1.00),
        (Mecanico("Rafael Costa", 20), 0.80),
        (Mecanico("Carlos Andrade (sócio)", 0), 0.60),  # sócio: não recebe comissão
    ]
    ids = [mecanicos.salvar(conn, m) for m, _ in equipe]
    pesos_mecanicos = [peso for _, peso in equipe]
    clientes = _clientes(r, 600)
    # Poucos clientes voltam muitas vezes (frotas e fiéis); a maioria vem uma vez no ano.
    pesos_clientes = [12 if c.frota else r.choice([1, 1, 1, 1, 1, 1, 1, 2, 4]) for c in clientes]

    inicio = (hoje.replace(day=1) - timedelta(days=1)).replace(day=1)
    for _ in range(meses - 2):
        inicio = (inicio - timedelta(days=1)).replace(day=1)

    criadas = abertas = canceladas = orcamentos_criados = 0
    dia = inicio
    while dia <= hoje:
        if dia.weekday() < 5:
            meses_passados = (hoje.year - dia.year) * 12 + hoje.month - dia.month
            inflacao = 1 - 0.004 * meses_passados  # preços sobem ~0,4% ao mês
            media = OS_POR_DIA * SAZONALIDADE[dia.month - 1] * DIAS_DA_SEMANA[dia.weekday()]
            for _ in range(_quantidade(r, media)):
                cliente = r.choices(clientes, weights=pesos_clientes, k=1)[0]
                cliente.km += r.randint(3_000, 12_000)
                itens = _itens_do_servico(r, inflacao)
                subtotal = sum(i.total for i in itens)

                orcamento_id = None
                if r.random() < 0.35:  # parte dos serviços começa como orçamento
                    orcamento = orcamentos.salvar(conn, Orcamento(
                        data=dia - timedelta(days=r.randint(1, 6)), placa=cliente.placa, modelo=cliente.modelo,
                        itens=itens, observacoes="Orçamento válido por 7 dias."))
                    orcamentos_criados += 1
                    orcamento_id = orcamento.id
                    # Cliente não aprovou (fica sem OS). Quanto mais caro, maior a chance de recusa:
                    # ~15% nos serviços baratos, ~50% a partir de R$ 1.500.
                    if r.random() < 0.15 + 0.35 * min(1.0, subtotal / 150_000):
                        continue

                recente = (hoje - dia).days <= 2
                status = "aberta" if recente and r.random() < 0.5 else STATUS_FINALIZADA
                os_ = OrdemServico(
                    data=dia, mecanico_id=r.choices(ids, weights=pesos_mecanicos, k=1)[0],
                    cliente_nome=cliente.nome, cliente_telefone=cliente.telefone,
                    cliente_documento=cliente.documento,
                    placa=cliente.placa, modelo=cliente.modelo, ano=cliente.ano, km=str(cliente.km),
                    itens=itens, desconto=_desconto(r, subtotal), orcamento_id=orcamento_id,
                    observacoes=r.choice(["", "", "Cliente aguardou no local.", "Revisar em 10.000 km.",
                                          "Peças com garantia de 3 meses."]))
                salva = ordens.salvar(conn, os_, status)
                criadas += 1
                if status != STATUS_FINALIZADA:
                    abertas += 1
                elif r.random() < 0.03:
                    ordens.cancelar(conn, salva.id)
                    canceladas += 1
        dia += timedelta(days=1)

    _pagar_comissoes_antigas(conn, inicio, hoje)
    return {"os": criadas, "em_aberto": abertas, "canceladas": canceladas, "orcamentos": orcamentos_criados,
            "clientes": len(clientes), "mecanicos": len(equipe), "inicio": inicio, "fim": hoje}


def _quantidade(r: random.Random, media: float) -> int:
    """Quantidade de OS no dia (distribuição de Poisson pelo método de Knuth)."""
    limite, produto, k = 2.718281828 ** (-media), 1.0, 0
    while True:
        produto *= r.random()
        if produto <= limite:
            return k
        k += 1


def _desconto(r: random.Random, subtotal: int) -> int:
    if r.random() < 0.75:
        return 0
    return min(subtotal, r.choice([1000, 2000, 3000, 5000, round(subtotal * 0.05 / 100) * 100]))


def _pagar_comissoes_antigas(conn, inicio: date, hoje: date) -> None:
    """Comissões são pagas toda sexta, referentes à semana; a semana atual fica pendente."""
    segunda, _ = semana(inicio)
    while True:
        de, ate = semana(segunda)
        if ate >= semana(hoje)[0]:
            break
        linhas = comissoes.listar(conn, de, ate, situacao=comissoes.SITUACAO_PENDENTES)
        comissoes.marcar_como_pagas(conn, [l.os_id for l in linhas], ate - timedelta(days=2))
        segunda += timedelta(days=7)


def preparar_pasta(pasta: Path, meses: int = 12) -> Path:
    """Cria o banco de demonstração na pasta, se ainda não existir. Devolve o caminho do banco."""
    pasta.mkdir(parents=True, exist_ok=True)
    banco = pasta / "oficina.db"
    if not banco.exists():
        conn = conectar(banco)
        try:
            gerar(conn, meses)
        finally:
            conn.close()
    return banco


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera um banco de demonstração do Sistema de Oficina.")
    parser.add_argument("--pasta", default="dados_demo", help="pasta onde o banco será criado (padrão: dados_demo)")
    parser.add_argument("--meses", type=int, default=12, help="quantos meses de movimento (padrão: 12)")
    args = parser.parse_args()
    banco = Path(args.pasta) / "oficina.db"
    if banco.exists():
        raise SystemExit(f"{banco} já existe. Apague a pasta para gerar de novo.")
    preparar_pasta(Path(args.pasta), args.meses)
    print(f"Banco de demonstração criado em {banco}")


if __name__ == "__main__":
    main()
