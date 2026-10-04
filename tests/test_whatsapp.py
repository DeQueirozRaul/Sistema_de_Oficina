import pytest

from oficina.whatsapp import MODO_APLICATIVO, MODO_WEB, numero_internacional, url_conversa


@pytest.mark.parametrize("digitado, esperado", [
    ("(61) 99999-0000", "5561999990000"),
    ("(61) 3333-4444", "556133334444"),
    ("061 99999-0000", "5561999990000"),
    ("+55 61 99999-0000", "5561999990000"),
    ("5561999990000", "5561999990000"),
    ("99999-0000", ""),  # sem DDD
    ("", ""),
])
def test_numero_internacional(digitado, esperado):
    assert numero_internacional(digitado) == esperado


def test_url_conversa():
    assert url_conversa("5561999990000", MODO_APLICATIVO) == "whatsapp://send?phone=5561999990000"
    assert url_conversa("5561999990000", MODO_WEB) == "https://web.whatsapp.com/send?phone=5561999990000"


@pytest.mark.parametrize("telefone, celular", [
    ("(61) 99999-0000", True),
    ("61999990000", True),
    ("+55 (61) 99999-0000", True),
    ("(61) 3333-4444", False),  # fixo
    ("(61) 89999-0000", False),  # 11 dígitos mas não começa com 9
    ("", False),
])
def test_eh_celular(telefone, celular):
    from oficina.whatsapp import eh_celular
    assert eh_celular(telefone) is celular


def test_numero_destino():
    from oficina.whatsapp import DESTINO_CLIENTE, DESTINO_LOJA, numero_destino
    loja = "(61) 3333-4444"
    assert numero_destino(DESTINO_CLIENTE, "(61) 98888-7777", loja) == ("5561988887777", "cliente")
    assert numero_destino(DESTINO_CLIENTE, "", loja) == ("556133334444", "loja")
    assert numero_destino(DESTINO_CLIENTE, "(61) 3222-1111", loja) == ("556133334444", "loja")  # cliente com fixo
    assert numero_destino(DESTINO_LOJA, "(61) 98888-7777", loja) == ("556133334444", "loja")
    assert numero_destino(DESTINO_LOJA, "", "") == ("", "loja")
