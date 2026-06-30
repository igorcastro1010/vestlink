import logging

from django.conf import settings

from loja.models import Cupom, Pagamento
from loja.payments import (
    AbacatePayError,
    atualizar_pagamento_abacate_pay,
    criar_pagamento_premium_abacate_pay,
)

logger = logging.getLogger(__name__)


def obter_dados_checkout(cupom_codigo):
    """
    Resolve o cupom e calcula os valores padrao para a pagina de pagamento.
    """
    cupom_codigo = (cupom_codigo or "").strip().upper()
    cupom = Cupom.objects.filter(codigo__iexact=cupom_codigo, ativo=True).first() if cupom_codigo else None
    valor = Pagamento._meta.get_field("valor").default
    valor_final = cupom.aplicar(valor) if cupom else valor
    abacate_pay_configurado = bool(getattr(settings, "ABACATE_PAY_API_KEY", ""))

    return {
        "cupom": cupom,
        "cupom_codigo": cupom_codigo,
        "valor": valor,
        "valor_final": valor_final,
        "abacate_pay_configurado": abacate_pay_configurado,
    }


def processar_checkout(request, loja, usuario, cupom):
    """
    Cria o pagamento na Abacate Pay e retorna a URL de redirecionamento.
    """
    pagamento = criar_pagamento_premium_abacate_pay(request, loja, usuario, cupom=cupom)
    if pagamento.checkout_url:
        return pagamento.checkout_url
    raise AbacatePayError("A Abacate Pay nao retornou uma URL de pagamento.")


def processar_pagamento_retorno(loja, external_reference, payment_id, status_retorno, resultado):
    """
    Processa o retorno da pagina de pagamento e atualiza o status local quando possivel.
    """
    pagamento = None
    if external_reference:
        pagamento = Pagamento.objects.filter(loja=loja, external_reference=external_reference).first()
    if not pagamento and payment_id:
        pagamento = Pagamento.objects.filter(loja=loja, payment_id=payment_id).first()

    if pagamento:
        if resultado == "success" or status_retorno in {"approved", "PAID", "COMPLETED"}:
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


def processar_webhook_pagamento(payload):
    """
    Processa notificacao de pagamento confirmada pela Abacate Pay.
    """
    if not payload:
        raise ValueError("payload ausente")
    return atualizar_pagamento_abacate_pay(payload)
