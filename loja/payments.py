import base64
import hashlib
import hmac
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.urls import reverse

from .models import Loja, Pagamento


ABACATE_PAY_CHECKOUTS_URL = "https://api.abacatepay.com/v2/checkouts/create"


class AbacatePayError(Exception):
    pass


MercadoPagoError = AbacatePayError


def _base_url(request):
    configured = (
        getattr(settings, "VESTLINK_BASE_URL", "") or getattr(settings, "MODALINK_BASE_URL", "")
    ).strip().rstrip("/")
    if configured:
        return configured
    return request.build_absolute_uri("/").rstrip("/")


def _abacate_pay_headers():
    token = getattr(settings, "ABACATE_PAY_API_KEY", "").strip()
    if not token:
        raise AbacatePayError("Configure ABACATE_PAY_API_KEY para criar pagamentos pela Abacate Pay.")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _post_json(url, payload):
    data = json.dumps(payload).encode("utf-8")
    request = Request(url, data=data, headers=_abacate_pay_headers(), method="POST")
    try:
        with urlopen(request, timeout=20) as response:
            resposta = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise AbacatePayError(f"Abacate Pay recusou o pagamento: {body}") from error
    except URLError as error:
        raise AbacatePayError(f"Nao foi possivel conectar a Abacate Pay: {error.reason}") from error

    if not resposta.get("success", False):
        raise AbacatePayError(f"Abacate Pay recusou o pagamento: {resposta.get('error') or resposta}")
    return resposta.get("data") or {}


def _webhook_url(base_url):
    configured = getattr(settings, "ABACATE_PAY_WEBHOOK_URL", "").strip()
    webhook_url = configured or f"{base_url}{reverse('abacate_pay_webhook')}"
    webhook_secret = getattr(settings, "ABACATE_PAY_WEBHOOK_SECRET", "").strip()
    if webhook_secret and "webhookSecret=" not in webhook_url:
        separator = "&" if "?" in webhook_url else "?"
        webhook_url = f"{webhook_url}{separator}webhookSecret={webhook_secret}"
    return webhook_url


def criar_pagamento_premium_abacate_pay(request, loja, usuario, cupom=None):
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
    return_url = getattr(settings, "ABACATE_PAY_RETURN_URL", "").strip()
    if not return_url:
        return_url = f"{base_url}{reverse('assinatura', kwargs={'slug': loja.slug})}"

    payload = {
        "items": [
            {
                "id": getattr(settings, "ABACATE_PAY_PREMIUM_PRODUCT_ID", "vestlink-premium"),
                "quantity": 1,
            }
        ],
        "methods": ["PIX", "CARD"],
        "externalId": pagamento.external_reference,
        "returnUrl": return_url,
        "completionUrl": f"{base_url}{reverse('pagamento_retorno', kwargs={'slug': loja.slug, 'resultado': 'success'})}",
        "webhookUrl": _webhook_url(base_url),
        "metadata": {
            "loja_id": loja.id,
            "loja_slug": loja.slug,
            "plano": Loja.PLANO_PREMIUM,
            "usuario_email": usuario.email or usuario.username,
            "valor_final_centavos": int(pagamento.valor_final * 100),
        },
    }
    resposta = _post_json(ABACATE_PAY_CHECKOUTS_URL, payload)
    pagamento.preference_id = resposta.get("id", "")
    pagamento.init_point = resposta.get("url", "")
    pagamento.sandbox_init_point = ""
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


criar_preferencia_premium = criar_pagamento_premium_abacate_pay


def validar_assinatura_abacate_pay(raw_body, assinatura):
    secret = getattr(settings, "ABACATE_PAY_WEBHOOK_SECRET", "").strip()
    if not secret:
        return True
    if not assinatura:
        return False
    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).digest()
    expected_base64 = base64.b64encode(digest).decode("ascii")
    expected_hex = digest.hex()
    return hmac.compare_digest(assinatura, expected_base64) or hmac.compare_digest(assinatura, expected_hex)


def atualizar_pagamento_abacate_pay(payload):
    event = payload.get("event") or payload.get("type") or ""
    data = payload.get("data") or payload
    metadata = data.get("metadata") or {}
    external_reference = (
        data.get("externalId")
        or data.get("external_reference")
        or data.get("externalReference")
        or metadata.get("external_reference")
    )
    if not external_reference:
        raise AbacatePayError("Pagamento sem externalId.")

    pagamento = Pagamento.objects.get(external_reference=external_reference)
    if pagamento.status == Pagamento.STATUS_APROVADO and event in {
        "checkout.completed",
        "subscription.completed",
        "subscription.renewed",
    }:
        return pagamento

    status_abacate = (data.get("status") or "").upper()
    payment_id = str(data.get("id") or data.get("paymentId") or data.get("checkoutId") or "")
    if payment_id:
        pagamento.payment_id = payment_id
    pagamento.raw_response = data

    if event in {"checkout.completed", "subscription.completed", "subscription.renewed"} or status_abacate in {
        "PAID",
        "APPROVED",
        "COMPLETED",
    }:
        pagamento.save(update_fields=["payment_id", "raw_response", "atualizado_em"])
        pagamento.marcar_aprovado(payment_id=pagamento.payment_id)
    elif status_abacate in {"PENDING", "PROCESSING"}:
        pagamento.status = Pagamento.STATUS_PENDENTE
        pagamento.save(update_fields=["status", "payment_id", "raw_response", "atualizado_em"])
    elif event in {"checkout.refunded", "checkout.disputed", "checkout.lost"} or status_abacate in {
        "CANCELLED",
        "REFUNDED",
    }:
        pagamento.status = Pagamento.STATUS_CANCELADO
        pagamento.save(update_fields=["status", "payment_id", "raw_response", "atualizado_em"])
    else:
        pagamento.status = Pagamento.STATUS_RECUSADO
        pagamento.save(update_fields=["status", "payment_id", "raw_response", "atualizado_em"])
    return pagamento


atualizar_pagamento_mercado_pago = atualizar_pagamento_abacate_pay
