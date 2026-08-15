import logging
from urllib.parse import quote

from django.conf import settings

from loja.models import Cupom, Pagamento

logger = logging.getLogger(__name__)


def obter_dados_checkout(cupom_codigo):
    """
    Resolve o cupom e calcula os valores padrao para a pagina de pagamento manual.
    """
    cupom_codigo = (cupom_codigo or "").strip().upper()
    cupom = Cupom.objects.filter(codigo__iexact=cupom_codigo, ativo=True).first() if cupom_codigo else None
    valor = Pagamento._meta.get_field("valor").default
    valor_final = cupom.aplicar(valor) if cupom else valor

    return {
        "cupom": cupom,
        "cupom_codigo": cupom_codigo,
        "valor": valor,
        "valor_final": valor_final,
        "pix_key": getattr(settings, "PREMIUM_PIX_KEY", "").strip(),
        "whatsapp_number": getattr(settings, "PREMIUM_WHATSAPP_NUMBER", "").strip(),
    }


def montar_url_comprovante_whatsapp(loja, usuario, pix_key=""):
    numero = "".join(char for char in getattr(settings, "PREMIUM_WHATSAPP_NUMBER", "") if char.isdigit())
    if not numero:
        return ""
    mensagem = (
        "Olá! Enviei o pagamento manual da assinatura Premium do VestLink.\n"
        f"Loja: {loja.nome}\n"
        f"Slug: {loja.slug}\n"
        f"Usuário: {usuario.email or usuario.username}\n"
        "Valor: R$ 39,90/mês\n"
    )
    if pix_key:
        mensagem += f"Chave Pix: {pix_key}\n"
    mensagem += "Segue o comprovante para confirmação."
    return f"https://wa.me/{numero}?text={quote(mensagem)}"


def processar_checkout(request, loja, usuario, cupom):
    """
    Fluxo manual: nao cria cobranca externa e nao redireciona para gateway.
    """
    return None


def processar_pagamento_retorno(loja, external_reference, payment_id, status_retorno, resultado):
    """
    Retornos externos nao aprovam assinatura no fluxo manual.
    """
    pagamento = None
    if external_reference:
        pagamento = Pagamento.objects.filter(loja=loja, external_reference=external_reference).first()
    if not pagamento and payment_id:
        pagamento = Pagamento.objects.filter(loja=loja, payment_id=payment_id).first()
    return pagamento


def processar_webhook_pagamento(payload):
    """
    Webhooks externos ficam desativados enquanto o pagamento Premium for manual.
    """
    raise ValueError("webhook de pagamento desativado no fluxo manual")
