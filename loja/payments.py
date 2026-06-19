import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.urls import reverse

from .models import Loja, Pagamento


MERCADO_PAGO_PREFERENCES_URL = "https://api.mercadopago.com/checkout/preferences"
MERCADO_PAGO_PAYMENT_URL = "https://api.mercadopago.com/v1/payments/{payment_id}"


class MercadoPagoError(Exception):
    pass


def _base_url(request):
    configured = (
        getattr(settings, "VESTLINK_BASE_URL", "") or getattr(settings, "MODALINK_BASE_URL", "")
    ).strip().rstrip("/")
    if configured:
        return configured
    return request.build_absolute_uri("/").rstrip("/")


def _mercado_pago_headers():
    token = getattr(settings, "MERCADO_PAGO_ACCESS_TOKEN", "").strip()
    if not token:
        raise MercadoPagoError("Configure MERCADO_PAGO_ACCESS_TOKEN para usar o checkout real.")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _post_json(url, payload):
    data = json.dumps(payload).encode("utf-8")
    request = Request(url, data=data, headers=_mercado_pago_headers(), method="POST")
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise MercadoPagoError(f"Mercado Pago recusou a preferência: {body}") from error
    except URLError as error:
        raise MercadoPagoError(f"Não foi possível conectar ao Mercado Pago: {error.reason}") from error


def _get_json(url):
    request = Request(url, headers=_mercado_pago_headers(), method="GET")
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise MercadoPagoError(f"Não foi possível consultar pagamento: {body}") from error
    except URLError as error:
        raise MercadoPagoError(f"Não foi possível conectar ao Mercado Pago: {error.reason}") from error


def criar_preferencia_premium(request, loja, usuario, cupom=None):
    valor = Pagamento._meta.get_field("valor").default
    valor_final = cupom.aplicar(valor) if cupom else valor
    pagamento = Pagamento.objects.create(
        loja=loja,
        usuario=usuario,
        cupom=cupom,
        valor=valor,
        desconto=valor - valor_final,
        valor_final=valor_final,
        status=Pagamento.STATUS_CRIADO,
    )
    base_url = _base_url(request)
    payload = {
        "items": [
            {
                "id": f"vestlink-premium-{loja.id}",
                "title": f"VestLink Premium - {loja.nome}",
                "description": "Assinatura mensal do catálogo digital VestLink",
                "quantity": 1,
                "currency_id": "BRL",
                "unit_price": float(pagamento.valor_final),
            }
        ],
        "payer": {
            "email": usuario.email or f"{usuario.username}@vestlink.local",
        },
        "back_urls": {
            "success": f"{base_url}{reverse('pagamento_retorno', kwargs={'slug': loja.slug, 'resultado': 'success'})}",
            "pending": f"{base_url}{reverse('pagamento_retorno', kwargs={'slug': loja.slug, 'resultado': 'pending'})}",
            "failure": f"{base_url}{reverse('pagamento_retorno', kwargs={'slug': loja.slug, 'resultado': 'failure'})}",
        },
        "notification_url": f"{base_url}{reverse('mercado_pago_webhook')}",
        "auto_return": "approved",
        "external_reference": pagamento.external_reference,
        "metadata": {
            "loja_id": loja.id,
            "loja_slug": loja.slug,
            "plano": Loja.PLANO_PREMIUM,
        },
    }
    resposta = _post_json(MERCADO_PAGO_PREFERENCES_URL, payload)
    pagamento.preference_id = resposta.get("id", "")
    pagamento.init_point = resposta.get("init_point", "")
    pagamento.sandbox_init_point = resposta.get("sandbox_init_point", "")
    pagamento.status = Pagamento.STATUS_PENDENTE
    pagamento.raw_response = resposta
    pagamento.save(
        update_fields=[
            "preference_id",
            "init_point",
            "sandbox_init_point",
            "status",
            "raw_response",
            "atualizado_em",
        ]
    )
    return pagamento


def atualizar_pagamento_mercado_pago(payment_id):
    dados = _get_json(MERCADO_PAGO_PAYMENT_URL.format(payment_id=payment_id))
    external_reference = dados.get("external_reference", "")
    if not external_reference:
        raise MercadoPagoError("Pagamento sem external_reference.")
    pagamento = Pagamento.objects.get(external_reference=external_reference)
    status_mp = dados.get("status", "")
    pagamento.payment_id = str(dados.get("id") or payment_id)
    pagamento.raw_response = dados
    if status_mp == "approved":
        pagamento.raw_response = dados
        pagamento.save(update_fields=["payment_id", "raw_response", "atualizado_em"])
        pagamento.marcar_aprovado(payment_id=pagamento.payment_id)
    elif status_mp in {"pending", "in_process"}:
        pagamento.status = Pagamento.STATUS_PENDENTE
        pagamento.save(update_fields=["status", "payment_id", "raw_response", "atualizado_em"])
    elif status_mp in {"cancelled", "refunded", "charged_back"}:
        pagamento.status = Pagamento.STATUS_CANCELADO
        pagamento.save(update_fields=["status", "payment_id", "raw_response", "atualizado_em"])
    else:
        pagamento.status = Pagamento.STATUS_RECUSADO
        pagamento.save(update_fields=["status", "payment_id", "raw_response", "atualizado_em"])
    return pagamento
