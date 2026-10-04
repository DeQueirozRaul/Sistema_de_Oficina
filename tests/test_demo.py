from datetime import date

from oficina import demo
from oficina.periodos import semana
from oficina.servicos import comissoes

HOJE = date(2026, 10, 7)  # quarta-feira


def test_demo_gera_movimento_realista_e_reproduzivel(conn):
    resumo = demo.gerar(conn, meses=3, hoje=HOJE)

    assert resumo["os"] > 100 and resumo["orcamentos"] > 0
    assert resumo["inicio"] == date(2026, 8, 1)
    datas = [linha[0] for linha in conn.execute("SELECT DISTINCT data FROM ordens_servico")]
    assert all(date.fromisoformat(d).weekday() < 5 for d in datas)  # fim de semana fechado
    assert max(datas) <= HOJE.isoformat()

    # Orçamentos aprovados viram OS; alguns ficam sem OS (não aprovados).
    aprovados = conn.execute("SELECT COUNT(DISTINCT orcamento_id) FROM ordens_servico").fetchone()[0]
    assert 0 < aprovados < resumo["orcamentos"]

    # Telefones fictícios: DDD 00, que não existe.
    telefones = {linha[0] for linha in conn.execute("SELECT telefone FROM clientes")}
    assert telefones and all(t.startswith("(00) ") for t in telefones)

    # Mesma semente, mesmo resultado.
    from oficina.banco import conectar
    outro = conectar(":memory:")
    try:
        assert demo.gerar(outro, meses=3, hoje=HOJE) == resumo
    finally:
        outro.close()


def test_demo_socio_sem_comissao_e_semana_atual_pendente(conn):
    demo.gerar(conn, meses=2, hoje=HOJE)
    segunda_atual = semana(HOJE)[0]

    linhas = comissoes.listar(conn, date(2026, 1, 1), HOJE)
    assert linhas and not any("sócio" in l.mecanico_nome for l in linhas)
    assert all(l.paga for l in linhas if l.data < segunda_atual)
    assert not any(l.paga for l in linhas if l.data >= segunda_atual)
    assert all(l.data_pagamento.weekday() == 4 for l in linhas if l.paga)  # pagas na sexta

    os_socio = conn.execute("SELECT COUNT(*) FROM ordens_servico WHERE mecanico_nome LIKE '%sócio%'").fetchone()[0]
    assert os_socio > 0  # ele trabalha, só não recebe comissão


def test_preparar_pasta_nao_recria_banco_existente(tmp_path, monkeypatch):
    chamadas = []
    original = demo.gerar
    monkeypatch.setattr(demo, "gerar", lambda conn, meses: chamadas.append(meses) or original(conn, 1, HOJE))

    banco = demo.preparar_pasta(tmp_path / "demo", meses=1)
    assert banco.exists()
    demo.preparar_pasta(tmp_path / "demo", meses=1)
    assert chamadas == [1]
