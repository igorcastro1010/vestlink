import logging
from django.db.models import F
from django.utils import timezone
from django.utils.text import slugify
from urllib.parse import quote

from loja.models import Lead, Vendedor, Produto, ProdutoVariacao
from loja.validators import limpar_telefone

logger = logging.getLogger(__name__)


def _request_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _vendedor_por_codigo(loja, codigo):
    codigo = (codigo or "").strip().lower()
    if not codigo:
        return None
    return loja.vendedores.filter(codigo__iexact=codigo, ativo=True).first()


def _atualizar_esgotado_produto(produto):
    if not produto or not produto.variacoes.exists():
        return

    tem_estoque_disponivel = produto.variacoes.filter(estoque__gt=0, disponivel=True).exists()
    Produto.objects.filter(pk=produto.pk).update(esgotado=not tem_estoque_disponivel)


def _baixar_estoque_variacao_do_lead(lead):
    produto = lead.produto
    if not produto:
        return

    cor = (lead.cor or "").strip()
    tamanho = (lead.tamanho or "").strip()
    variacao = ProdutoVariacao.objects.filter(
        produto=produto,
        cor__iexact=cor,
        tamanho__iexact=tamanho,
    ).first()
    if not variacao:
        return

    if variacao.estoque > 0:
        variacao.estoque -= 1
        if variacao.estoque == 0:
            variacao.disponivel = False
        variacao.save(update_fields=["estoque", "disponivel"])

    _atualizar_esgotado_produto(produto)


def atualizar_status_lead(lead, novo_status, observacao="", usuario=None):
    status_anterior = lead.status
    lead.status = novo_status
    lead.observacao = (observacao or "").strip()
    lead.status_atualizado_por = usuario if getattr(usuario, "is_authenticated", False) else None
    lead.status_atualizado_em = timezone.now()
    lead.save(update_fields=["status", "observacao", "status_atualizado_por", "status_atualizado_em"])

    if status_anterior != Lead.STATUS_CONCLUIDO and novo_status == Lead.STATUS_CONCLUIDO:
        _baixar_estoque_variacao_do_lead(lead)

    return lead


def processar_whatsapp_produto(request, loja, produto, tamanho, cor, cliente_nome, vendedor_codigo):
    """
    Registra o clique de WhatsApp no produto, cria o Lead e retorna o telefone de destino e a mensagem formatada.
    """
    Produto.objects.filter(id=produto.id).update(cliques_whatsapp=F("cliques_whatsapp") + 1)

    detalhes = []
    tamanho = (tamanho or "").strip()
    cor = (cor or "").strip()
    cliente_nome = (cliente_nome or "").strip()
    vendedor_ref = _vendedor_por_codigo(loja, vendedor_codigo)
    
    if tamanho:
        detalhes.append(f"tamanho {tamanho}")
    if cor:
        detalhes.append(f"cor {cor}")

    complemento = f", {', '.join(detalhes)}" if detalhes else ""
    mensagem = f"Olá! Tenho interesse na peça: {produto.nome}{complemento}"
    if cliente_nome:
        mensagem = f"{mensagem}\nCliente: {cliente_nome}"
    if vendedor_ref:
        mensagem = f"{mensagem}\nVendedor: {vendedor_ref.nome}"

    Lead.objects.create(
        loja=loja,
        vendedor=vendedor_ref,
        produto=produto,
        origem=Lead.ORIGEM_PRODUTO,
        cliente_nome=cliente_nome,
        tamanho=tamanho,
        cor=cor,
        status=Lead.STATUS_NOVO,
        mensagem=mensagem,
        ip=_request_ip(request),
        navegador=request.META.get("HTTP_USER_AGENT", "")[:255],
    )

    destino = loja.telefone
    if vendedor_ref and vendedor_ref.telefone:
        destino_vendedor = limpar_telefone(vendedor_ref.telefone)
        if destino_vendedor:
            destino = destino_vendedor
            
    return destino, mensagem


def processar_whatsapp_carrinho(request, loja, mensagem, cliente_nome, cliente_telefone, tipo_entrega, endereco_completo, vendedor_codigo):
    """
    Registra o Lead da sacolinha/carrinho e retorna o telefone de destino e a mensagem formatada.
    """
    mensagem = (mensagem or "").strip()
    cliente_nome = (cliente_nome or "").strip()
    cliente_telefone = (cliente_telefone or "").strip()
    tipo_entrega = (tipo_entrega or "retirada").strip()
    endereco_completo = (endereco_completo or "").strip()
    vendedor_ref = _vendedor_por_codigo(loja, vendedor_codigo)

    if not mensagem:
        mensagem = "Olá! Quero fazer um pedido pelo catálogo."
    if vendedor_ref and "Vendedor:" not in mensagem:
        mensagem = f"{mensagem}\nVendedor: {vendedor_ref.nome}"

    Lead.objects.create(
        loja=loja,
        vendedor=vendedor_ref,
        origem=Lead.ORIGEM_SACOLINHA,
        cliente_nome=cliente_nome,
        cliente_telefone=cliente_telefone,
        status=Lead.STATUS_NOVO,
        tipo_entrega=tipo_entrega,
        endereco_completo=endereco_completo,
        mensagem=mensagem,
        ip=_request_ip(request),
        navegador=request.META.get("HTTP_USER_AGENT", "")[:255],
    )

    destino = loja.telefone
    if vendedor_ref and vendedor_ref.telefone:
        destino_vendedor = limpar_telefone(vendedor_ref.telefone)
        if destino_vendedor:
            destino = destino_vendedor
            
    return destino, mensagem
