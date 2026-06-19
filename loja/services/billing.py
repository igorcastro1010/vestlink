import logging
from urllib.parse import urlencode
from django.conf import settings
from django.urls import reverse

from loja.models import Cupom, Pagamento, Loja
from loja.payments import (
    MercadoPagoError,
    criar_preferencia_premium,
    atualizar_pagamento_mercado_pago,
)

logger = logging.getLogger(__name__)


def obter_dados_checkout(cupom_codigo):
    """
    Resolve o cupom e calcula os valores padrão para a página de checkout.
    """
    cupom_codigo = (cupom_codigo or "").strip().upper()
    cupom = Cupom.objects.filter(codigo__iexact=cupom_codigo, ativo=True).first() if cupom_codigo else None
    valor = Pagamento._meta.get_field("valor").default
    valor_final = cupom.aplicar(valor) if cupom else valor
    mercado_pago_configurado = bool(getattr(settings, "MERCADO_PAGO_ACCESS_TOKEN", ""))
    
    return {
        "cupom": cupom,
        "cupom_codigo": cupom_codigo,
        "valor": valor,
        "valor_final": valor_final,
        "mercado_pago_configurado": mercado_pago_configurado,
    }


def processar_checkout(request, loja, usuario, cupom):
    """
    Cria a preferência de pagamento no Mercado Pago ou gera a URL de checkout externa.
    Retorna a URL de redirecionamento correspondente.
    """
    if getattr(settings, "MERCADO_PAGO_ACCESS_TOKEN", ""):
        pagamento = criar_preferencia_premium(request, loja, usuario, cupom=cupom)
        if pagamento.checkout_url:
            return pagamento.checkout_url
            
    checkout_url = getattr(settings, "VESTLINK_CHECKOUT_URL", "") or getattr(settings, "MODALINK_CHECKOUT_URL", "")
    if checkout_url:
        parametros = urlencode(
            {
                "loja": loja.slug,
                "plano": Loja.PLANO_PREMIUM,
                "email": usuario.email or usuario.username,
                "cupom": cupom.codigo if cupom else "",
            }
        )
        separador = "&" if "?" in checkout_url else "?"
        return f"{checkout_url}{separador}{parametros}"
        
    return None


def processar_pagamento_retorno(loja, external_reference, payment_id, status_retorno, resultado):
    """
    Processa o retorno do checkout e atualiza o status do pagamento local.
    """
    pagamento = None
    if external_reference:
        pagamento = Pagamento.objects.filter(loja=loja, external_reference=external_reference).first()
    if not pagamento and payment_id:
        pagamento = Pagamento.objects.filter(loja=loja, payment_id=payment_id).first()

    if pagamento:
        if resultado == "success" or status_retorno == "approved":
            pagamento.marcar_aprovado(payment_id=payment_id)
        elif resultado == "pending":
            pagamento.status = Pagamento.STATUS_PENDENTE
            if payment_id:
                pagamento.payment_id = payment_id
            pagamento.save(update_fields=["status", "payment_id", "atualizado_em"])
        elif resultado == "failure":
            pagamento.status = Pagamento.STATUS_RECUSADO
            if payment_id:
                pagamento.payment_id = payment_id
            pagamento.save(update_fields=["status", "payment_id", "atualizado_em"])
            
    return pagamento


def processar_webhook_pagamento(payment_id):
    """
    Processa a notificação IPN/Webhook do Mercado Pago buscando os dados oficiais do pagamento.
    """
    if not payment_id:
        raise ValueError("payment_id ausente")
    return atualizar_pagamento_mercado_pago(str(payment_id))
