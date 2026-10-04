"""Links para abrir uma conversa do WhatsApp (aplicativo do computador ou WhatsApp Web)
e escolha de para quem a nota vai (cliente ou loja).

O envio é semiautomático: o sistema copia o PDF e abre a conversa; a pessoa
só aperta Ctrl+V e Enter. Não usa API nem automação do WhatsApp, então não há
custo nem risco de bloqueio do número.
"""

from urllib.parse import urlencode

from oficina.banco import somente_digitos

MODO_APLICATIVO = "aplicativo"
MODO_WEB = "web"
MODOS = {MODO_APLICATIVO: "Aplicativo do WhatsApp no computador", MODO_WEB: "WhatsApp Web (navegador)"}

DESTINO_CLIENTE = "cliente"
DESTINO_LOJA = "loja"
DESTINOS = {
    DESTINO_CLIENTE: "Cliente (se não tiver celular, vai para a loja)",
    DESTINO_LOJA: "Sempre a loja",
}


def numero_internacional(telefone: str) -> str:
    """'(61) 99999-0000' -> '5561999990000'. Devolve '' se o número for inválido.

    Números com DDD (10 ou 11 dígitos) ganham o código do Brasil (55).
    """
    digitos = somente_digitos(telefone).lstrip("0")
    if len(digitos) in (10, 11):
        return "55" + digitos
    if len(digitos) in (12, 13) and digitos.startswith("55"):
        return digitos
    return ""


def url_conversa(numero: str, modo: str = MODO_APLICATIVO) -> str:
    """Link que abre a conversa com o número (já no formato internacional)."""
    consulta = urlencode({"phone": numero})
    if modo == MODO_WEB:
        return f"https://web.whatsapp.com/send?{consulta}"
    return f"whatsapp://send?{consulta}"


def eh_celular(telefone: str) -> bool:
    """Se o número parece um celular brasileiro (DDD + 9 dígitos começando com 9).

    Telefone fixo não costuma ter WhatsApp; nesse caso a nota vai para a loja.
    """
    numero = numero_internacional(telefone)
    return len(numero) == 13 and numero[4] == "9"


def numero_destino(destino: str, telefone_cliente: str, telefone_loja: str) -> tuple[str, str]:
    """Para qual número a nota vai. Devolve (número internacional, "cliente" ou "loja").

    O número vem vazio se for para a loja e ela não tiver número configurado.
    """
    if destino == DESTINO_CLIENTE and eh_celular(telefone_cliente):
        return numero_internacional(telefone_cliente), DESTINO_CLIENTE
    return numero_internacional(telefone_loja), DESTINO_LOJA
